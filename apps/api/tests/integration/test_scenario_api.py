"""Tests integration de los endpoints `/api/scenario/*`.

Cubren:
- POST /simulate: aplicación de palancas, validación, persistencia.
- GET /list: filtrado por workspace (RLS) y tax_year.
- POST /compare: hasta 4 escenarios, marca es_recomendado y plan de
  acción consolidado.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from decimal import Decimal
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
async def http_client_sim() -> AsyncIterator[AsyncClient]:
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
    """Crea un workspace y un usuario sin empresas asociadas."""
    user_id = uuid4()
    workspace_id = uuid4()

    async with admin_session.begin():
        await admin_session.execute(
            text(
                "insert into auth.users (id, email) values (:id, :email)"
            ),
            {"id": str(user_id), "email": f"sim-{user_id}@renteo.local"},
        )
        await admin_session.execute(
            text(
                "insert into core.workspaces (id, name, type) "
                "values (:id, 'Test Sim', 'pyme')"
            ),
            {"id": str(workspace_id)},
        )
        await admin_session.execute(
            text(
                "insert into core.workspace_members "
                "(workspace_id, user_id, role, accepted_at) "
                "values (:ws, :uid, 'owner', now())"
            ),
            {"ws": str(workspace_id), "uid": str(user_id)},
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
# POST /simulate
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_simulate_no_palancas_persists_with_zero_ahorro(
    http_client_sim: AsyncClient, workspace_ctx: dict[str, UUID]
) -> None:
    app.dependency_overrides[verify_jwt] = _override_jwt(
        _claims(workspace_ctx["user_id"], workspace_ctx["workspace_id"])
    )

    response = await http_client_sim.post(
        "/api/scenario/simulate",
        json={
            "regimen": "14_d_3",
            "tax_year": 2026,
            "rli_base": "30000000",
            "retiros_base": "5000000",
            "palancas": {},
        },
        headers={"Authorization": "Bearer fake"},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert "id" in data
    assert UUID(data["id"])
    assert Decimal(data["base"]["carga_total"]) == Decimal(
        data["simulado"]["carga_total"]
    )
    assert Decimal(data["ahorro_total"]) == Decimal("0")
    assert data["banderas"] == []
    aplicadas = {p["palanca_id"] for p in data["palancas_aplicadas"]}
    assert aplicadas == {
        "dep_instantanea",
        "sence",
        "rebaja_14e",
        "retiros_adicionales",
        "sueldo_empresarial",
        "credito_id",
        "apv",
        "depreciacion_acelerada",
        "credito_reinversion",
        "ppm_extraordinario",
        "postergacion_iva",
        "cambio_regimen",
    }


@pytest.mark.integration
async def test_simulate_dep_instantanea_reduces_rli(
    http_client_sim: AsyncClient, workspace_ctx: dict[str, UUID]
) -> None:
    app.dependency_overrides[verify_jwt] = _override_jwt(
        _claims(workspace_ctx["user_id"], workspace_ctx["workspace_id"])
    )

    response = await http_client_sim.post(
        "/api/scenario/simulate",
        json={
            "regimen": "14_d_3",
            "tax_year": 2026,
            "rli_base": "30000000",
            "retiros_base": "0",
            "palancas": {"dep_instantanea": "10000000"},
        },
        headers={"Authorization": "Bearer fake"},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert Decimal(data["simulado"]["rli"]) == Decimal("20000000")
    assert Decimal(data["ahorro_total"]) > Decimal("0")


@pytest.mark.integration
async def test_simulate_p1_blocked_for_14a(
    http_client_sim: AsyncClient, workspace_ctx: dict[str, UUID]
) -> None:
    app.dependency_overrides[verify_jwt] = _override_jwt(
        _claims(workspace_ctx["user_id"], workspace_ctx["workspace_id"])
    )

    response = await http_client_sim.post(
        "/api/scenario/simulate",
        json={
            "regimen": "14_a",
            "tax_year": 2026,
            "rli_base": "30000000",
            "palancas": {"dep_instantanea": "5000000"},
        },
        headers={"Authorization": "Bearer fake"},
    )

    assert response.status_code == 422
    assert "31 N°5 bis" in response.json()["detail"]


@pytest.mark.integration
async def test_simulate_p3_only_in_14d3(
    http_client_sim: AsyncClient, workspace_ctx: dict[str, UUID]
) -> None:
    app.dependency_overrides[verify_jwt] = _override_jwt(
        _claims(workspace_ctx["user_id"], workspace_ctx["workspace_id"])
    )

    response = await http_client_sim.post(
        "/api/scenario/simulate",
        json={
            "regimen": "14_d_8",
            "tax_year": 2026,
            "rli_base": "30000000",
            "palancas": {"rebaja_14e_pct": "0.30"},
        },
        headers={"Authorization": "Bearer fake"},
    )

    assert response.status_code == 422
    assert "14 E" in response.json()["detail"]


@pytest.mark.integration
async def test_simulate_sence_credits_idpc(
    http_client_sim: AsyncClient, workspace_ctx: dict[str, UUID]
) -> None:
    """SENCE crea crédito directo contra IDPC sin alterar la RLI."""
    app.dependency_overrides[verify_jwt] = _override_jwt(
        _claims(workspace_ctx["user_id"], workspace_ctx["workspace_id"])
    )

    response = await http_client_sim.post(
        "/api/scenario/simulate",
        json={
            "regimen": "14_d_3",
            "tax_year": 2026,
            "rli_base": "30000000",
            "planilla_anual_pesos": "100000000",
            "palancas": {"sence_monto": "500000"},
        },
        headers={"Authorization": "Bearer fake"},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    # RLI no cambia: SENCE no es deducción.
    assert Decimal(data["simulado"]["rli"]) == Decimal(
        data["base"]["rli"]
    )
    # IDPC sí: el crédito reduce IDPC bruto.
    assert Decimal(data["simulado"]["idpc"]) < Decimal(
        data["base"]["idpc"]
    )
    sence = next(
        p
        for p in data["palancas_aplicadas"]
        if p["palanca_id"] == "sence"
    )
    # 1% de planilla 100M = 1M; tope 9 UTM 70.000 = 630.000; max(1M, 630k) = 1M.
    # Monto pedido 500k <= 1M → todo se imputa.
    assert Decimal(sence["monto_aplicado"]) == Decimal("500000")


@pytest.mark.integration
async def test_simulate_credito_id_combines_credit_and_gasto(
    http_client_sim: AsyncClient, workspace_ctx: dict[str, UUID]
) -> None:
    """P6: 35% crédito IDPC + 65% gasto que baja RLI."""
    app.dependency_overrides[verify_jwt] = _override_jwt(
        _claims(workspace_ctx["user_id"], workspace_ctx["workspace_id"])
    )

    response = await http_client_sim.post(
        "/api/scenario/simulate",
        json={
            "regimen": "14_d_3",
            "tax_year": 2026,
            "rli_base": "30000000",
            "palancas": {"credito_id_monto": "10000000"},
        },
        headers={"Authorization": "Bearer fake"},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    # 65% de 10M = 6,5M de gasto deducible → RLI 23,5M.
    assert Decimal(data["simulado"]["rli"]) == Decimal("23500000")
    assert Decimal(data["ahorro_total"]) > Decimal("0")


@pytest.mark.integration
async def test_simulate_apv_reduces_igc_base(
    http_client_sim: AsyncClient, workspace_ctx: dict[str, UUID]
) -> None:
    """P9 APV reduce la base IGC del dueño."""
    app.dependency_overrides[verify_jwt] = _override_jwt(
        _claims(workspace_ctx["user_id"], workspace_ctx["workspace_id"])
    )

    response = await http_client_sim.post(
        "/api/scenario/simulate",
        json={
            "regimen": "14_a",
            "tax_year": 2026,
            "rli_base": "50000000",
            "retiros_base": "30000000",
            "palancas": {"apv_monto": "5000000"},
        },
        headers={"Authorization": "Bearer fake"},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    # IGC simulado debe ser menor (la base se redujo en 5M).
    assert Decimal(data["simulado"]["igc_dueno"]) <= Decimal(
        data["base"]["igc_dueno"]
    )


@pytest.mark.integration
async def test_simulate_apv_warns_when_above_tope(
    http_client_sim: AsyncClient, workspace_ctx: dict[str, UUID]
) -> None:
    """Aporte APV sobre 600 UF placeholder dispara warning."""
    app.dependency_overrides[verify_jwt] = _override_jwt(
        _claims(workspace_ctx["user_id"], workspace_ctx["workspace_id"])
    )

    response = await http_client_sim.post(
        "/api/scenario/simulate",
        json={
            "regimen": "14_a",
            "tax_year": 2026,
            "rli_base": "100000000",
            "retiros_base": "10000000",
            "palancas": {"apv_monto": "100000000"},
        },
        headers={"Authorization": "Bearer fake"},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    palancas_banderas = [b["palanca_id"] for b in data["banderas"]]
    assert "apv" in palancas_banderas


@pytest.mark.integration
async def test_simulate_requires_tenancy(
    http_client_sim: AsyncClient,
) -> None:
    """Sin workspace en JWT, simulate retorna 403 (no 401)."""
    user_id = uuid4()
    app.dependency_overrides[verify_jwt] = _override_jwt(
        {
            "sub": str(user_id),
            "aud": "authenticated",
            "role": "authenticated",
            "app_metadata": {"provider": "email"},
        }
    )

    response = await http_client_sim.post(
        "/api/scenario/simulate",
        json={
            "regimen": "14_d_3",
            "tax_year": 2026,
            "rli_base": "30000000",
            "palancas": {},
        },
        headers={"Authorization": "Bearer fake"},
    )

    assert response.status_code == 403


# ---------------------------------------------------------------------------
# GET /list
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_list_returns_only_workspace_scenarios(
    http_client_sim: AsyncClient, workspace_ctx: dict[str, UUID]
) -> None:
    app.dependency_overrides[verify_jwt] = _override_jwt(
        _claims(workspace_ctx["user_id"], workspace_ctx["workspace_id"])
    )

    # Crear 2 escenarios distintos.
    for dep in ("0", "5000000"):
        r = await http_client_sim.post(
            "/api/scenario/simulate",
            json={
                "regimen": "14_d_3",
                "tax_year": 2026,
                "rli_base": "30000000",
                "palancas": ({} if dep == "0" else {"dep_instantanea": dep}),
            },
            headers={"Authorization": "Bearer fake"},
        )
        assert r.status_code == 200, r.text

    response = await http_client_sim.get(
        "/api/scenario/list",
        headers={"Authorization": "Bearer fake"},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert len(data["scenarios"]) == 2
    # El de menor carga_simulada queda recomendado.
    recomendados = [s for s in data["scenarios"] if s["es_recomendado"]]
    assert len(recomendados) == 1


@pytest.mark.integration
async def test_list_filters_by_tax_year(
    http_client_sim: AsyncClient, workspace_ctx: dict[str, UUID]
) -> None:
    app.dependency_overrides[verify_jwt] = _override_jwt(
        _claims(workspace_ctx["user_id"], workspace_ctx["workspace_id"])
    )

    for year in (2025, 2026):
        r = await http_client_sim.post(
            "/api/scenario/simulate",
            json={
                "regimen": "14_d_3",
                "tax_year": year,
                "rli_base": "10000000",
                "palancas": {},
            },
            headers={"Authorization": "Bearer fake"},
        )
        assert r.status_code == 200, r.text

    response = await http_client_sim.get(
        "/api/scenario/list?tax_year=2025",
        headers={"Authorization": "Bearer fake"},
    )
    data = response.json()
    years = {s["tax_year"] for s in data["scenarios"]}
    assert years == {2025}


# ---------------------------------------------------------------------------
# POST /compare
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_compare_marks_lowest_carga_as_recomendado(
    http_client_sim: AsyncClient, workspace_ctx: dict[str, UUID]
) -> None:
    app.dependency_overrides[verify_jwt] = _override_jwt(
        _claims(workspace_ctx["user_id"], workspace_ctx["workspace_id"])
    )

    ids: list[str] = []
    # Escenario "alto": sin palancas → carga simulada = base.
    # Escenario "bajo": con depreciación → carga simulada menor.
    payloads: list[dict[str, Any]] = [
        {"regimen": "14_d_3", "tax_year": 2026, "rli_base": "30000000",
         "palancas": {}},
        {"regimen": "14_d_3", "tax_year": 2026, "rli_base": "30000000",
         "palancas": {"dep_instantanea": "10000000"}},
    ]
    for body in payloads:
        r = await http_client_sim.post(
            "/api/scenario/simulate",
            json=body,
            headers={"Authorization": "Bearer fake"},
        )
        assert r.status_code == 200, r.text
        ids.append(r.json()["id"])

    response = await http_client_sim.post(
        "/api/scenario/compare",
        json={"ids": ids},
        headers={"Authorization": "Bearer fake"},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert len(data["scenarios"]) == 2
    recomendado = next(s for s in data["scenarios"] if s["es_recomendado"])
    other = next(s for s in data["scenarios"] if not s["es_recomendado"])
    assert Decimal(recomendado["simulado"]["carga_total"]) <= Decimal(
        other["simulado"]["carga_total"]
    )
    # El plan de acción del recomendado incluye dep_instantanea.
    plan_ids = {p["palanca_id"] for p in data["plan_accion"]}
    assert "dep_instantanea" in plan_ids


@pytest.mark.integration
async def test_compare_rejects_more_than_four(
    http_client_sim: AsyncClient, workspace_ctx: dict[str, UUID]
) -> None:
    app.dependency_overrides[verify_jwt] = _override_jwt(
        _claims(workspace_ctx["user_id"], workspace_ctx["workspace_id"])
    )

    response = await http_client_sim.post(
        "/api/scenario/compare",
        json={"ids": [str(uuid4()) for _ in range(5)]},
        headers={"Authorization": "Bearer fake"},
    )
    assert response.status_code == 422


@pytest.mark.integration
async def test_compare_404_on_unknown_id(
    http_client_sim: AsyncClient, workspace_ctx: dict[str, UUID]
) -> None:
    app.dependency_overrides[verify_jwt] = _override_jwt(
        _claims(workspace_ctx["user_id"], workspace_ctx["workspace_id"])
    )

    response = await http_client_sim.post(
        "/api/scenario/compare",
        json={"ids": [str(uuid4())]},
        headers={"Authorization": "Bearer fake"},
    )
    assert response.status_code == 404
