"""Golden cases del cálculo PPM PyME.

🟡 Marcados @pytest.mark.xfail hasta firma del contador.

Fundamento: Ley 21.210 (régimen PyME), Circular SII 53/2025
(transitoria 0,125% / 0,25% para 14 D N°3).
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.tax_engine.ppm import compute_ppm

XFAIL_REASON = (
    "awaiting CONTADOR_SOCIO signoff on PPM rates (ppm_pyme_rates seeds)"
)


@pytest.mark.golden
@pytest.mark.xfail(reason=XFAIL_REASON, strict=False)
async def test_ppm_14d3_at2026_tasa_baja(
    admin_session: AsyncSession,
) -> None:
    """14 D N°3 AT 2026, ingresos año anterior 30.000 UF (≤ 50.000).

    Tasa baja transitoria 0,125%. Ingresos del mes $10.000.000.
    PPM = $10.000.000 × 0,00125 = $12.500.
    """
    result = await compute_ppm(
        admin_session,
        regimen="14_d_3",
        tax_year=2026,
        ingresos_mes_pesos=Decimal("10000000"),
        ingresos_anio_anterior_uf=Decimal("30000"),
    )
    assert result == Decimal("12500.00")


@pytest.mark.golden
@pytest.mark.xfail(reason=XFAIL_REASON, strict=False)
async def test_ppm_14d3_at2026_tasa_alta(
    admin_session: AsyncSession,
) -> None:
    """14 D N°3 AT 2026, ingresos año anterior 70.000 UF (> 50.000).

    Tasa alta transitoria 0,25%. Ingresos del mes $10.000.000.
    PPM = $10.000.000 × 0,0025 = $25.000.
    """
    result = await compute_ppm(
        admin_session,
        regimen="14_d_3",
        tax_year=2026,
        ingresos_mes_pesos=Decimal("10000000"),
        ingresos_anio_anterior_uf=Decimal("70000"),
    )
    assert result == Decimal("25000.00")


@pytest.mark.golden
async def test_ppm_ingresos_mes_cero_retorna_cero(
    admin_session: AsyncSession,
) -> None:
    result = await compute_ppm(
        admin_session,
        regimen="14_d_3",
        tax_year=2026,
        ingresos_mes_pesos=Decimal("0"),
        ingresos_anio_anterior_uf=Decimal("30000"),
    )
    assert result == Decimal("0")
