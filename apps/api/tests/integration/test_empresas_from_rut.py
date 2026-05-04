"""Tests integration del onboarding empresa desde RUT (cierre cliente B).

Cubren: alta auto-asistida con datos del lookup mock, manejo de RUT
sin padrón (000), conflicto de RUT duplicado, role gate y sync RCV
ejecutado.
"""

from __future__ import annotations

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
    workspace_type: str = "accounting_firm",
) -> dict[str, Any]:
    return {
        "sub": str(user_id),
        "email": f"contador-{user_id}@renteo.local",
        "aud": "authenticated",
        "role": "authenticated",
        "app_metadata": {
            "provider": "email",
            "workspace_id": str(workspace_id),
            "workspace_type": workspace_type,
            "role": role,
            "empresa_ids": [],
        },
    }


def _override_jwt(claims: dict[str, Any]) -> Callable[[], dict[str, Any]]:
    def _dep() -> dict[str, Any]:
        return claims

    return _dep


@pytest_asyncio.fixture
async def http_client_onboarding() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        yield client
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def workspace_onb(
    admin_session: AsyncSession,
) -> AsyncIterator[dict[str, UUID]]:
    user_id = uuid4()
    workspace_id = uuid4()
    async with admin_session.begin():
        await admin_session.execute(
            text("insert into auth.users (id, email) values (:id, :e)"),
            {"id": str(user_id), "e": f"onb-{user_id}@renteo.local"},
        )
        await admin_session.execute(
            text(
                "insert into core.workspaces (id, name, type) "
                "values (:id, 'Onboarding test', 'accounting_firm')"
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
    yield {"user_id": user_id, "workspace_id": workspace_id}
    async with admin_session.begin():
        await admin_session.execute(
            text("set local session_replication_role = 'replica'")
        )
        await admin_session.execute(
            text(
                "delete from tax_data.sii_sync_log where workspace_id = :w"
            ),
            {"w": str(workspace_id)},
        )
        await admin_session.execute(
            text("delete from tax_data.rcv_lines where workspace_id = :w"),
            {"w": str(workspace_id)},
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


@pytest.mark.integration
async def test_onboarding_from_rut_with_mock_lookup(
    http_client_onboarding: AsyncClient,
    workspace_onb: dict[str, UUID],
) -> None:
    app.dependency_overrides[verify_jwt] = _override_jwt(
        _claims(workspace_onb["user_id"], workspace_onb["workspace_id"])
    )
    response = await http_client_onboarding.post(
        "/api/empresas/from-rut",
        json={"rut": "11.111.111-1", "sync_meses": 3},
        headers={"Authorization": "Bearer fake"},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["rut"] == "11111111-1"
    assert body["razon_social"]
    assert body["lookup"]["via_sii"] is True
    assert body["regimen_actual"] in ("14_a", "14_d_3", "14_d_8")
    sync = body["sync"]
    assert sync is not None
    assert sync["status"] == "success"
    assert sync["rcv_rows_inserted"] >= 3 * 7  # min compras+ventas/mes
    assert UUID(body["empresa_id"])


@pytest.mark.integration
async def test_onboarding_falla_si_rut_no_existe_ni_fallback(
    http_client_onboarding: AsyncClient,
    workspace_onb: dict[str, UUID],
) -> None:
    """RUT terminado en '000' simula RUT inexistente en padrón mock."""
    app.dependency_overrides[verify_jwt] = _override_jwt(
        _claims(workspace_onb["user_id"], workspace_onb["workspace_id"])
    )
    response = await http_client_onboarding.post(
        "/api/empresas/from-rut",
        json={"rut": "12000000-4"},
        headers={"Authorization": "Bearer fake"},
    )
    assert response.status_code == 422
    assert "razon_social_fallback" in response.json()["detail"]


@pytest.mark.integration
async def test_onboarding_usa_fallback_cuando_rut_no_existe(
    http_client_onboarding: AsyncClient,
    workspace_onb: dict[str, UUID],
) -> None:
    app.dependency_overrides[verify_jwt] = _override_jwt(
        _claims(workspace_onb["user_id"], workspace_onb["workspace_id"])
    )
    response = await http_client_onboarding.post(
        "/api/empresas/from-rut",
        json={
            "rut": "12000000-4",
            "razon_social_fallback": "Empresa Fallback SpA",
            "sync_meses": 2,
        },
        headers={"Authorization": "Bearer fake"},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["razon_social"] == "Empresa Fallback SpA"
    assert body["lookup"]["via_sii"] is False
    assert any("padrón SII" in w for w in body["warnings"])


@pytest.mark.integration
async def test_onboarding_rechaza_rut_invalido(
    http_client_onboarding: AsyncClient,
    workspace_onb: dict[str, UUID],
) -> None:
    app.dependency_overrides[verify_jwt] = _override_jwt(
        _claims(workspace_onb["user_id"], workspace_onb["workspace_id"])
    )
    response = await http_client_onboarding.post(
        "/api/empresas/from-rut",
        json={"rut": "11111111-9"},  # DV incorrecto
        headers={"Authorization": "Bearer fake"},
    )
    assert response.status_code == 422


@pytest.mark.integration
async def test_onboarding_409_si_rut_ya_registrado(
    http_client_onboarding: AsyncClient,
    workspace_onb: dict[str, UUID],
) -> None:
    app.dependency_overrides[verify_jwt] = _override_jwt(
        _claims(workspace_onb["user_id"], workspace_onb["workspace_id"])
    )
    body = {"rut": "11111111-1", "sync_meses": 2}
    first = await http_client_onboarding.post(
        "/api/empresas/from-rut",
        json=body,
        headers={"Authorization": "Bearer fake"},
    )
    assert first.status_code == 201, first.text
    second = await http_client_onboarding.post(
        "/api/empresas/from-rut",
        json=body,
        headers={"Authorization": "Bearer fake"},
    )
    assert second.status_code == 409


@pytest.mark.integration
async def test_onboarding_blocked_for_viewer(
    http_client_onboarding: AsyncClient,
    workspace_onb: dict[str, UUID],
) -> None:
    app.dependency_overrides[verify_jwt] = _override_jwt(
        _claims(
            workspace_onb["user_id"],
            workspace_onb["workspace_id"],
            role="viewer",
        )
    )
    response = await http_client_onboarding.post(
        "/api/empresas/from-rut",
        json={"rut": "11111111-1"},
        headers={"Authorization": "Bearer fake"},
    )
    assert response.status_code == 403
