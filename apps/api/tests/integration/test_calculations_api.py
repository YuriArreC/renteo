"""Tests integration de POST /api/calc/{idpc,igc,ppm}.

Verifican que los endpoints aceptan input válido, devuelven shape
correcto con disclaimer placeholder, y rechazan input inválido.
Los valores numéricos vienen de los seeds placeholder, así que NO
se assertean montos exactos (eso lo cubren los tests golden).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
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
async def http_client_calc() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.mark.integration
async def test_calc_idpc_returns_value_and_disclaimer(
    http_client_calc: AsyncClient,
) -> None:
    user_id = uuid4()
    app.dependency_overrides[verify_jwt] = lambda: _claims(user_id)

    response = await http_client_calc.post(
        "/api/calc/idpc",
        json={"regimen": "14_a", "tax_year": 2026, "rli": "50000000"},
        headers={"Authorization": "Bearer fake"},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert "value" in data
    assert data["currency"] == "CLP"
    assert data["tax_year"] == 2026
    assert "PLACEHOLDER" in data["disclaimer"]
    assert "PLACEHOLDER" in data["fuente_legal"]
    # 14 A 2026 → 27% * 50.000.000 = 13.500.000.
    assert float(data["value"]) == 13500000.0


@pytest.mark.integration
async def test_calc_igc_uses_brackets(
    http_client_calc: AsyncClient,
) -> None:
    user_id = uuid4()
    app.dependency_overrides[verify_jwt] = lambda: _claims(user_id)

    response = await http_client_calc.post(
        "/api/calc/igc",
        json={"tax_year": 2026, "base_pesos": "8345040"},
        headers={"Authorization": "Bearer fake"},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    # Base 10 UTA (con UTA placeholder $834.504) → tramo 1 exento.
    assert float(data["value"]) == 0.0


@pytest.mark.integration
async def test_calc_ppm_pyme_tasa_baja(
    http_client_calc: AsyncClient,
) -> None:
    user_id = uuid4()
    app.dependency_overrides[verify_jwt] = lambda: _claims(user_id)

    response = await http_client_calc.post(
        "/api/calc/ppm",
        json={
            "regimen": "14_d_3",
            "tax_year": 2026,
            "ingresos_mes_pesos": "10000000",
            "ingresos_anio_anterior_uf": "30000",
        },
        headers={"Authorization": "Bearer fake"},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    # 30.000 UF <= 50.000 → tasa 0.125% * $10.000.000 = $12.500.
    assert float(data["value"]) == 12500.0


@pytest.mark.integration
async def test_calc_idpc_rejects_invalid_regimen(
    http_client_calc: AsyncClient,
) -> None:
    user_id = uuid4()
    app.dependency_overrides[verify_jwt] = lambda: _claims(user_id)

    response = await http_client_calc.post(
        "/api/calc/idpc",
        json={"regimen": "invalid", "tax_year": 2026, "rli": "1000000"},
        headers={"Authorization": "Bearer fake"},
    )
    assert response.status_code == 422


@pytest.mark.integration
async def test_calc_idpc_rejects_year_out_of_range(
    http_client_calc: AsyncClient,
) -> None:
    user_id = uuid4()
    app.dependency_overrides[verify_jwt] = lambda: _claims(user_id)

    response = await http_client_calc.post(
        "/api/calc/idpc",
        json={"regimen": "14_a", "tax_year": 1999, "rli": "1000000"},
        headers={"Authorization": "Bearer fake"},
    )
    assert response.status_code == 422


@pytest.mark.integration
async def test_calc_requires_auth(http_client_calc: AsyncClient) -> None:
    # Garantizar que ningún override de tests previos se filtre acá.
    app.dependency_overrides.pop(verify_jwt, None)
    # Sin Authorization header → 401 o 403 (HTTPBearer auto_error=True
    # devuelve 401 en versiones recientes de FastAPI; aceptamos ambos
    # para ser robusto a cambios upstream).
    response = await http_client_calc.post(
        "/api/calc/idpc",
        json={"regimen": "14_a", "tax_year": 2026, "rli": "1000000"},
    )
    assert response.status_code in (401, 403), response.text
