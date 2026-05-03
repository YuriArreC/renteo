"""Tests integration de POST/GET /api/empresas."""

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
    workspace_type: str = "pyme",
) -> dict[str, Any]:
    return {
        "sub": str(user_id),
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
async def http_client_emp() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        yield client
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def workspace_ctx(
    admin_session: AsyncSession,
) -> AsyncIterator[dict[str, UUID]]:
    user_id = uuid4()
    workspace_id = uuid4()
    async with admin_session.begin():
        await admin_session.execute(
            text("insert into auth.users (id, email) values (:id, :e)"),
            {"id": str(user_id), "e": f"emp-{user_id}@renteo.local"},
        )
        await admin_session.execute(
            text(
                "insert into core.workspaces (id, name, type) "
                "values (:id, 'Emp test', 'pyme')"
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
            text("delete from core.empresas where workspace_id = :ws"),
            {"ws": str(workspace_id)},
        )
        await admin_session.execute(
            text("delete from core.workspaces where id = :id"),
            {"id": str(workspace_id)},
        )
        await admin_session.execute(
            text("delete from auth.users where id = :id"),
            {"id": str(user_id)},
        )


@pytest.mark.integration
async def test_create_empresa_returns_201_with_canonical_rut(
    http_client_emp: AsyncClient, workspace_ctx: dict[str, UUID]
) -> None:
    app.dependency_overrides[verify_jwt] = _override_jwt(
        _claims(workspace_ctx["user_id"], workspace_ctx["workspace_id"])
    )

    response = await http_client_emp.post(
        "/api/empresas",
        json={
            "rut": "11.111.111-1",
            "razon_social": "Mi Pyme SpA",
            "giro": "Comercio al por menor",
            "regimen_actual": "14_d_3",
        },
        headers={"Authorization": "Bearer fake"},
    )

    assert response.status_code == 201, response.text
    data = response.json()
    assert data["rut"] == "11111111-1"
    assert data["razon_social"] == "Mi Pyme SpA"
    assert data["regimen_actual"] == "14_d_3"
    assert UUID(data["id"])


@pytest.mark.integration
async def test_create_empresa_rejects_invalid_rut(
    http_client_emp: AsyncClient, workspace_ctx: dict[str, UUID]
) -> None:
    app.dependency_overrides[verify_jwt] = _override_jwt(
        _claims(workspace_ctx["user_id"], workspace_ctx["workspace_id"])
    )

    response = await http_client_emp.post(
        "/api/empresas",
        json={"rut": "11111111-9", "razon_social": "Foo SpA"},
        headers={"Authorization": "Bearer fake"},
    )
    assert response.status_code == 422


@pytest.mark.integration
async def test_create_empresa_rejects_duplicate_rut_in_workspace(
    http_client_emp: AsyncClient, workspace_ctx: dict[str, UUID]
) -> None:
    app.dependency_overrides[verify_jwt] = _override_jwt(
        _claims(workspace_ctx["user_id"], workspace_ctx["workspace_id"])
    )
    body = {"rut": "11111111-1", "razon_social": "Dup"}

    first = await http_client_emp.post(
        "/api/empresas",
        json=body,
        headers={"Authorization": "Bearer fake"},
    )
    assert first.status_code == 201, first.text

    second = await http_client_emp.post(
        "/api/empresas",
        json=body,
        headers={"Authorization": "Bearer fake"},
    )
    assert second.status_code == 409


@pytest.mark.integration
async def test_create_empresa_blocked_for_viewer_role(
    http_client_emp: AsyncClient, workspace_ctx: dict[str, UUID]
) -> None:
    app.dependency_overrides[verify_jwt] = _override_jwt(
        _claims(
            workspace_ctx["user_id"],
            workspace_ctx["workspace_id"],
            role="viewer",
        )
    )

    response = await http_client_emp.post(
        "/api/empresas",
        json={"rut": "11111111-1", "razon_social": "Foo"},
        headers={"Authorization": "Bearer fake"},
    )
    assert response.status_code == 403


@pytest.mark.integration
async def test_list_empresas_returns_workspace_only(
    http_client_emp: AsyncClient, workspace_ctx: dict[str, UUID]
) -> None:
    app.dependency_overrides[verify_jwt] = _override_jwt(
        _claims(workspace_ctx["user_id"], workspace_ctx["workspace_id"])
    )

    initial = await http_client_emp.get(
        "/api/empresas",
        headers={"Authorization": "Bearer fake"},
    )
    assert initial.status_code == 200
    initial_count = len(initial.json()["empresas"])

    create = await http_client_emp.post(
        "/api/empresas",
        json={"rut": "12345678-5", "razon_social": "Foo SpA"},
        headers={"Authorization": "Bearer fake"},
    )
    assert create.status_code == 201, create.text

    listed = await http_client_emp.get(
        "/api/empresas",
        headers={"Authorization": "Bearer fake"},
    )
    items = listed.json()["empresas"]
    assert len(items) == initial_count + 1
    ruts = {e["rut"] for e in items}
    assert "12345678-5" in ruts
