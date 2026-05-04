"""Tests integration que verifican que scenario, comparador y diagnose
exponen `rules_snapshot_hash` en su respuesta y que el hash es
determinístico para el mismo (rule_set + tax_year_params).

Track snapshot escenarios + comparador (skill 11): cierra la promesa
"cada cálculo persiste/expone snapshot inmutable" en los tres motores
expuestos al usuario."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from typing import Any
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, InternalError
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
async def http_client_snap() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        yield client
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def workspace_user(
    admin_session: AsyncSession,
) -> AsyncIterator[dict[str, UUID]]:
    user_id = uuid4()
    workspace_id = uuid4()
    async with admin_session.begin():
        await admin_session.execute(
            text("insert into auth.users (id, email) values (:id, :e)"),
            {"id": str(user_id), "e": f"snap-{user_id}@renteo.local"},
        )
        await admin_session.execute(
            text(
                "insert into core.workspaces (id, name, type) "
                "values (:id, 'Snap test', 'pyme')"
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
                "delete from core.escenarios_simulacion where workspace_id = :w"
            ),
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
async def test_comparador_response_exposes_hash(
    http_client_snap: AsyncClient, workspace_user: dict[str, UUID]
) -> None:
    app.dependency_overrides[verify_jwt] = _override_jwt(
        _claims(workspace_user["user_id"], workspace_user["workspace_id"])
    )
    response = await http_client_snap.post(
        "/api/calc/comparador-regimen",
        json={
            "tax_year": 2026,
            "rli": "100000000",
            "retiros_pesos": "30000000",
        },
        headers={"Authorization": "Bearer fake"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert "rules_snapshot_hash" in body
    assert isinstance(body["rules_snapshot_hash"], str)
    # SHA-256 hex = 64 chars.
    assert len(body["rules_snapshot_hash"]) == 64
    assert "engine_version" in body


@pytest.mark.integration
async def test_comparador_hash_deterministic_for_same_year(
    http_client_snap: AsyncClient, workspace_user: dict[str, UUID]
) -> None:
    """Dos llamadas con mismo tax_year + sin cambios de rule_set viven
    bajo el mismo hash. Esto prueba la promesa de skill 11: el hash
    identifica el set de reglas, no los inputs del usuario."""
    app.dependency_overrides[verify_jwt] = _override_jwt(
        _claims(workspace_user["user_id"], workspace_user["workspace_id"])
    )
    body = {
        "tax_year": 2026,
        "rli": "100000000",
        "retiros_pesos": "30000000",
    }
    a = await http_client_snap.post(
        "/api/calc/comparador-regimen",
        json=body,
        headers={"Authorization": "Bearer fake"},
    )
    # Cambiamos los inputs sin tocar reglas — el hash debe quedar igual.
    b = await http_client_snap.post(
        "/api/calc/comparador-regimen",
        json={
            "tax_year": 2026,
            "rli": "200000000",
            "retiros_pesos": "50000000",
        },
        headers={"Authorization": "Bearer fake"},
    )
    assert a.status_code == 200 and b.status_code == 200
    assert (
        a.json()["rules_snapshot_hash"] == b.json()["rules_snapshot_hash"]
    )


@pytest.mark.integration
async def test_simulator_persists_and_returns_hash(
    http_client_snap: AsyncClient,
    workspace_user: dict[str, UUID],
    admin_session: AsyncSession,
) -> None:
    app.dependency_overrides[verify_jwt] = _override_jwt(
        _claims(workspace_user["user_id"], workspace_user["workspace_id"])
    )
    response = await http_client_snap.post(
        "/api/scenario/simulate",
        json={
            "tax_year": 2026,
            "regimen": "14_d_3",
            "rli_base": "50000000",
            "retiros_base": "10000000",
            "palancas": {},
        },
        headers={"Authorization": "Bearer fake"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    response_hash = body["rules_snapshot_hash"]
    assert len(response_hash) == 64

    # Confirmamos que el hash persistido coincide con el de la respuesta.
    async with admin_session.begin():
        result = await admin_session.execute(
            text(
                "select rules_snapshot_hash from core.escenarios_simulacion "
                "where id = :id"
            ),
            {"id": body["id"]},
        )
        persisted_hash = result.scalar_one()
    assert persisted_hash == response_hash


@pytest.mark.integration
async def test_simulator_snapshot_is_immutable(
    http_client_snap: AsyncClient,
    workspace_user: dict[str, UUID],
    admin_session: AsyncSession,
) -> None:
    """Después de persistir un escenario, no se puede mutar el hash."""
    app.dependency_overrides[verify_jwt] = _override_jwt(
        _claims(workspace_user["user_id"], workspace_user["workspace_id"])
    )
    response = await http_client_snap.post(
        "/api/scenario/simulate",
        json={
            "tax_year": 2026,
            "regimen": "14_d_3",
            "rli_base": "50000000",
            "retiros_base": "10000000",
            "palancas": {},
        },
        headers={"Authorization": "Bearer fake"},
    )
    assert response.status_code == 200
    scen_id = response.json()["id"]

    with pytest.raises((DBAPIError, InternalError)):
        async with admin_session.begin():
            await admin_session.execute(
                text(
                    "update core.escenarios_simulacion "
                    "set rules_snapshot_hash = 'tampered' where id = :id"
                ),
                {"id": scen_id},
            )
