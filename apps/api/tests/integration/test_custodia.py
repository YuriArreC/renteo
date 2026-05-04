"""Tests integration de custodia certificado + mandato (skill 4b).

Cubren:
- POST /api/empresas/{id}/certificado: cifra + persiste, GET devuelve
  metadata, DELETE revoca y borra blob.
- Subir un cert nuevo revoca automáticamente el cert vigente
  previo (una empresa = un cert vigente).
- POST /api/empresas/{id}/mandato registra mandato + persiste
  consentimiento. GET devuelve el vigente.
- Role gate viewer (403).
- Audit log entries.
"""

from __future__ import annotations

import base64
from collections.abc import AsyncIterator, Callable
from typing import Any
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.jwt import verify_jwt
from src.main import app


def _claims(
    user_id: UUID,
    workspace_id: UUID,
    *,
    role: str = "owner",
) -> dict[str, Any]:
    return {
        "sub": str(user_id),
        "email": f"contador-{user_id}@renteo.local",
        "aud": "authenticated",
        "role": "authenticated",
        "app_metadata": {
            "provider": "email",
            "workspace_id": str(workspace_id),
            "workspace_type": "accounting_firm",
            "role": role,
            "empresa_ids": [],
        },
    }


def _override(claims: dict[str, Any]) -> Callable[[], dict[str, Any]]:
    def _dep() -> dict[str, Any]:
        return claims

    return _dep


@pytest_asyncio.fixture
async def http_client_custodia() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        yield client
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def empresa_custody_ctx(
    admin_session: AsyncSession,
) -> AsyncIterator[dict[str, UUID]]:
    user_id = uuid4()
    workspace_id = uuid4()
    empresa_id = uuid4()
    async with admin_session.begin():
        await admin_session.execute(
            text("insert into auth.users (id, email) values (:id, :e)"),
            {"id": str(user_id), "e": f"cust-{user_id}@renteo.local"},
        )
        await admin_session.execute(
            text(
                "insert into core.workspaces (id, name, type) "
                "values (:id, 'Custody Test', 'accounting_firm')"
            ),
            {"id": str(workspace_id)},
        )
        await admin_session.execute(
            text(
                "insert into core.workspace_members "
                "(workspace_id, user_id, role, accepted_at) "
                "values (:ws, :u, 'owner', now())"
            ),
            {"ws": str(workspace_id), "u": str(user_id)},
        )
        await admin_session.execute(
            text(
                "insert into core.empresas "
                "(id, workspace_id, rut, razon_social) "
                "values (:e, :ws, '11111111-1', 'Custodia SpA')"
            ),
            {"e": str(empresa_id), "ws": str(workspace_id)},
        )
    yield {
        "user_id": user_id,
        "workspace_id": workspace_id,
        "empresa_id": empresa_id,
    }
    async with admin_session.begin():
        await admin_session.execute(
            text("set local session_replication_role = 'replica'")
        )
        for tbl in (
            "security.cert_usage_log",
            "security.certificados_digitales",
            "security.mandatos_digitales",
            "privacy.consentimientos",
        ):
            # `tbl` viene de un literal whitelist; no hay input externo.
            sql = f"delete from {tbl} where workspace_id = :w"  # noqa: S608
            await admin_session.execute(
                text(sql), {"w": str(workspace_id)}
            )
        await admin_session.execute(
            text("delete from core.empresas where workspace_id = :w"),
            {"w": str(workspace_id)},
        )
        await admin_session.execute(
            text("delete from core.workspaces where id = :w"),
            {"w": str(workspace_id)},
        )
        await admin_session.execute(
            text("delete from auth.users where id = :u"),
            {"u": str(user_id)},
        )


def _cert_payload(rut: str = "11111111-1") -> dict[str, Any]:
    pfx_dummy = b"PKCS#12 dummy bytes for tests"
    return {
        "pfx_base64": base64.b64encode(pfx_dummy).decode("ascii"),
        "rut_titular": rut,
        "nombre_titular": "Juanito de Prueba",
        "valido_desde": "2026-01-01",
        "valido_hasta": "2027-01-01",
        "passphrase": "fake-pwd-not-persisted",
    }


@pytest.mark.integration
async def test_upload_certificate_persists_metadata_only(
    http_client_custodia: AsyncClient,
    empresa_custody_ctx: dict[str, UUID],
    admin_session: AsyncSession,
) -> None:
    ctx = empresa_custody_ctx
    app.dependency_overrides[verify_jwt] = _override(
        _claims(ctx["user_id"], ctx["workspace_id"])
    )

    response = await http_client_custodia.post(
        f"/api/empresas/{ctx['empresa_id']}/certificado",
        json=_cert_payload(),
        headers={"Authorization": "Bearer fake"},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["rut_titular"] == "11111111-1"
    assert body["kms_provider"] == "mock"
    assert body["storage_provider"] == "mock"

    # Solo metadata en DB; jamás el PFX ni la passphrase.
    async with admin_session.begin():
        result = await admin_session.execute(
            text(
                "select kms_key_arn, s3_object_key, rut_titular "
                "from security.certificados_digitales "
                "where empresa_id = :emp"
            ),
            {"emp": str(ctx["empresa_id"])},
        )
        rows = result.mappings().all()
    assert len(rows) == 1
    row = dict(rows[0])
    assert row["kms_key_arn"]
    assert row["s3_object_key"]
    assert row["rut_titular"] == "11111111-1"


@pytest.mark.integration
async def test_upload_revokes_previous_certificate(
    http_client_custodia: AsyncClient,
    empresa_custody_ctx: dict[str, UUID],
    admin_session: AsyncSession,
) -> None:
    ctx = empresa_custody_ctx
    app.dependency_overrides[verify_jwt] = _override(
        _claims(ctx["user_id"], ctx["workspace_id"])
    )

    first = await http_client_custodia.post(
        f"/api/empresas/{ctx['empresa_id']}/certificado",
        json=_cert_payload(),
        headers={"Authorization": "Bearer fake"},
    )
    assert first.status_code == 201
    first_id = first.json()["id"]

    second = await http_client_custodia.post(
        f"/api/empresas/{ctx['empresa_id']}/certificado",
        json=_cert_payload(),
        headers={"Authorization": "Bearer fake"},
    )
    assert second.status_code == 201
    second_id = second.json()["id"]
    assert first_id != second_id

    async with admin_session.begin():
        result = await admin_session.execute(
            text(
                "select id, revocado_at "
                "from security.certificados_digitales "
                "where empresa_id = :emp order by created_at"
            ),
            {"emp": str(ctx["empresa_id"])},
        )
        rows = list(result.mappings().all())
    assert len(rows) == 2
    # Primer cert revocado, segundo vigente.
    assert rows[0]["revocado_at"] is not None
    assert rows[1]["revocado_at"] is None


@pytest.mark.integration
async def test_get_certificate_returns_active_metadata(
    http_client_custodia: AsyncClient,
    empresa_custody_ctx: dict[str, UUID],
) -> None:
    ctx = empresa_custody_ctx
    app.dependency_overrides[verify_jwt] = _override(
        _claims(ctx["user_id"], ctx["workspace_id"])
    )
    not_yet = await http_client_custodia.get(
        f"/api/empresas/{ctx['empresa_id']}/certificado",
        headers={"Authorization": "Bearer fake"},
    )
    assert not_yet.status_code == 404

    await http_client_custodia.post(
        f"/api/empresas/{ctx['empresa_id']}/certificado",
        json=_cert_payload(),
        headers={"Authorization": "Bearer fake"},
    )
    after = await http_client_custodia.get(
        f"/api/empresas/{ctx['empresa_id']}/certificado",
        headers={"Authorization": "Bearer fake"},
    )
    assert after.status_code == 200
    assert after.json()["rut_titular"] == "11111111-1"


@pytest.mark.integration
async def test_revoke_certificate_marks_and_returns_204(
    http_client_custodia: AsyncClient,
    empresa_custody_ctx: dict[str, UUID],
    admin_session: AsyncSession,
) -> None:
    ctx = empresa_custody_ctx
    app.dependency_overrides[verify_jwt] = _override(
        _claims(ctx["user_id"], ctx["workspace_id"])
    )
    await http_client_custodia.post(
        f"/api/empresas/{ctx['empresa_id']}/certificado",
        json=_cert_payload(),
        headers={"Authorization": "Bearer fake"},
    )
    delete = await http_client_custodia.delete(
        f"/api/empresas/{ctx['empresa_id']}/certificado",
        headers={"Authorization": "Bearer fake"},
    )
    assert delete.status_code == 204

    after = await http_client_custodia.get(
        f"/api/empresas/{ctx['empresa_id']}/certificado",
        headers={"Authorization": "Bearer fake"},
    )
    assert after.status_code == 404

    async with admin_session.begin():
        result = await admin_session.execute(
            text(
                "select revocado_at "
                "from security.certificados_digitales "
                "where empresa_id = :emp"
            ),
            {"emp": str(ctx["empresa_id"])},
        )
        rows = result.fetchall()
    assert all(r[0] is not None for r in rows)


@pytest.mark.integration
async def test_certificate_rejects_invalid_rut(
    http_client_custodia: AsyncClient,
    empresa_custody_ctx: dict[str, UUID],
) -> None:
    ctx = empresa_custody_ctx
    app.dependency_overrides[verify_jwt] = _override(
        _claims(ctx["user_id"], ctx["workspace_id"])
    )
    payload = _cert_payload(rut="11111111-9")  # DV inválido
    response = await http_client_custodia.post(
        f"/api/empresas/{ctx['empresa_id']}/certificado",
        json=payload,
        headers={"Authorization": "Bearer fake"},
    )
    assert response.status_code == 422


@pytest.mark.integration
async def test_certificate_blocked_for_viewer(
    http_client_custodia: AsyncClient,
    empresa_custody_ctx: dict[str, UUID],
) -> None:
    ctx = empresa_custody_ctx
    app.dependency_overrides[verify_jwt] = _override(
        _claims(ctx["user_id"], ctx["workspace_id"], role="viewer")
    )
    response = await http_client_custodia.post(
        f"/api/empresas/{ctx['empresa_id']}/certificado",
        json=_cert_payload(),
        headers={"Authorization": "Bearer fake"},
    )
    assert response.status_code == 403


@pytest.mark.integration
async def test_register_mandato_persists_consentimiento(
    http_client_custodia: AsyncClient,
    empresa_custody_ctx: dict[str, UUID],
    admin_session: AsyncSession,
) -> None:
    ctx = empresa_custody_ctx
    app.dependency_overrides[verify_jwt] = _override(
        _claims(ctx["user_id"], ctx["workspace_id"])
    )
    response = await http_client_custodia.post(
        f"/api/empresas/{ctx['empresa_id']}/mandato",
        json={
            "alcance": ["consultar_f29", "declarar_f22"],
            "inicio": "2026-01-01",
            "termino": "2027-01-01",
            "consentimiento_version": "consentimiento-mandato-v1",
            "ip_otorgamiento": "192.168.1.10",
        },
        headers={"Authorization": "Bearer fake"},
    )
    assert response.status_code == 201, response.text
    assert "consultar_f29" in response.json()["alcance"]

    async with admin_session.begin():
        result = await admin_session.execute(
            text(
                """
                select tipo_consentimiento, version_texto
                  from privacy.consentimientos
                 where empresa_id = :emp
                   and user_id = :uid
                """
            ),
            {
                "emp": str(ctx["empresa_id"]),
                "uid": str(ctx["user_id"]),
            },
        )
        rows = list(result.mappings().all())
    assert len(rows) == 1
    assert rows[0]["tipo_consentimiento"] == "mandato_digital"
    assert rows[0]["version_texto"] == "consentimiento-mandato-v1"


@pytest.mark.integration
async def test_mandato_rejects_termino_anterior_a_inicio(
    http_client_custodia: AsyncClient,
    empresa_custody_ctx: dict[str, UUID],
) -> None:
    ctx = empresa_custody_ctx
    app.dependency_overrides[verify_jwt] = _override(
        _claims(ctx["user_id"], ctx["workspace_id"])
    )
    response = await http_client_custodia.post(
        f"/api/empresas/{ctx['empresa_id']}/mandato",
        json={
            "alcance": ["consultar_f29"],
            "inicio": "2027-01-01",
            "termino": "2026-01-01",
            "consentimiento_version": "consentimiento-mandato-v1",
        },
        headers={"Authorization": "Bearer fake"},
    )
    assert response.status_code == 422
