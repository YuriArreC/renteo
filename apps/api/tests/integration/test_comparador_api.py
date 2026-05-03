"""Tests integration de POST /api/calc/comparador-regimen.

Verifican que el comparador devuelve los 4 escenarios (14_a, 14_d_3,
14_d_3_revertido, 14_d_8) con shape correcto, marca uno como
es_recomendado, y que el escenario revertido tiene tasa 25% efectiva.
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
async def http_client_comp() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.mark.integration
async def test_comparador_returns_four_scenarios(
    http_client_comp: AsyncClient,
) -> None:
    user_id = uuid4()
    app.dependency_overrides[verify_jwt] = lambda: _claims(user_id)

    response = await http_client_comp.post(
        "/api/calc/comparador-regimen",
        json={
            "tax_year": 2026,
            "rli": "30000000",
            "retiros_pesos": "15000000",
        },
        headers={"Authorization": "Bearer fake"},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["tax_year"] == 2026
    assert "PLACEHOLDER" in data["disclaimer"]

    regimens = [s["regimen"] for s in data["scenarios"]]
    assert regimens == ["14_a", "14_d_3", "14_d_3_revertido", "14_d_8"]


@pytest.mark.integration
async def test_comparador_marks_one_as_recomendado(
    http_client_comp: AsyncClient,
) -> None:
    user_id = uuid4()
    app.dependency_overrides[verify_jwt] = lambda: _claims(user_id)

    response = await http_client_comp.post(
        "/api/calc/comparador-regimen",
        json={
            "tax_year": 2026,
            "rli": "30000000",
            "retiros_pesos": "5000000",
        },
        headers={"Authorization": "Bearer fake"},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    recomendados = [s for s in data["scenarios"] if s["es_recomendado"]]
    assert len(recomendados) == 1


@pytest.mark.integration
async def test_comparador_14d3_revertido_uses_25pct(
    http_client_comp: AsyncClient,
) -> None:
    """RLI 100M con tasa revertida 25% → IDPC 25M exacto."""
    user_id = uuid4()
    app.dependency_overrides[verify_jwt] = lambda: _claims(user_id)

    response = await http_client_comp.post(
        "/api/calc/comparador-regimen",
        json={
            "tax_year": 2026,
            "rli": "100000000",
            "retiros_pesos": "0",
        },
        headers={"Authorization": "Bearer fake"},
    )

    data = response.json()
    revertido = next(
        s for s in data["scenarios"] if s["regimen"] == "14_d_3_revertido"
    )
    assert Decimal(revertido["idpc"]) == Decimal("25000000.00")
    assert revertido["es_transitoria"] is False


@pytest.mark.integration
async def test_comparador_14d8_idpc_zero_igc_sobre_rli(
    http_client_comp: AsyncClient,
) -> None:
    """14 D N°8 (transparente): IDPC=0 y IGC del dueño sobre RLI completa."""
    user_id = uuid4()
    app.dependency_overrides[verify_jwt] = lambda: _claims(user_id)

    response = await http_client_comp.post(
        "/api/calc/comparador-regimen",
        json={
            "tax_year": 2026,
            "rli": "30000000",
            "retiros_pesos": "5000000",
        },
        headers={"Authorization": "Bearer fake"},
    )

    data = response.json()
    transparente = next(
        s for s in data["scenarios"] if s["regimen"] == "14_d_8"
    )
    assert Decimal(transparente["idpc"]) == Decimal("0")
    # IGC en transparente NO depende de retiros; depende de RLI atribuida.
    # Distinto al IGC sobre 5M de retiros del 14 A.
    catorce_a = next(
        s for s in data["scenarios"] if s["regimen"] == "14_a"
    )
    assert transparente["igc_dueno"] != catorce_a["igc_dueno"]


@pytest.mark.integration
async def test_comparador_rejects_negative_rli(
    http_client_comp: AsyncClient,
) -> None:
    user_id = uuid4()
    app.dependency_overrides[verify_jwt] = lambda: _claims(user_id)

    response = await http_client_comp.post(
        "/api/calc/comparador-regimen",
        json={
            "tax_year": 2026,
            "rli": "-1000",
            "retiros_pesos": "0",
        },
        headers={"Authorization": "Bearer fake"},
    )
    assert response.status_code == 422
