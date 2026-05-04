"""Tests integration de GET /api/cartera (skill 9, cliente B)."""

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
    role: str = "accountant_lead",
    workspace_type: str = "accounting_firm",
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


def _override(claims: dict[str, Any]) -> Callable[[], dict[str, Any]]:
    def _dep() -> dict[str, Any]:
        return claims

    return _dep


@pytest_asyncio.fixture
async def http_client_cartera() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        yield client
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def cartera_with_three_empresas(
    admin_session: AsyncSession,
) -> AsyncIterator[dict[str, UUID]]:
    """Workspace con 3 empresas en distintos estados:
      - emp_a: con alerta abierta + sin diagnóstico (score esperado alto)
      - emp_b: sin alertas + con diagnóstico (score 0)
      - emp_c: sin alertas + sin diagnóstico (score 25)
    """
    user_id = uuid4()
    workspace_id = uuid4()
    emp_a, emp_b, emp_c = uuid4(), uuid4(), uuid4()
    async with admin_session.begin():
        await admin_session.execute(
            text("insert into auth.users (id, email) values (:id, :e)"),
            {"id": str(user_id), "e": f"cartera-{user_id}@renteo.local"},
        )
        await admin_session.execute(
            text(
                "insert into core.workspaces (id, name, type) "
                "values (:id, 'Estudio', 'accounting_firm')"
            ),
            {"id": str(workspace_id)},
        )
        await admin_session.execute(
            text(
                "insert into core.workspace_members "
                "(workspace_id, user_id, role, accepted_at) "
                "values (:ws, :u, 'accountant_lead', now())"
            ),
            {"ws": str(workspace_id), "u": str(user_id)},
        )
        await admin_session.execute(
            text(
                "insert into core.empresas "
                "(id, workspace_id, rut, razon_social, regimen_actual)"
                " values "
                "(:a, :ws, '11111111-1', 'Empresa A', '14_d_3'), "
                "(:b, :ws, '12345678-5', 'Empresa B', '14_a'), "
                "(:c, :ws, '20000000-0', 'Empresa C', '14_d_8')"
            ),
            {
                "ws": str(workspace_id),
                "a": str(emp_a),
                "b": str(emp_b),
                "c": str(emp_c),
            },
        )
        # Empresa A: alerta nueva.
        await admin_session.execute(
            text(
                "insert into core.alertas "
                "(workspace_id, empresa_id, tipo, severidad, titulo, "
                " descripcion) values "
                "(:ws, :emp, 'rebaja_14e_disponible', 'warning', "
                " 't', 'd')"
            ),
            {"ws": str(workspace_id), "emp": str(emp_a)},
        )
        # Empresa B: recomendación cambio_regimen.
        await admin_session.execute(
            text(
                """
                insert into core.recomendaciones (
                    workspace_id, empresa_id, tax_year, tipo,
                    descripcion, fundamento_legal, ahorro_estimado_clp,
                    disclaimer_version, engine_version,
                    inputs_snapshot, outputs,
                    rule_set_snapshot, tax_year_params_snapshot,
                    rules_snapshot_hash
                ) values (
                    :ws, :emp, 2026, 'cambio_regimen',
                    'desc', '[]'::jsonb, 1000000.00,
                    'v1', 'tt',
                    '{}'::jsonb,
                    cast(:out as jsonb),
                    '{}'::jsonb, '{}'::jsonb,
                    'h'
                )
                """
            ),
            {
                "ws": str(workspace_id),
                "emp": str(emp_b),
                "out": '{"veredicto": {"regimen_recomendado": "14_d_3"}}',
            },
        )
    yield {
        "user_id": user_id,
        "workspace_id": workspace_id,
        "emp_a": emp_a,
        "emp_b": emp_b,
        "emp_c": emp_c,
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
            text("delete from core.recomendaciones where workspace_id = :w"),
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
async def test_cartera_returns_three_empresas_sorted_by_score(
    http_client_cartera: AsyncClient,
    cartera_with_three_empresas: dict[str, UUID],
) -> None:
    ctx = cartera_with_three_empresas
    app.dependency_overrides[verify_jwt] = _override(
        _claims(ctx["user_id"], ctx["workspace_id"])
    )

    response = await http_client_cartera.get(
        "/api/cartera",
        headers={"Authorization": "Bearer fake"},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["total_empresas"] == 3
    assert data["total_alertas_abiertas"] == 1
    by_id = {UUID(e["empresa_id"]): e for e in data["empresas"]}

    # Empresa A: 1 alerta + sin diagnóstico → 25 + 25 = 50.
    assert by_id[ctx["emp_a"]]["score_oportunidad"] == 50
    assert by_id[ctx["emp_a"]]["alertas_abiertas"] == 1

    # Empresa B: sin alertas + con diagnóstico → 0.
    assert by_id[ctx["emp_b"]]["score_oportunidad"] == 0
    assert by_id[ctx["emp_b"]]["ultima_recomendacion"] is not None
    assert (
        by_id[ctx["emp_b"]]["ultima_recomendacion"]["regimen_recomendado"]
        == "14_d_3"
    )

    # Empresa C: sin alertas + sin diagnóstico → 25.
    assert by_id[ctx["emp_c"]]["score_oportunidad"] == 25

    # Ordenadas por score desc.
    scores = [e["score_oportunidad"] for e in data["empresas"]]
    assert scores == sorted(scores, reverse=True)


@pytest.mark.integration
async def test_cartera_requires_tenancy(
    http_client_cartera: AsyncClient,
) -> None:
    user_id = uuid4()
    app.dependency_overrides[verify_jwt] = _override(
        {
            "sub": str(user_id),
            "aud": "authenticated",
            "role": "authenticated",
            "app_metadata": {"provider": "email"},
        }
    )

    response = await http_client_cartera.get(
        "/api/cartera",
        headers={"Authorization": "Bearer fake"},
    )
    assert response.status_code == 403
