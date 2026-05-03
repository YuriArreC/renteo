"""Tests del portal ARCOP (skill 5)."""

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
    user_id: UUID, workspace_id: UUID, *, role: str = "owner"
) -> dict[str, Any]:
    return {
        "sub": str(user_id),
        "aud": "authenticated",
        "role": "authenticated",
        "app_metadata": {
            "provider": "email",
            "workspace_id": str(workspace_id),
            "workspace_type": "pyme",
            "role": role,
            "empresa_ids": [],
        },
    }


def _override(claims: dict[str, Any]) -> Callable[[], dict[str, Any]]:
    def _dep() -> dict[str, Any]:
        return claims

    return _dep


@pytest_asyncio.fixture
async def http_client_arcop() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        yield client
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def workspace_with_two_users(
    admin_session: AsyncSession,
) -> AsyncIterator[dict[str, UUID]]:
    """Workspace con un owner y un viewer (otro user)."""
    owner_id = uuid4()
    viewer_id = uuid4()
    workspace_id = uuid4()
    async with admin_session.begin():
        for uid in (owner_id, viewer_id):
            await admin_session.execute(
                text("insert into auth.users (id, email) values (:id, :e)"),
                {"id": str(uid), "e": f"arcop-{uid}@renteo.local"},
            )
        await admin_session.execute(
            text(
                "insert into core.workspaces (id, name, type) "
                "values (:id, 'ARCOP', 'pyme')"
            ),
            {"id": str(workspace_id)},
        )
        await admin_session.execute(
            text(
                "insert into core.workspace_members "
                "(workspace_id, user_id, role, accepted_at) values "
                "(:ws, :owner, 'owner', now()), "
                "(:ws, :viewer, 'viewer', now())"
            ),
            {
                "ws": str(workspace_id),
                "owner": str(owner_id),
                "viewer": str(viewer_id),
            },
        )
    yield {
        "owner_id": owner_id,
        "viewer_id": viewer_id,
        "workspace_id": workspace_id,
    }
    async with admin_session.begin():
        await admin_session.execute(
            text("set local session_replication_role = 'replica'")
        )
        await admin_session.execute(
            text(
                "delete from privacy.arcop_requests where workspace_id = :w"
            ),
            {"w": str(workspace_id)},
        )
        await admin_session.execute(
            text("delete from security.audit_log where workspace_id = :w"),
            {"w": str(workspace_id)},
        )
        await admin_session.execute(
            text("delete from core.workspaces where id = :w"),
            {"w": str(workspace_id)},
        )
        await admin_session.execute(
            text("delete from auth.users where id in (:o, :v)"),
            {"o": str(owner_id), "v": str(viewer_id)},
        )


@pytest.mark.integration
async def test_create_arcop_returns_201_with_recibida_estado(
    http_client_arcop: AsyncClient,
    workspace_with_two_users: dict[str, UUID],
) -> None:
    ctx = workspace_with_two_users
    app.dependency_overrides[verify_jwt] = _override(
        _claims(ctx["owner_id"], ctx["workspace_id"])
    )

    response = await http_client_arcop.post(
        "/api/privacy/arcop",
        json={
            "tipo": "acceso",
            "descripcion": "Quiero descargar mis datos.",
        },
        headers={"Authorization": "Bearer fake"},
    )

    assert response.status_code == 201, response.text
    data = response.json()
    assert UUID(data["id"])
    assert data["tipo"] == "acceso"
    assert data["estado"] == "recibida"
    assert data["respondida_at"] is None


@pytest.mark.integration
async def test_create_arcop_rejects_invalid_tipo(
    http_client_arcop: AsyncClient,
    workspace_with_two_users: dict[str, UUID],
) -> None:
    ctx = workspace_with_two_users
    app.dependency_overrides[verify_jwt] = _override(
        _claims(ctx["owner_id"], ctx["workspace_id"])
    )

    response = await http_client_arcop.post(
        "/api/privacy/arcop",
        json={"tipo": "no-existe"},
        headers={"Authorization": "Bearer fake"},
    )
    assert response.status_code == 422


@pytest.mark.integration
async def test_owner_lists_all_arcop_in_workspace(
    http_client_arcop: AsyncClient,
    workspace_with_two_users: dict[str, UUID],
) -> None:
    """El viewer ve solo las suyas; el owner ve las de los dos usuarios."""
    ctx = workspace_with_two_users

    # viewer crea una.
    app.dependency_overrides[verify_jwt] = _override(
        _claims(ctx["viewer_id"], ctx["workspace_id"], role="viewer")
    )
    r1 = await http_client_arcop.post(
        "/api/privacy/arcop",
        json={"tipo": "rectificacion", "descripcion": "Mi nombre está mal."},
        headers={"Authorization": "Bearer fake"},
    )
    assert r1.status_code == 201, r1.text

    # owner crea otra.
    app.dependency_overrides[verify_jwt] = _override(
        _claims(ctx["owner_id"], ctx["workspace_id"])
    )
    r2 = await http_client_arcop.post(
        "/api/privacy/arcop",
        json={"tipo": "portabilidad"},
        headers={"Authorization": "Bearer fake"},
    )
    assert r2.status_code == 201, r2.text

    # owner ve las dos.
    listed_owner = await http_client_arcop.get(
        "/api/privacy/arcop",
        headers={"Authorization": "Bearer fake"},
    )
    assert listed_owner.status_code == 200
    tipos_owner = {s["tipo"] for s in listed_owner.json()["solicitudes"]}
    assert {"rectificacion", "portabilidad"}.issubset(tipos_owner)

    # viewer ve solo la suya.
    app.dependency_overrides[verify_jwt] = _override(
        _claims(ctx["viewer_id"], ctx["workspace_id"], role="viewer")
    )
    listed_viewer = await http_client_arcop.get(
        "/api/privacy/arcop",
        headers={"Authorization": "Bearer fake"},
    )
    tipos_viewer = {s["tipo"] for s in listed_viewer.json()["solicitudes"]}
    assert tipos_viewer == {"rectificacion"}


@pytest.mark.integration
async def test_create_arcop_logs_audit(
    http_client_arcop: AsyncClient,
    workspace_with_two_users: dict[str, UUID],
    admin_session: AsyncSession,
) -> None:
    ctx = workspace_with_two_users
    app.dependency_overrides[verify_jwt] = _override(
        _claims(ctx["owner_id"], ctx["workspace_id"])
    )

    await http_client_arcop.post(
        "/api/privacy/arcop",
        json={"tipo": "cancelacion"},
        headers={"Authorization": "Bearer fake"},
    )

    async with admin_session.begin():
        result = await admin_session.execute(
            text(
                "select action, resource_type, metadata "
                "from security.audit_log "
                "where workspace_id = :w and resource_type = 'arcop'"
            ),
            {"w": str(ctx["workspace_id"])},
        )
        rows = [dict(r) for r in result.mappings().all()]
    assert len(rows) == 1
    assert rows[0]["action"] == "create"
    assert rows[0]["metadata"]["tipo"] == "cancelacion"
