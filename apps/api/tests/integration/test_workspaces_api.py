"""Tests integration de POST /api/workspaces y GET /api/me.

Mocks `verify_jwt` para no depender de Supabase Auth real; los tests RLS y
del Auth Hook ya cubren la pieza de autenticación.
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


def _claims_for(user_id: UUID, **app_metadata: Any) -> dict[str, Any]:
    base_meta: dict[str, Any] = {"provider": "email"}
    base_meta.update(app_metadata)
    return {
        "sub": str(user_id),
        "aud": "authenticated",
        "role": "authenticated",
        "app_metadata": base_meta,
    }


def _override_jwt(claims: dict[str, Any]) -> Callable[[], dict[str, Any]]:
    def _dep() -> dict[str, Any]:
        return claims

    return _dep


@pytest_asyncio.fixture
async def http_client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        yield client
    app.dependency_overrides.clear()


async def _delete_bypassing_triggers(
    session: AsyncSession, sql: str, params: dict[str, Any]
) -> None:
    """Cleanup helper que desactiva triggers para esta transacción.

    El trigger anti-modificación de security.audit_log bloquea no solo
    DELETEs directos sino también UPDATEs/DELETEs en cascada (ej. el
    SET NULL desde auth.users.id, o el cascade desde core.workspaces.id).
    `session_replication_role = 'replica'` desactiva los triggers
    regulares en la transacción actual; el postgres local de Supabase es
    superuser y permite el cambio.
    """
    async with session.begin():
        await session.execute(
            text("set local session_replication_role = 'replica'")
        )
        await session.execute(text(sql), params)


@pytest_asyncio.fixture
async def fresh_user(admin_session: AsyncSession) -> AsyncIterator[UUID]:
    user_id = uuid4()
    async with admin_session.begin():
        await admin_session.execute(
            text(
                "insert into auth.users (id, email) values (:id, :email)"
            ),
            {"id": str(user_id), "email": f"api-{user_id}@renteo.local"},
        )
    try:
        yield user_id
    finally:
        await _delete_bypassing_triggers(
            admin_session,
            "delete from auth.users where id = :id",
            {"id": str(user_id)},
        )


# ---------------------------------------------------------------------------
# POST /api/workspaces
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_create_workspace_pyme_assigns_owner_role(
    admin_session: AsyncSession,
    http_client: AsyncClient,
    fresh_user: UUID,
) -> None:
    app.dependency_overrides[verify_jwt] = _override_jwt(
        _claims_for(fresh_user)
    )

    response = await http_client.post(
        "/api/workspaces",
        json={
            "name": "Mi Pyme SpA",
            "type": "pyme",
            "consent_tratamiento_datos": True,
        },
        headers={"Authorization": "Bearer fake"},
    )

    assert response.status_code == 201, response.text
    data = response.json()
    assert data["name"] == "Mi Pyme SpA"
    assert data["type"] == "pyme"
    assert data["role"] == "owner"

    ws_id = UUID(data["id"])
    try:
        # Envolver verificaciones en async with begin() para que la
        # auto-transacción se commitee antes del cleanup; de lo contrario
        # admin_session.begin() del finally falla con "transaction already
        # begun".
        async with admin_session.begin():
            result = await admin_session.execute(
                text(
                    "select role, accepted_at from core.workspace_members "
                    "where workspace_id = :ws and user_id = :uid"
                ),
                {"ws": str(ws_id), "uid": str(fresh_user)},
            )
            member = result.mappings().one()
            assert member["role"] == "owner"
            assert member["accepted_at"] is not None

            result = await admin_session.execute(
                text(
                    "select version_texto from privacy.consentimientos "
                    "where user_id = :uid "
                    "  and tipo_consentimiento = 'tratamiento_datos'"
                ),
                {"uid": str(fresh_user)},
            )
            assert (
                result.scalar_one()
                == "consentimiento-tratamiento-datos-v1"
            )

            result = await admin_session.execute(
                text(
                    "select count(*) from security.audit_log "
                    "where workspace_id = :ws and action = 'create' "
                    "  and resource_type = 'workspace'"
                ),
                {"ws": str(ws_id)},
            )
            assert result.scalar_one() == 1
    finally:
        await _delete_bypassing_triggers(
            admin_session,
            "delete from core.workspaces where id = :id",
            {"id": str(ws_id)},
        )


@pytest.mark.integration
async def test_create_workspace_accounting_firm_assigns_lead_role(
    admin_session: AsyncSession,
    http_client: AsyncClient,
    fresh_user: UUID,
) -> None:
    app.dependency_overrides[verify_jwt] = _override_jwt(
        _claims_for(fresh_user)
    )

    response = await http_client.post(
        "/api/workspaces",
        json={
            "name": "Estudio Contable Ltda",
            "type": "accounting_firm",
            "consent_tratamiento_datos": True,
        },
        headers={"Authorization": "Bearer fake"},
    )

    assert response.status_code == 201, response.text
    data = response.json()
    assert data["type"] == "accounting_firm"
    assert data["role"] == "accountant_lead"

    ws_id = UUID(data["id"])
    try:
        async with admin_session.begin():
            result = await admin_session.execute(
                text(
                    "select role from core.workspace_members "
                    "where workspace_id = :ws and user_id = :uid"
                ),
                {"ws": str(ws_id), "uid": str(fresh_user)},
            )
            assert result.scalar_one() == "accountant_lead"
    finally:
        await _delete_bypassing_triggers(
            admin_session,
            "delete from core.workspaces where id = :id",
            {"id": str(ws_id)},
        )


@pytest.mark.integration
async def test_create_workspace_rejects_missing_consent(
    http_client: AsyncClient, fresh_user: UUID
) -> None:
    app.dependency_overrides[verify_jwt] = _override_jwt(
        _claims_for(fresh_user)
    )

    response = await http_client.post(
        "/api/workspaces",
        json={
            "name": "Sin consent",
            "type": "pyme",
            # consent_tratamiento_datos falta
        },
        headers={"Authorization": "Bearer fake"},
    )

    assert response.status_code == 422


@pytest.mark.integration
async def test_create_workspace_rejects_when_user_already_has_one(
    admin_session: AsyncSession,
    http_client: AsyncClient,
    fresh_user: UUID,
) -> None:
    # Pre-crear workspace + member para fresh_user.
    ws_id = uuid4()
    async with admin_session.begin():
        await admin_session.execute(
            text(
                "insert into core.workspaces (id, name, type) "
                "values (:id, 'Existing', 'pyme')"
            ),
            {"id": str(ws_id)},
        )
        await admin_session.execute(
            text(
                "insert into core.workspace_members "
                "(workspace_id, user_id, role, accepted_at) "
                "values (:ws, :uid, 'owner', now())"
            ),
            {"ws": str(ws_id), "uid": str(fresh_user)},
        )

    app.dependency_overrides[verify_jwt] = _override_jwt(
        _claims_for(fresh_user)
    )

    try:
        response = await http_client.post(
            "/api/workspaces",
            json={
                "name": "Segundo intento",
                "type": "pyme",
                "consent_tratamiento_datos": True,
            },
            headers={"Authorization": "Bearer fake"},
        )
        assert response.status_code == 409
    finally:
        await _delete_bypassing_triggers(
            admin_session,
            "delete from core.workspaces where id = :id",
            {"id": str(ws_id)},
        )


# ---------------------------------------------------------------------------
# GET /api/me
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_me_returns_workspace_when_jwt_has_one(
    http_client: AsyncClient, two_workspaces: dict[str, UUID]
) -> None:
    ctx = two_workspaces
    app.dependency_overrides[verify_jwt] = _override_jwt(
        _claims_for(
            ctx["user_a"],
            workspace_id=str(ctx["ws_a"]),
            workspace_type="pyme",
            role="owner",
            empresa_ids=[],
        )
    )

    response = await http_client.get(
        "/api/me", headers={"Authorization": "Bearer fake"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == str(ctx["user_a"])
    assert data["workspace"]["id"] == str(ctx["ws_a"])
    assert data["workspace"]["type"] == "pyme"
    assert data["workspace"]["role"] == "owner"


@pytest.mark.integration
async def test_me_returns_null_workspace_when_jwt_lacks_one(
    http_client: AsyncClient, fresh_user: UUID
) -> None:
    app.dependency_overrides[verify_jwt] = _override_jwt(
        _claims_for(fresh_user)
    )

    response = await http_client.get(
        "/api/me", headers={"Authorization": "Bearer fake"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == str(fresh_user)
    assert data["workspace"] is None
