"""Lookup paramétrico de topes y factores de beneficios tributarios.

Track 11b: las constantes que el simulador y el comparador usaban
hardcoded (rebaja 14 E, sueldo empresarial razonable, UF estimada
para conversiones) viven ahora en `tax_params.beneficios_topes` con
vigencia anual. Cualquier cambio paramétrico = nueva fila, sin
redeploy de código.

Si la fila no existe para el `tax_year` pedido, se lanza
`MissingTaxYearParams` — el motor jamás opera con valores asumidos.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.lib.errors import MissingTaxYearParams


async def get_beneficio(
    session: AsyncSession, *, key: str, tax_year: int
) -> Decimal:
    """Devuelve `tax_params.beneficios_topes.valor` para (key, tax_year)."""
    result = await session.execute(
        text(
            """
            select valor
              from tax_params.beneficios_topes
             where key = :k
               and tax_year = :y
            """
        ),
        {"k": key, "y": tax_year},
    )
    row = result.first()
    if row is None:
        raise MissingTaxYearParams(
            f"No beneficios_topes row for key={key!r} at tax_year {tax_year}"
        )
    return Decimal(str(row[0]))
