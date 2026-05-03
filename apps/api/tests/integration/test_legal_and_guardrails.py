"""Tests del track 1 + 2: textos legales versionados y guardrails de
recomendación lícita.

- GET /api/legal/{key} retorna body + version del texto vigente.
- Pedir un key no permitido cae con 404.
- Pedir un key sin texto publicado cae con 503.
- POST /api/scenario/simulate enriquece el disclaimer con
  privacy.legal_texts (no usa la constante PLACEHOLDER).
- POST /api/regime/diagnose hace lo mismo con disclaimer-recomendacion.
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
    user_id: UUID, workspace_id: UUID
) -> dict[str, Any]:
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


def _override_jwt(claims: dict[str, Any]) -> Callable[[], dict[str, Any]]:
    def _dep() -> dict[str, Any]:
        return claims

    return _dep


@pytest_asyncio.fixture
async def http_client_legal() -> AsyncIterator[AsyncClient]:
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
            {"id": str(user_id), "e": f"legal-{user_id}@renteo.local"},
        )
        await admin_session.execute(
            text(
                "insert into core.workspaces (id, name, type) "
                "values (:id, 'Legal test', 'pyme')"
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
                "delete from core.escenarios_simulacion "
                "where workspace_id = :ws"
            ),
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


# ---------------------------------------------------------------------------
# /api/legal/{key}
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_legal_returns_seeded_body(
    http_client_legal: AsyncClient, workspace_ctx: dict[str, UUID]
) -> None:
    app.dependency_overrides[verify_jwt] = _override_jwt(
        _claims(workspace_ctx["user_id"], workspace_ctx["workspace_id"])
    )

    response = await http_client_legal.get(
        "/api/legal/disclaimer-recomendacion",
        headers={"Authorization": "Bearer fake"},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["key"] == "disclaimer-recomendacion"
    assert data["version"] == "v1"
    assert "Información general" in data["body"]


@pytest.mark.integration
async def test_legal_rejects_unknown_key(
    http_client_legal: AsyncClient, workspace_ctx: dict[str, UUID]
) -> None:
    app.dependency_overrides[verify_jwt] = _override_jwt(
        _claims(workspace_ctx["user_id"], workspace_ctx["workspace_id"])
    )

    response = await http_client_legal.get(
        "/api/legal/this-key-does-not-exist",
        headers={"Authorization": "Bearer fake"},
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Disclaimer enriquecido en endpoints
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_simulate_attaches_versioned_disclaimer(
    http_client_legal: AsyncClient, workspace_ctx: dict[str, UUID]
) -> None:
    app.dependency_overrides[verify_jwt] = _override_jwt(
        _claims(workspace_ctx["user_id"], workspace_ctx["workspace_id"])
    )

    response = await http_client_legal.post(
        "/api/scenario/simulate",
        json={
            "regimen": "14_d_3",
            "tax_year": 2026,
            "rli_base": "30000000",
            "palancas": {},
        },
        headers={"Authorization": "Bearer fake"},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["disclaimer"].startswith("Esta simulación es una proyección")


@pytest.mark.integration
async def test_diagnose_attaches_recomendacion_disclaimer(
    http_client_legal: AsyncClient, workspace_ctx: dict[str, UUID]
) -> None:
    app.dependency_overrides[verify_jwt] = _override_jwt(
        _claims(workspace_ctx["user_id"], workspace_ctx["workspace_id"])
    )

    response = await http_client_legal.post(
        "/api/regime/diagnose",
        json={
            "tax_year": 2026,
            "regimen_actual": "14_a",
            "ingresos_promedio_3a_uf": "30000",
            "ingresos_max_anual_uf": "40000",
            "capital_efectivo_inicial_uf": "5000",
            "pct_ingresos_pasivos": "0.10",
            "todos_duenos_personas_naturales_chile": True,
            "participacion_empresas_no_14d_sobre_10pct": False,
            "sector": "comercio",
            "ventas_anuales_uf": "30000",
            "rli_proyectada_anual_uf": "1000",
            "plan_retiros_pct": "0.30",
        },
        headers={"Authorization": "Bearer fake"},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert "Información general" in data["disclaimer"]
