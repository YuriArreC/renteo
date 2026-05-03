"""Cálculo del Impuesto de Primera Categoría (IDPC).

🟡 Placeholder: las tasas viven en `tax_params.idpc_rates` con
`fuente_legal` marcado como PLACEHOLDER. Los tests golden están en
`@pytest.mark.xfail` hasta que el contador socio firme la tabla
oficial (TODOS-CONTADOR.md ítem #1).

Cuando se firme:
1. Reemplazar la migración placeholder por la firmada.
2. Quitar `xfail` de los tests golden.
3. CI debería pasar verde; si falla, hay bug en este módulo.

Fundamento legal:
- Art. 14 A LIR (régimen general semi integrado, IDPC permanente).
- Art. 14 D N°3 LIR (Pro Pyme General, IDPC con rampa transitoria).
- Art. 14 D N°8 LIR (Pro Pyme Transparente, IDPC = 0 a nivel empresa).
- Ley 21.578 (rampa transitoria post-pandemia).
- Ley 21.755 + Circular SII 53/2025 (rebaja transitoria 12,5% AT 2026-2028).
- Ley 21.735 art. 4° transitorio (condicionalidad por cotización empleador).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.lib.errors import MissingTaxYearParams

Regimen = Literal["14_a", "14_d_3", "14_d_8"]


async def compute_idpc(
    session: AsyncSession,
    *,
    regimen: Regimen,
    tax_year: int,
    rli: Decimal,
) -> Decimal:
    """Calcula el IDPC bruto: tasa × RLI.

    Args:
        session: AsyncSession (sin RLS necesario; tax_params es global).
        regimen: '14_a' | '14_d_3' | '14_d_8'.
        tax_year: año tributario (debe existir en tax_year_params).
        rli: Renta Líquida Imponible en pesos chilenos.

    Returns:
        IDPC bruto en pesos chilenos (Decimal). NO aplica créditos.

    Raises:
        MissingTaxYearParams: si no hay fila en idpc_rates para
            (tax_year, regimen).

    Fundamento:
        Art. 14 LIR. Tasa por (año, régimen) en tax_params.idpc_rates.
        Para 14 D N°3 AT 2026-2028 la tasa transitoria 12,5% queda sujeta
        a feature flag (`tax_rules.feature_flags_by_year`) — fase 1+.
    """
    if rli < 0:
        # RLI negativa = pérdida tributaria; IDPC es 0 (no se devuelve).
        return Decimal("0")

    result = await session.execute(
        text(
            """
            select rate
              from tax_params.idpc_rates
             where tax_year = :tax_year
               and regimen = :regimen
            """
        ),
        {"tax_year": tax_year, "regimen": regimen},
    )
    row = result.first()
    if row is None:
        raise MissingTaxYearParams(
            f"No idpc_rates row for ({regimen!r}, AT {tax_year})"
        )

    rate: Decimal = row[0]
    return (rate * rli).quantize(Decimal("0.01"))
