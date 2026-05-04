"""Derivación de inputs del wizard a partir de datos SII sincronizados.

Track 1 (post skill 4): aprovecha `tax_data.rcv_lines` para precargar
las preguntas 4-9 del wizard (ventas anuales, ingresos prom 3 años,
ingreso máximo). El resto sigue exigiéndose al usuario porque no es
derivable solo del RCV (sector, dueños, planes de retiro).

La conversión CLP → UF usa `tax_params.beneficios_topes.uf_valor_clp`
del año pedido, manteniendo la promesa de skill 11: ningún valor
hardcoded en código.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.tax_engine.beneficios import get_beneficio
from src.lib.errors import MissingTaxYearParams


@dataclass(frozen=True)
class WizardPrefill:
    empresa_id: UUID
    tax_year: int
    ventas_anuales_uf: Decimal | None
    ingresos_promedio_3a_uf: Decimal | None
    ingresos_max_anual_uf: Decimal | None
    capital_efectivo_inicial_uf: Decimal | None
    regimen_actual: str | None
    uf_valor_clp_usado: Decimal
    anios_con_datos: list[int]
    warnings: list[str]


async def _ventas_clp_por_anio(
    session: AsyncSession, *, empresa_id: UUID, anios: list[int]
) -> dict[int, Decimal]:
    """Suma `total` (CLP) de RCV tipo='venta' por año, restringida a
    los años pedidos. Usa el período YYYY-MM para extraer el año."""
    if not anios:
        return {}
    result = await session.execute(
        text(
            """
            select substr(period, 1, 4)::int as anio,
                   coalesce(sum(total), 0) as total
              from tax_data.rcv_lines
             where empresa_id = :e
               and tipo = 'venta'
               and substr(period, 1, 4)::int = any(cast(:anios as int[]))
             group by substr(period, 1, 4)
            """
        ),
        {"e": str(empresa_id), "anios": anios},
    )
    return {int(r[0]): Decimal(str(r[1])) for r in result.all()}


async def build_wizard_prefill(
    session: AsyncSession,
    *,
    empresa_id: UUID,
    tax_year: int,
) -> WizardPrefill:
    """Construye el prefill mirando RCV ventas + capital de la empresa.

    Reglas:
    - `ventas_anuales_uf`  : ventas del año tributario - 1 (devengado).
    - `ingresos_promedio_3a_uf`: promedio de los últimos 3 años con datos.
    - `ingresos_max_anual_uf` : máximo de los últimos 3 años con datos.
    - Si un año no tiene RCV, se omite del cálculo y se agrega un
      warning visible al usuario.
    """
    warnings: list[str] = []

    try:
        uf_clp = await get_beneficio(
            session, key="uf_valor_clp", tax_year=tax_year
        )
    except MissingTaxYearParams as exc:
        raise MissingTaxYearParams(
            f"Falta uf_valor_clp para tax_year={tax_year}; "
            "publica el parámetro antes de pedir prefill."
        ) from exc

    # Ventas se buscan para los 3 años fiscales previos.
    target_anios = [tax_year - i for i in (1, 2, 3)]
    ventas = await _ventas_clp_por_anio(
        session, empresa_id=empresa_id, anios=target_anios
    )
    anios_con_datos = sorted(a for a in target_anios if ventas.get(a))

    if not anios_con_datos:
        warnings.append(
            "No hay líneas RCV de ventas para los últimos 3 años. "
            "Sincroniza con SII antes de usar el prefill."
        )

    def _to_uf(clp: Decimal) -> Decimal:
        return (clp / uf_clp).quantize(Decimal("0.01"))

    ventas_anuales_uf: Decimal | None = None
    anio_ventas = tax_year - 1
    if ventas.get(anio_ventas):
        ventas_anuales_uf = _to_uf(ventas[anio_ventas])
    else:
        warnings.append(
            f"Sin ventas RCV para el año {anio_ventas}; revisa el "
            "alcance de la sincronización."
        )

    ingresos_max_anual_uf: Decimal | None = None
    ingresos_promedio_3a_uf: Decimal | None = None
    if anios_con_datos:
        anuales_clp = [ventas[a] for a in anios_con_datos]
        ingresos_max_anual_uf = _to_uf(max(anuales_clp))
        promedio_clp = sum(anuales_clp, Decimal("0")) / Decimal(
            len(anuales_clp)
        )
        ingresos_promedio_3a_uf = _to_uf(promedio_clp)

        if len(anios_con_datos) < 3:
            warnings.append(
                "El promedio 3 años se calculó con menos de 3 años "
                f"({len(anios_con_datos)}). Sigue siendo válido pero "
                "menos representativo."
            )

    # Capital + régimen vienen de core.empresas.
    empresa_row = await session.execute(
        text(
            """
            select capital_inicial_uf, regimen_actual
              from core.empresas
             where id = :id
               and deleted_at is null
            """
        ),
        {"id": str(empresa_id)},
    )
    capital_uf: Decimal | None = None
    regimen_actual: str | None = None
    row = empresa_row.first()
    if row is not None:
        if row[0] is not None:
            capital_uf = Decimal(str(row[0]))
        regimen_db = str(row[1])
        regimen_actual = (
            regimen_db
            if regimen_db in ("14_a", "14_d_3", "14_d_8")
            else None
        )

    return WizardPrefill(
        empresa_id=empresa_id,
        tax_year=tax_year,
        ventas_anuales_uf=ventas_anuales_uf,
        ingresos_promedio_3a_uf=ingresos_promedio_3a_uf,
        ingresos_max_anual_uf=ingresos_max_anual_uf,
        capital_efectivo_inicial_uf=capital_uf,
        regimen_actual=regimen_actual,
        uf_valor_clp_usado=uf_clp,
        anios_con_datos=anios_con_datos,
        warnings=warnings,
    )
