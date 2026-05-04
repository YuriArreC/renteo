"""Tests integration de /api/alertas/{evaluate,list,patch}."""

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


def _claims(user_id: UUID, workspace_id: UUID) -> dict[str, Any]:
    return {
        "sub": str(user_id),
        "aud": "authenticated",
        "role": "authenticated",
        "app_metadata": {
            "provider": "email",
            "workspace_id": str(workspace_id),
            "workspace_type": "pyme",
            "role": "owner",
            "empresa_ids": [],
        },
    }


def _override(claims: dict[str, Any]) -> Callable[[], dict[str, Any]]:
    def _dep() -> dict[str, Any]:
        return claims

    return _dep


@pytest_asyncio.fixture
async def http_client_alertas() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        yield client
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def workspace_with_empresa(
    admin_session: AsyncSession,
) -> AsyncIterator[dict[str, UUID]]:
    user_id = uuid4()
    workspace_id = uuid4()
    empresa_id = uuid4()
    async with admin_session.begin():
        await admin_session.execute(
            text("insert into auth.users (id, email) values (:id, :e)"),
            {"id": str(user_id), "e": f"alerta-{user_id}@renteo.local"},
        )
        await admin_session.execute(
            text(
                "insert into core.workspaces (id, name, type) "
                "values (:id, 'Alerta', 'pyme')"
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
                "values (:e, :ws, '11111111-1', 'Empresa Alerta')"
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
        await admin_session.execute(
            text("delete from core.alertas where workspace_id = :w"),
            {"w": str(workspace_id)},
        )
        await admin_session.execute(
            text("delete from security.audit_log where workspace_id = :w"),
            {"w": str(workspace_id)},
        )
        await admin_session.execute(
            text("delete from core.empresas where id = :e"),
            {"e": str(empresa_id)},
        )
        await admin_session.execute(
            text("delete from core.workspaces where id = :w"),
            {"w": str(workspace_id)},
        )
        await admin_session.execute(
            text("delete from auth.users where id = :u"),
            {"u": str(user_id)},
        )


_BASE_PAYLOAD: dict[str, Any] = {
    "regimen": "14_d_3",
    "tax_year": 2026,
    "rli_proyectada_pesos": "30000000",
    "retiros_declarados_pesos": "5000000",
    "palancas_aplicadas": [],
}


@pytest.mark.integration
async def test_evaluate_creates_three_alertas_for_pyme_14d3(
    http_client_alertas: AsyncClient,
    workspace_with_empresa: dict[str, UUID],
) -> None:
    ctx = workspace_with_empresa
    app.dependency_overrides[verify_jwt] = _override(
        _claims(ctx["user_id"], ctx["workspace_id"])
    )

    response = await http_client_alertas.post(
        "/api/alertas/evaluate",
        json={**_BASE_PAYLOAD, "empresa_id": str(ctx["empresa_id"])},
        headers={"Authorization": "Bearer fake"},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    # Las 3 alertas iniciales se disparan: rebaja_14e + dep + apv.
    assert data["creadas"] == 3
    tipos = {a["tipo"] for a in data["alertas"]}
    assert tipos == {
        "rebaja_14e_disponible",
        "dep_instantanea_disponible",
        "apv_disponible",
    }


@pytest.mark.integration
async def test_evaluate_dedupes_open_alertas(
    http_client_alertas: AsyncClient,
    workspace_with_empresa: dict[str, UUID],
) -> None:
    """Llamar evaluate dos veces no duplica alertas abiertas."""
    ctx = workspace_with_empresa
    app.dependency_overrides[verify_jwt] = _override(
        _claims(ctx["user_id"], ctx["workspace_id"])
    )

    body = {**_BASE_PAYLOAD, "empresa_id": str(ctx["empresa_id"])}
    first = await http_client_alertas.post(
        "/api/alertas/evaluate",
        json=body,
        headers={"Authorization": "Bearer fake"},
    )
    assert first.status_code == 200, first.text
    assert first.json()["creadas"] == 3

    second = await http_client_alertas.post(
        "/api/alertas/evaluate",
        json=body,
        headers={"Authorization": "Bearer fake"},
    )
    assert second.json()["creadas"] == 0
    assert second.json()["ya_existentes"] == 3


@pytest.mark.integration
async def test_evaluate_no_alertas_when_palancas_aplicadas(
    http_client_alertas: AsyncClient,
    workspace_with_empresa: dict[str, UUID],
) -> None:
    ctx = workspace_with_empresa
    app.dependency_overrides[verify_jwt] = _override(
        _claims(ctx["user_id"], ctx["workspace_id"])
    )

    body = {
        **_BASE_PAYLOAD,
        "empresa_id": str(ctx["empresa_id"]),
        "palancas_aplicadas": ["rebaja_14e", "dep_instantanea", "apv"],
    }
    response = await http_client_alertas.post(
        "/api/alertas/evaluate",
        json=body,
        headers={"Authorization": "Bearer fake"},
    )
    assert response.json()["creadas"] == 0


@pytest.mark.integration
async def test_evaluate_rejects_empresa_de_otro_workspace(
    http_client_alertas: AsyncClient,
    workspace_with_empresa: dict[str, UUID],
) -> None:
    ctx = workspace_with_empresa
    app.dependency_overrides[verify_jwt] = _override(
        _claims(ctx["user_id"], ctx["workspace_id"])
    )

    response = await http_client_alertas.post(
        "/api/alertas/evaluate",
        json={**_BASE_PAYLOAD, "empresa_id": str(uuid4())},
        headers={"Authorization": "Bearer fake"},
    )
    assert response.status_code == 422


@pytest.mark.integration
async def test_list_filters_default_to_open_estados(
    http_client_alertas: AsyncClient,
    workspace_with_empresa: dict[str, UUID],
) -> None:
    ctx = workspace_with_empresa
    app.dependency_overrides[verify_jwt] = _override(
        _claims(ctx["user_id"], ctx["workspace_id"])
    )

    create = await http_client_alertas.post(
        "/api/alertas/evaluate",
        json={**_BASE_PAYLOAD, "empresa_id": str(ctx["empresa_id"])},
        headers={"Authorization": "Bearer fake"},
    )
    alerta_id = create.json()["alertas"][0]["id"]

    # Descartar la primera.
    patched = await http_client_alertas.patch(
        f"/api/alertas/{alerta_id}",
        json={"estado": "descartada"},
        headers={"Authorization": "Bearer fake"},
    )
    assert patched.status_code == 200, patched.text

    listed = await http_client_alertas.get(
        "/api/alertas",
        headers={"Authorization": "Bearer fake"},
    )
    ids_open = {a["id"] for a in listed.json()["alertas"]}
    assert alerta_id not in ids_open

    listed_all = await http_client_alertas.get(
        "/api/alertas?incluir_cerradas=true",
        headers={"Authorization": "Bearer fake"},
    )
    ids_all = {a["id"] for a in listed_all.json()["alertas"]}
    assert alerta_id in ids_all


@pytest.mark.integration
async def test_patch_alerta_requires_workspace_ownership(
    http_client_alertas: AsyncClient,
    workspace_with_empresa: dict[str, UUID],
) -> None:
    ctx = workspace_with_empresa
    app.dependency_overrides[verify_jwt] = _override(
        _claims(ctx["user_id"], ctx["workspace_id"])
    )

    response = await http_client_alertas.patch(
        f"/api/alertas/{uuid4()}",
        json={"estado": "vista"},
        headers={"Authorization": "Bearer fake"},
    )
    assert response.status_code == 404
