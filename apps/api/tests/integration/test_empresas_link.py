"""Tests del track empresas-link.

Validan que escenarios y recomendaciones se pueden asociar a una
empresa del workspace activo, y que un empresa_id de OTRO workspace
es rechazado por RLS / validación explícita (422).
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


def _override_jwt(claims: dict[str, Any]) -> Callable[[], dict[str, Any]]:
    def _dep() -> dict[str, Any]:
        return claims

    return _dep


@pytest_asyncio.fixture
async def http_client_link() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        yield client
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def two_workspaces_with_empresa(
    admin_session: AsyncSession,
) -> AsyncIterator[dict[str, UUID]]:
    """Workspace A con empresa E_A, workspace B con empresa E_B."""
    user_a = uuid4()
    user_b = uuid4()
    ws_a = uuid4()
    ws_b = uuid4()
    emp_a = uuid4()
    emp_b = uuid4()
    async with admin_session.begin():
        for uid in (user_a, user_b):
            await admin_session.execute(
                text(
                    "insert into auth.users (id, email) "
                    "values (:id, :e) on conflict (id) do nothing"
                ),
                {"id": str(uid), "e": f"link-{uid}@renteo.local"},
            )
        await admin_session.execute(
            text(
                "insert into core.workspaces (id, name, type) values "
                "(:a, 'Link A', 'pyme'), (:b, 'Link B', 'pyme')"
            ),
            {"a": str(ws_a), "b": str(ws_b)},
        )
        await admin_session.execute(
            text(
                "insert into core.workspace_members "
                "(workspace_id, user_id, role, accepted_at) values "
                "(:wa, :ua, 'owner', now()), "
                "(:wb, :ub, 'owner', now())"
            ),
            {
                "wa": str(ws_a),
                "ua": str(user_a),
                "wb": str(ws_b),
                "ub": str(user_b),
            },
        )
        await admin_session.execute(
            text(
                "insert into core.empresas "
                "(id, workspace_id, rut, razon_social) values "
                "(:ea, :wa, '11111111-1', 'Empresa A'), "
                "(:eb, :wb, '12345678-5', 'Empresa B')"
            ),
            {
                "ea": str(emp_a),
                "wa": str(ws_a),
                "eb": str(emp_b),
                "wb": str(ws_b),
            },
        )
    yield {
        "user_a": user_a,
        "user_b": user_b,
        "ws_a": ws_a,
        "ws_b": ws_b,
        "emp_a": emp_a,
        "emp_b": emp_b,
    }
    async with admin_session.begin():
        await admin_session.execute(
            text("set local session_replication_role = 'replica'")
        )
        await admin_session.execute(
            text(
                "delete from core.escenarios_simulacion "
                "where workspace_id in (:a, :b)"
            ),
            {"a": str(ws_a), "b": str(ws_b)},
        )
        await admin_session.execute(
            text(
                "delete from core.recomendaciones "
                "where workspace_id in (:a, :b)"
            ),
            {"a": str(ws_a), "b": str(ws_b)},
        )
        await admin_session.execute(
            text(
                "delete from core.empresas where id in (:ea, :eb)"
            ),
            {"ea": str(emp_a), "eb": str(emp_b)},
        )
        await admin_session.execute(
            text(
                "delete from core.workspaces where id in (:a, :b)"
            ),
            {"a": str(ws_a), "b": str(ws_b)},
        )
        await admin_session.execute(
            text(
                "delete from auth.users where id in (:ua, :ub)"
            ),
            {"ua": str(user_a), "ub": str(user_b)},
        )


@pytest.mark.integration
async def test_simulate_persists_empresa_id(
    http_client_link: AsyncClient,
    two_workspaces_with_empresa: dict[str, UUID],
) -> None:
    ctx = two_workspaces_with_empresa
    app.dependency_overrides[verify_jwt] = _override_jwt(
        _claims(ctx["user_a"], ctx["ws_a"])
    )

    response = await http_client_link.post(
        "/api/scenario/simulate",
        json={
            "regimen": "14_d_3",
            "tax_year": 2026,
            "rli_base": "30000000",
            "empresa_id": str(ctx["emp_a"]),
            "palancas": {},
        },
        headers={"Authorization": "Bearer fake"},
    )

    assert response.status_code == 200, response.text
    scenario_id = response.json()["id"]

    listed = await http_client_link.get(
        f"/api/scenario/list?empresa_id={ctx['emp_a']}",
        headers={"Authorization": "Bearer fake"},
    )
    items = listed.json()["scenarios"]
    nuevo = next(i for i in items if i["id"] == scenario_id)
    assert nuevo["empresa_id"] == str(ctx["emp_a"])


@pytest.mark.integration
async def test_simulate_rejects_empresa_de_otro_workspace(
    http_client_link: AsyncClient,
    two_workspaces_with_empresa: dict[str, UUID],
) -> None:
    """user_a no puede asociar un escenario a empresa del workspace B."""
    ctx = two_workspaces_with_empresa
    app.dependency_overrides[verify_jwt] = _override_jwt(
        _claims(ctx["user_a"], ctx["ws_a"])
    )

    response = await http_client_link.post(
        "/api/scenario/simulate",
        json={
            "regimen": "14_d_3",
            "tax_year": 2026,
            "rli_base": "30000000",
            "empresa_id": str(ctx["emp_b"]),
            "palancas": {},
        },
        headers={"Authorization": "Bearer fake"},
    )
    assert response.status_code == 422


@pytest.mark.integration
async def test_diagnose_persists_empresa_id(
    http_client_link: AsyncClient,
    two_workspaces_with_empresa: dict[str, UUID],
) -> None:
    ctx = two_workspaces_with_empresa
    app.dependency_overrides[verify_jwt] = _override_jwt(
        _claims(ctx["user_a"], ctx["ws_a"])
    )

    response = await http_client_link.post(
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
            "empresa_id": str(ctx["emp_a"]),
        },
        headers={"Authorization": "Bearer fake"},
    )
    assert response.status_code == 200, response.text
    rec_id = response.json()["id"]

    listed = await http_client_link.get(
        f"/api/regime/recomendaciones?empresa_id={ctx['emp_a']}",
        headers={"Authorization": "Bearer fake"},
    )
    items = listed.json()["recomendaciones"]
    nuevo = next(i for i in items if i["id"] == rec_id)
    assert nuevo["empresa_id"] == str(ctx["emp_a"])
