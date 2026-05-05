"""Golden cases del cálculo IDPC.

🟡 Marcados @pytest.mark.xfail hasta que el contador socio firme la
tabla de tasas (TODOS-CONTADOR.md ítem #1). Los valores esperados
asumen las tasas placeholder de la migración
20260502120000_tax_params_placeholder_seeds.sql, así que pueden
"funcionar" hoy con strict=False — pero NO son válidos hasta firma.

Cuando contador firme:
1. Reemplazar la migración placeholder por la firmada.
2. Si los valores oficiales coinciden con los placeholder → quitar
   `strict=False` y los tests deberían pasar.
3. Si los valores cambian → actualizar las assertions y firmar el
   `expected_pesos` en cada caso golden.

Cada caso golden incluye:
- Inputs explícitos (régimen, año, RLI).
- Output esperado calculado a mano (con la tasa firmada).
- Año tributario y artículo LIR aplicable.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.tax_engine.idpc import compute_idpc
from src.lib.errors import MissingTaxYearParams
from tests.golden import GOLDENS_STRICT

XFAIL_REASON = (
    "awaiting CONTADOR_SOCIO signoff on TODOS-CONTADOR.md #1 (idpc_rates)"
)


@pytest.mark.golden
@pytest.mark.xfail(reason=XFAIL_REASON, strict=GOLDENS_STRICT)
async def test_idpc_14a_at2026_rli_50000000(
    admin_session: AsyncSession,
) -> None:
    """14 A AT 2026: RLI $50.000.000 * 27% = $13.500.000.

    Fundamento esperado: art. 14 A LIR, tasa permanente 27% post Ley
    21.210. Regla pendiente firma.
    """
    rli = Decimal("50000000")
    expected = Decimal("13500000.00")

    result = await compute_idpc(
        admin_session, regimen="14_a", tax_year=2026, rli=rli
    )
    assert result == expected


@pytest.mark.golden
@pytest.mark.xfail(reason=XFAIL_REASON, strict=GOLDENS_STRICT)
async def test_idpc_14d3_at2026_transitoria(
    admin_session: AsyncSession,
) -> None:
    """14 D N°3 AT 2026 con tasa transitoria 12,5%.

    RLI $30.000.000 * 12,5% = $3.750.000.
    Fundamento: Ley 21.755, Circular SII 53/2025. Sujeto a condicio-
    nalidad del art. 4° transitorio Ley 21.735.
    """
    rli = Decimal("30000000")
    expected = Decimal("3750000.00")

    result = await compute_idpc(
        admin_session, regimen="14_d_3", tax_year=2026, rli=rli
    )
    assert result == expected


@pytest.mark.golden
@pytest.mark.xfail(reason=XFAIL_REASON, strict=GOLDENS_STRICT)
async def test_idpc_14d3_at2025_permanente(
    admin_session: AsyncSession,
) -> None:
    """14 D N°3 AT 2025 a tasa permanente 25%.

    RLI $40.000.000 * 25% = $10.000.000.
    Fundamento: art. 14 D N°3 LIR, régimen permanente post-pandemia.
    """
    rli = Decimal("40000000")
    expected = Decimal("10000000.00")

    result = await compute_idpc(
        admin_session, regimen="14_d_3", tax_year=2025, rli=rli
    )
    assert result == expected


@pytest.mark.golden
@pytest.mark.xfail(reason=XFAIL_REASON, strict=GOLDENS_STRICT)
async def test_idpc_14d8_es_cero(
    admin_session: AsyncSession,
) -> None:
    """14 D N°8 (transparente): IDPC = 0 a nivel empresa siempre.

    El IDPC corre por los dueños vía IGC con renta atribuida.
    """
    result = await compute_idpc(
        admin_session, regimen="14_d_8", tax_year=2026, rli=Decimal("100000000")
    )
    assert result == Decimal("0.00")


# ---------------------------------------------------------------------------
# Edge cases (no requieren firma; son del motor mismo)
# ---------------------------------------------------------------------------


@pytest.mark.golden
async def test_idpc_rli_negativa_retorna_cero(
    admin_session: AsyncSession,
) -> None:
    """Pérdida tributaria → IDPC 0 (no se devuelve impuesto)."""
    result = await compute_idpc(
        admin_session, regimen="14_a", tax_year=2026, rli=Decimal("-1000000")
    )
    assert result == Decimal("0")


@pytest.mark.golden
async def test_idpc_anio_inexistente_explota(
    admin_session: AsyncSession,
) -> None:
    """Año sin parámetros cargados → MissingTaxYearParams."""
    with pytest.raises(MissingTaxYearParams):
        await compute_idpc(
            admin_session, regimen="14_a", tax_year=1999, rli=Decimal("1000000")
        )
