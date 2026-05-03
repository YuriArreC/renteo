"""Cálculo del Impuesto Global Complementario (IGC).

Tabla de 8 tramos en UTA, art. 52 LIR. La fórmula por tramo es:

    impuesto = (base_uta * tasa - rebajar) * uta_pesos_dic

donde tasa y rebajar dependen del tramo en el que cae la `base_uta`.

🟡 Placeholder: tramos viven en `tax_params.igc_brackets` con
`fuente_legal` marcado como PLACEHOLDER. Tests golden en
`@pytest.mark.xfail` hasta firma del contador (TODOS-CONTADOR.md ítem #2).

Crédito 5% último tramo (art. 56 LIR): aplica sobre la fracción
afecta al 40% (tramo 8). Lo aplicamos como deducción al final.

Fundamento:
- Art. 52 LIR (tabla de tramos IGC).
- Art. 56 LIR (crédito 5% sobre fracción afecta al 40%).
- Tabla anual publicada por SII en función de la UTA dic.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.lib.errors import MissingTaxYearParams


async def compute_igc(
    session: AsyncSession,
    *,
    tax_year: int,
    base_pesos: Decimal,
) -> Decimal:
    """Calcula el IGC anual del dueño en pesos chilenos.

    Args:
        session: AsyncSession.
        tax_year: año tributario.
        base_pesos: base imponible anual en pesos (suma de retiros
            afectos, sueldos, otras rentas afectas a IGC).

    Returns:
        IGC bruto en pesos (Decimal con 2 decimales). Antes de aplicar
        créditos (IDPC, IPE, donaciones).

    Raises:
        MissingTaxYearParams: si faltan filas en igc_brackets o
            tax_year_params para el año.

    Fundamento:
        Art. 52 LIR + tabla anual SII. La tabla está parametrizada por
        año en tax_params.igc_brackets (rangos en UTA, tasa marginal,
        cantidad a rebajar).
    """
    if base_pesos <= 0:
        return Decimal("0")

    # 1. Cargar UTA dic del año (para convertir base_pesos → base_uta).
    uta_result = await session.execute(
        text(
            "select uta_pesos_dic from tax_params.tax_year_params "
            "where tax_year = :y"
        ),
        {"y": tax_year},
    )
    uta_row = uta_result.first()
    if uta_row is None:
        raise MissingTaxYearParams(
            f"No tax_year_params row for AT {tax_year}"
        )
    uta_pesos: Decimal = uta_row[0]

    # 2. Convertir base a UTA.
    base_uta = (base_pesos / uta_pesos).quantize(Decimal("0.0001"))

    # 3. Cargar tramos del año, ordenados ascendente.
    brackets_result = await session.execute(
        text(
            """
            select desde_uta, hasta_uta, tasa, rebajar_uta
              from tax_params.igc_brackets
             where tax_year = :y
             order by tramo asc
            """
        ),
        {"y": tax_year},
    )
    brackets = brackets_result.all()
    if not brackets:
        raise MissingTaxYearParams(
            f"No igc_brackets rows for AT {tax_year}"
        )

    # 4. Encontrar el tramo correcto.
    selected = None
    for desde, hasta, tasa, rebajar in brackets:
        if base_uta >= desde and (hasta is None or base_uta < hasta):
            selected = (tasa, rebajar)
            break

    if selected is None:
        # base_uta cae fuera de todos los tramos (caso extremo).
        # Default al último tramo.
        selected = (brackets[-1][2], brackets[-1][3])

    tasa, rebajar = selected

    # 5. impuesto_uta = base_uta * tasa - rebajar.
    impuesto_uta = base_uta * tasa - rebajar
    if impuesto_uta < 0:
        impuesto_uta = Decimal("0")

    # 6. Convertir a pesos.
    impuesto_pesos = (impuesto_uta * uta_pesos).quantize(Decimal("0.01"))
    return impuesto_pesos
