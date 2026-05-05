"""Golden cases del cálculo IGC.

🟡 Marcados @pytest.mark.xfail hasta que el contador socio firme los
tramos IGC AT 2024-2028 (TODOS-CONTADOR.md ítem #2).

Los casos asumen UTA dic 2025 ≈ $834.504 (placeholder de la migración).
Cuando el contador firme la UTA real para cada AT, los valores esperados
pueden cambiar; actualizar entonces las assertions.

Fundamento de la tabla IGC: art. 52 LIR (8 tramos en UTA, tasas
marginales con cantidad a rebajar). Crédito 5% último tramo: art. 56
LIR (NO se aplica en compute_igc; eso es un crédito posterior contra
el IDPC determinado del dueño).
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.tax_engine.igc import compute_igc
from tests.golden import GOLDENS_STRICT

XFAIL_REASON = (
    "awaiting CONTADOR_SOCIO signoff on TODOS-CONTADOR.md #2 (igc_brackets) "
    "and #3 (uta_pesos_dic)"
)


@pytest.mark.golden
@pytest.mark.xfail(reason=XFAIL_REASON, strict=GOLDENS_STRICT)
async def test_igc_at2026_tramo_exento(
    admin_session: AsyncSession,
) -> None:
    """Base 10 UTA → tramo 1 (exento).

    UTA dic 2025 placeholder = $834.504.
    Base = 10 * 834.504 = $8.345.040.
    Tramo 1 (0-13.5 UTA): tasa 0%. IGC = 0.
    """
    base = Decimal("8345040")
    result = await compute_igc(admin_session, tax_year=2026, base_pesos=base)
    assert result == Decimal("0")


@pytest.mark.golden
@pytest.mark.xfail(reason=XFAIL_REASON, strict=GOLDENS_STRICT)
async def test_igc_at2026_tramo_3(
    admin_session: AsyncSession,
) -> None:
    """Base 40 UTA → tramo 3 (8%, rebajar 1.74 UTA).

    Base = 40 * $834.504 = $33.380.160.
    impuesto_uta = 40 * 0.08 - 1.74 = 3.20 - 1.74 = 1.46 UTA.
    impuesto_pesos = 1.46 * 834.504 = $1.218.375,84.
    """
    base = Decimal("33380160")
    expected = Decimal("1218375.84")
    result = await compute_igc(admin_session, tax_year=2026, base_pesos=base)
    assert result == expected


@pytest.mark.golden
@pytest.mark.xfail(reason=XFAIL_REASON, strict=GOLDENS_STRICT)
async def test_igc_at2026_tramo_8_alto(
    admin_session: AsyncSession,
) -> None:
    """Base 400 UTA → tramo 8 (40%, rebajar 38.82 UTA).

    Base = 400 * $834.504 = $333.801.600.
    impuesto_uta = 400 * 0.40 - 38.82 = 160 - 38.82 = 121.18 UTA.
    impuesto_pesos = 121.18 * 834.504 = $101.123.394,72.
    """
    base = Decimal("333801600")
    expected = Decimal("101123394.72")
    result = await compute_igc(admin_session, tax_year=2026, base_pesos=base)
    assert result == expected


# ---------------------------------------------------------------------------
# Edge cases del motor (no requieren firma)
# ---------------------------------------------------------------------------


@pytest.mark.golden
async def test_igc_base_cero_o_negativa_retorna_cero(
    admin_session: AsyncSession,
) -> None:
    assert (
        await compute_igc(admin_session, tax_year=2026, base_pesos=Decimal("0"))
        == Decimal("0")
    )
    assert (
        await compute_igc(
            admin_session, tax_year=2026, base_pesos=Decimal("-1000")
        )
        == Decimal("0")
    )
