"""Tests integration de POST /api/scenario/simulate.

Cubren flujo MVP de skill 8: 4 palancas (P1, P3, P4, P5), validación
de elegibilidad y banderas rojas. Los montos exactos vienen de los
seeds placeholder; los tests validan shape, deltas relativos y
comportamiento de las banderas, no valores absolutos firmados.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from src.auth.jwt import verify_jwt
from src.main import app


def _claims(user_id: UUID) -> dict[str, Any]:
    return {
        "sub": str(user_id),
        "aud": "authenticated",
        "role": "authenticated",
        "app_metadata": {"provider": "email"},
    }


@pytest_asyncio.fixture
async def http_client_sim() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.mark.integration
async def test_simulate_no_palancas_matches_base(
    http_client_sim: AsyncClient,
) -> None:
    """Sin palancas activas, el escenario simulado iguala al base."""
    user_id = uuid4()
    app.dependency_overrides[verify_jwt] = lambda: _claims(user_id)

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
    assert Decimal(data["base"]["carga_total"]) == Decimal(
        data["simulado"]["carga_total"]
    )
    assert Decimal(data["ahorro_total"]) == Decimal("0")
    assert data["banderas"] == []
    # Las 4 palancas siempre vienen reportadas con aplicada=False.
    aplicadas = {p["palanca_id"] for p in data["palancas_aplicadas"]}
    assert aplicadas == {
        "dep_instantanea",
        "rebaja_14e",
        "retiros_adicionales",
        "sueldo_empresarial",
    }
    assert all(not p["aplicada"] for p in data["palancas_aplicadas"])


@pytest.mark.integration
async def test_simulate_dep_instantanea_reduces_rli_and_idpc(
    http_client_sim: AsyncClient,
) -> None:
    user_id = uuid4()
    app.dependency_overrides[verify_jwt] = lambda: _claims(user_id)

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
    assert Decimal(data["simulado"]["idpc"]) < Decimal(data["base"]["idpc"])
    assert Decimal(data["ahorro_total"]) > Decimal("0")
    p1 = next(
        p
        for p in data["palancas_aplicadas"]
        if p["palanca_id"] == "dep_instantanea"
    )
    assert p1["aplicada"] is True
    assert "31 N°5 bis" in p1["fuente_legal"]


@pytest.mark.integration
async def test_simulate_p1_blocked_for_14a(
    http_client_sim: AsyncClient,
) -> None:
    """P1 (depreciación instantánea) no es elegible en 14 A → 422."""
    user_id = uuid4()
    app.dependency_overrides[verify_jwt] = lambda: _claims(user_id)

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
    http_client_sim: AsyncClient,
) -> None:
    """P3 (rebaja 14 E) bloqueada en 14 D N°8."""
    user_id = uuid4()
    app.dependency_overrides[verify_jwt] = lambda: _claims(user_id)

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
async def test_simulate_p3_caps_at_50pct(
    http_client_sim: AsyncClient,
) -> None:
    """Pedir 80% se trunca a 50% efectivo."""
    user_id = uuid4()
    app.dependency_overrides[verify_jwt] = lambda: _claims(user_id)

    response = await http_client_sim.post(
        "/api/scenario/simulate",
        json={
            "regimen": "14_d_3",
            "tax_year": 2026,
            "rli_base": "10000000",
            "palancas": {"rebaja_14e_pct": "0.80"},
        },
        headers={"Authorization": "Bearer fake"},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    p3 = next(
        p
        for p in data["palancas_aplicadas"]
        if p["palanca_id"] == "rebaja_14e"
    )
    # 50% de 10M = 5M (bajo el tope absoluto de 5.000 UF placeholder).
    assert Decimal(p3["monto_aplicado"]) == Decimal("5000000")


@pytest.mark.integration
async def test_simulate_p4_increases_igc_and_carga(
    http_client_sim: AsyncClient,
) -> None:
    user_id = uuid4()
    app.dependency_overrides[verify_jwt] = lambda: _claims(user_id)

    response = await http_client_sim.post(
        "/api/scenario/simulate",
        json={
            "regimen": "14_a",
            "tax_year": 2026,
            "rli_base": "50000000",
            "retiros_base": "5000000",
            "palancas": {"retiros_adicionales": "20000000"},
        },
        headers={"Authorization": "Bearer fake"},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert Decimal(data["simulado"]["retiros_total"]) == Decimal("25000000")
    assert Decimal(data["simulado"]["igc_dueno"]) > Decimal(
        data["base"]["igc_dueno"]
    )


@pytest.mark.integration
async def test_simulate_p5_warns_when_above_tope(
    http_client_sim: AsyncClient,
) -> None:
    """Sueldo mensual sobre 250 UF placeholder dispara bandera warning."""
    user_id = uuid4()
    app.dependency_overrides[verify_jwt] = lambda: _claims(user_id)

    response = await http_client_sim.post(
        "/api/scenario/simulate",
        json={
            "regimen": "14_d_3",
            "tax_year": 2026,
            "rli_base": "300000000",
            "palancas": {"sueldo_empresarial_mensual": "20000000"},
        },
        headers={"Authorization": "Bearer fake"},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    severities = [b["severidad"] for b in data["banderas"]]
    palancas = [b["palanca_id"] for b in data["banderas"]]
    assert "warning" in severities
    assert "sueldo_empresarial" in palancas


@pytest.mark.integration
async def test_simulate_requires_auth(http_client_sim: AsyncClient) -> None:
    app.dependency_overrides.pop(verify_jwt, None)
    response = await http_client_sim.post(
        "/api/scenario/simulate",
        json={
            "regimen": "14_d_3",
            "tax_year": 2026,
            "rli_base": "30000000",
            "palancas": {},
        },
    )
    assert response.status_code in (401, 403), response.text
