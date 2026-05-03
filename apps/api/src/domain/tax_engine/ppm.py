"""Cálculo del PPM (Pago Provisional Mensual) PyME.

Aplica solo a regímenes 14 D N°3 y 14 D N°8. La tasa depende de los
ingresos del giro del año anterior:

    si ingresos_uf <= umbral_uf:
        ppm = ingresos_mes_pesos * tasa_bajo
    else:
        ppm = ingresos_mes_pesos * tasa_alto

🟡 Placeholder: tasas viven en `tax_params.ppm_pyme_rates`. Tests golden
en `@pytest.mark.xfail` hasta firma del contador.

Fundamento:
- Ley 21.210 (régimen PyME).
- Circular SII 53/2025 (tasa transitoria 0,125% / 0,25% para 14 D N°3).
- Aplicación: ago 2025 a dic 2027 (periodo transitorio).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.lib.errors import MissingTaxYearParams

PPMRegimen = Literal["14_d_3", "14_d_8"]


async def compute_ppm(
    session: AsyncSession,
    *,
    regimen: PPMRegimen,
    tax_year: int,
    ingresos_mes_pesos: Decimal,
    ingresos_anio_anterior_uf: Decimal,
) -> Decimal:
    """Calcula el PPM mensual en pesos.

    Args:
        session: AsyncSession.
        regimen: '14_d_3' | '14_d_8'.
        tax_year: año tributario en curso.
        ingresos_mes_pesos: ingresos del giro del mes (base PPM).
        ingresos_anio_anterior_uf: ingresos del giro año anterior, en UF
            (define qué tasa aplicar según umbral).

    Returns:
        PPM mensual en pesos (Decimal con 2 decimales).

    Raises:
        MissingTaxYearParams: si no hay fila para (tax_year, regimen).

    Fundamento:
        Ley 21.210 (régimen PyME), Circular SII 53/2025 (tasas
        transitorias). Tabla parametrizada en tax_params.ppm_pyme_rates.
    """
    if ingresos_mes_pesos <= 0:
        return Decimal("0")

    result = await session.execute(
        text(
            """
            select umbral_uf, tasa_bajo, tasa_alto
              from tax_params.ppm_pyme_rates
             where tax_year = :y
               and regimen = :r
            """
        ),
        {"y": tax_year, "r": regimen},
    )
    row = result.first()
    if row is None:
        raise MissingTaxYearParams(
            f"No ppm_pyme_rates row for ({regimen!r}, AT {tax_year})"
        )

    umbral_uf, tasa_bajo, tasa_alto = row
    tasa = tasa_bajo if ingresos_anio_anterior_uf <= umbral_uf else tasa_alto
    return (ingresos_mes_pesos * tasa).quantize(Decimal("0.01"))
