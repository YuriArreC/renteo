"""Tests integration de POST /api/empresas/{id}/sync-sii y
GET /api/empresas/{id}/sync-status (track skill 4)."""

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
async def http_client_sii() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        yield client
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def empresa_ctx(
    admin_session: AsyncSession,
) -> AsyncIterator[dict[str, UUID]]:
    user_id = uuid4()
    workspace_id = uuid4()
    empresa_id = uuid4()
    async with admin_session.begin():
        await admin_session.execute(
            text("insert into auth.users (id, email) values (:id, :e)"),
            {"id": str(user_id), "e": f"sii-{user_id}@renteo.local"},
        )
        await admin_session.execute(
            text(
                "insert into core.workspaces (id, name, type) "
                "values (:id, 'SII test', 'pyme')"
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
                "(id, workspace_id, rut, razon_social, regimen_actual) "
                "values (:e, :ws, '11111111-1', 'SII Empresa', '14_d_3')"
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
            text(
                "delete from tax_data.sii_sync_log "
                "where workspace_id = :w"
            ),
            {"w": str(workspace_id)},
        )
        await admin_session.execute(
            text(
                "delete from tax_data.rcv_lines where workspace_id = :w"
            ),
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
async def test_sync_sii_with_mock_persists_rcv_lines(
    http_client_sii: AsyncClient, empresa_ctx: dict[str, UUID]
) -> None:
    app.dependency_overrides[verify_jwt] = _override_jwt(
        _claims(empresa_ctx["user_id"], empresa_ctx["workspace_id"])
    )

    response = await http_client_sii.post(
        f"/api/empresas/{empresa_ctx['empresa_id']}/sync-sii",
        json={"months": 3},
        headers={"Authorization": "Bearer fake"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["provider"] == "mock"
    assert body["status"] == "success"
    assert body["rcv_rows_inserted"] >= 3 * 7  # min 3 compras + 4 ventas/mes
    assert UUID(body["sync_id"])


@pytest.mark.integration
async def test_sync_status_reflects_last_sync(
    http_client_sii: AsyncClient, empresa_ctx: dict[str, UUID]
) -> None:
    app.dependency_overrides[verify_jwt] = _override_jwt(
        _claims(empresa_ctx["user_id"], empresa_ctx["workspace_id"])
    )

    pre = await http_client_sii.get(
        f"/api/empresas/{empresa_ctx['empresa_id']}/sync-status",
        headers={"Authorization": "Bearer fake"},
    )
    assert pre.status_code == 200
    assert pre.json()["last_sync_at"] is None
    assert pre.json()["rcv_rows_total"] == 0

    sync = await http_client_sii.post(
        f"/api/empresas/{empresa_ctx['empresa_id']}/sync-sii",
        json={"months": 2},
        headers={"Authorization": "Bearer fake"},
    )
    assert sync.status_code == 200, sync.text
    inserted = sync.json()["rcv_rows_inserted"]

    post = await http_client_sii.get(
        f"/api/empresas/{empresa_ctx['empresa_id']}/sync-status",
        headers={"Authorization": "Bearer fake"},
    )
    assert post.status_code == 200
    body = post.json()
    assert body["last_sync_status"] == "success"
    assert body["last_sync_provider"] == "mock"
    assert body["rcv_rows_total"] == inserted


@pytest.mark.integration
async def test_sync_sii_idempotent_for_same_periods(
    http_client_sii: AsyncClient, empresa_ctx: dict[str, UUID]
) -> None:
    """Reintentar la sync sobre los mismos meses no duplica filas."""
    app.dependency_overrides[verify_jwt] = _override_jwt(
        _claims(empresa_ctx["user_id"], empresa_ctx["workspace_id"])
    )
    payload = {"months": 2}

    first = await http_client_sii.post(
        f"/api/empresas/{empresa_ctx['empresa_id']}/sync-sii",
        json=payload,
        headers={"Authorization": "Bearer fake"},
    )
    assert first.status_code == 200
    rows_first = first.json()["rcv_rows_inserted"]

    second = await http_client_sii.post(
        f"/api/empresas/{empresa_ctx['empresa_id']}/sync-sii",
        json=payload,
        headers={"Authorization": "Bearer fake"},
    )
    assert second.status_code == 200
    status = await http_client_sii.get(
        f"/api/empresas/{empresa_ctx['empresa_id']}/sync-status",
        headers={"Authorization": "Bearer fake"},
    )
    # Mismo conteo total → no se duplicó.
    assert status.json()["rcv_rows_total"] == rows_first


@pytest.mark.integration
async def test_sync_sii_blocked_for_viewer_role(
    http_client_sii: AsyncClient, empresa_ctx: dict[str, UUID]
) -> None:
    app.dependency_overrides[verify_jwt] = _override_jwt(
        _claims(
            empresa_ctx["user_id"],
            empresa_ctx["workspace_id"],
            role="viewer",
        )
    )
    response = await http_client_sii.post(
        f"/api/empresas/{empresa_ctx['empresa_id']}/sync-sii",
        headers={"Authorization": "Bearer fake"},
    )
    assert response.status_code == 403


@pytest.mark.integration
async def test_sync_sii_404_for_unknown_empresa(
    http_client_sii: AsyncClient, empresa_ctx: dict[str, UUID]
) -> None:
    app.dependency_overrides[verify_jwt] = _override_jwt(
        _claims(empresa_ctx["user_id"], empresa_ctx["workspace_id"])
    )
    fake = uuid4()
    response = await http_client_sii.post(
        f"/api/empresas/{fake}/sync-sii",
        headers={"Authorization": "Bearer fake"},
    )
    assert response.status_code == 404
