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
    # Track F22/F29 prefill: enriquecimientos derivables del SII
    # completo. Cada uno tiene su origen para que el wizard muestre
    # de dónde viene (F22 fisco vs core.empresas vs default).
    regimen_origen: str  # "f22" | "empresa" | "desconocido"
    regimen_f22_year: int | None  # AT del F22 sincronizado (si lo hay)
    ppm_promedio_mensual_pesos: Decimal | None
    ppm_meses_con_datos: int
    iva_postergacion_recurrente: bool


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

    # Capital + régimen vienen de core.empresas como fallback.
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
    regimen_empresa: str | None = None
    row = empresa_row.first()
    if row is not None:
        if row[0] is not None:
            capital_uf = Decimal(str(row[0]))
        regimen_db = str(row[1])
        regimen_empresa = (
            regimen_db
            if regimen_db in ("14_a", "14_d_3", "14_d_8")
            else None
        )

    # F22 sincronizado overridea el régimen de empresa cuando existe:
    # es la fuente de verdad del fisco para el último AT presentado.
    f22_result = await session.execute(
        text(
            """
            select tax_year, regimen_declarado
              from tax_data.f22_anios
             where empresa_id = :id
               and regimen_declarado in ('14_a', '14_d_3', '14_d_8')
             order by tax_year desc
             limit 1
            """
        ),
        {"id": str(empresa_id)},
    )
    f22_row = f22_result.first()
    regimen_f22_year: int | None = None
    if f22_row is not None:
        regimen_actual = str(f22_row[1])
        regimen_f22_year = int(f22_row[0])
        regimen_origen = "f22"
    elif regimen_empresa is not None:
        regimen_actual = regimen_empresa
        regimen_origen = "empresa"
    else:
        regimen_actual = None
        regimen_origen = "desconocido"

    # F29 últimos 12 meses → PPM promedio + bandera postergación
    # IVA recurrente. Si la mayoría de los F29 marca postergación,
    # el wizard sugiere P8 activado.
    f29_result = await session.execute(
        text(
            """
            select ppm, postergacion_iva
              from tax_data.f29_periodos
             where empresa_id = :id
             order by period desc
             limit 12
            """
        ),
        {"id": str(empresa_id)},
    )
    f29_rows = list(f29_result.all())
    ppm_values: list[Decimal] = [
        Decimal(str(r[0])) for r in f29_rows if r[0] is not None
    ]
    ppm_promedio: Decimal | None = None
    if ppm_values:
        ppm_promedio = (
            sum(ppm_values, Decimal("0")) / Decimal(len(ppm_values))
        ).quantize(Decimal("0.01"))
    iva_postergacion_count = sum(1 for r in f29_rows if r[1])
    # Mayoría = postergación recurrente → sugerencia P8.
    iva_postergacion_recurrente = (
        len(f29_rows) > 0 and iva_postergacion_count * 2 > len(f29_rows)
    )

    if regimen_origen == "f22":
        warnings.append(
            f"Régimen detectado en F22 AT {regimen_f22_year}: "
            f"{regimen_actual}. Si la empresa cambió de régimen para "
            f"AT {tax_year}, ajústalo manualmente."
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
        regimen_origen=regimen_origen,
        regimen_f22_year=regimen_f22_year,
        ppm_promedio_mensual_pesos=ppm_promedio,
        ppm_meses_con_datos=len(ppm_values),
        iva_postergacion_recurrente=iva_postergacion_recurrente,
    )
