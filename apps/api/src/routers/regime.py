"""Diagnóstico de régimen tributario — Track 7 oficial (skill 7).

POST /api/regime/diagnose recibe los inputs del wizard y retorna:

- Veredicto: régimen actual + recomendado + ahorro 3 años en CLP/UF.
- Elegibilidad por régimen con detalle de requisitos (✓ / ✗ + cita
  legal por requisito).
- Proyección 3 años por régimen elegible (RLI, IDPC, retiros, IGC,
  carga total) — usa `compute_idpc` y `compute_igc` reales.
- Para 14 D N°3: escenario dual (transitoria 12,5% vs revertido 25%
  por incumplimiento Ley 21.735 art. 4° transitorio).
- Riesgos / implicancias del cambio de régimen.

Persistencia: deferida a track 7b (tabla `core.recomendaciones` ya
existe). Por ahora retorna el resultado pero no lo guarda.

Auth: tenancy completa (workspace activo).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.tenancy import Tenancy, current_tenancy
from src.db import get_db_session
from src.domain.tax_engine.eligibility import (
    EligibilityInputs,
    Requisito,
    evaluar_14_a,
    evaluar_14_d_3,
    evaluar_14_d_8,
    evaluar_renta_presunta,
)
from src.domain.tax_engine.idpc import compute_idpc
from src.domain.tax_engine.igc import compute_igc

router = APIRouter(prefix="/api/regime", tags=["regime"])

PLACEHOLDER_DISCLAIMER = (
    "🟡 Diagnóstico calculado con tasas y tramos PLACEHOLDER pendientes "
    "de validación por contador socio. La proyección 3 años usa la RLI "
    "que tú declaraste como expectativa, sin sincronización SII real. "
    "NO usar para decidir cambio de régimen sin revisión humana."
)

# Tasa permanente 14 D N°3 cuando se rompe la condicionalidad de Ley
# 21.735 (art. 4° transitorio). Vive en el router (no en
# domain/tax_engine) — no es un parámetro paramétrico anual sino una
# regla de reversión condicional. Track 11 la lleva a un rule_set.
_TASA_14D3_REVERTIDA: Decimal = Decimal("0.25")

# UF placeholder mientras tax_params no exponga `uf_valor` por año.
# Track 11 reemplaza por lookup paramétrico.
_UF_PLACEHOLDER_CLP: Decimal = Decimal("38000")

# Horizonte de la proyección (3 años — fijo en skill 7).
_HORIZONTE_AÑOS: int = 3


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


Regimen = Literal["14_a", "14_d_3", "14_d_8"]
RegimenConPresunta = Literal["14_a", "14_d_3", "14_d_8", "renta_presunta"]
Sector = Literal[
    "comercio", "servicios", "agricola", "transporte", "mineria", "otro"
]


class DiagnoseRequest(BaseModel):
    """Inputs del wizard de diagnóstico (skill 7, preguntas 4-12)."""

    model_config = ConfigDict(extra="forbid")

    tax_year: int = Field(ge=2024, le=2030)
    regimen_actual: Regimen | None = Field(
        default=None,
        description=(
            "Régimen vigente del contribuyente. Si se omite asume 14 A "
            "(supletorio)."
        ),
    )
    ingresos_promedio_3a_uf: Decimal = Field(ge=0)
    ingresos_max_anual_uf: Decimal = Field(ge=0)
    capital_efectivo_inicial_uf: Decimal = Field(ge=0)
    pct_ingresos_pasivos: Decimal = Field(ge=0, le=1)
    todos_duenos_personas_naturales_chile: bool
    participacion_empresas_no_14d_sobre_10pct: bool
    sector: Sector
    ventas_anuales_uf: Decimal = Field(
        ge=0,
        description=(
            "Ventas anuales actuales (UF). Se usa para evaluar renta "
            "presunta cuando el sector lo permite."
        ),
    )
    rli_proyectada_anual_uf: Decimal = Field(
        ge=0,
        description="RLI esperada para cada uno de los próximos 3 años.",
    )
    plan_retiros_pct: Decimal = Field(
        ge=0,
        le=1,
        description="% de RLI que el dueño planea retirar cada año.",
    )


class RequisitoOut(BaseModel):
    texto: str
    ok: bool
    fundamento: str


class EligibilityOut(BaseModel):
    regimen: RegimenConPresunta
    label: str
    elegible: bool
    requisitos: list[RequisitoOut]


class ProjectionRow(BaseModel):
    año: int
    rli: Decimal
    idpc: Decimal
    retiros: Decimal
    igc_dueno: Decimal
    carga_total: Decimal


class RegimeProjection(BaseModel):
    regimen: RegimenConPresunta
    label: str
    rows: list[ProjectionRow]
    total_3a: Decimal
    es_transitoria: bool = False
    nota: str | None = None


class DualProjection(BaseModel):
    base: RegimeProjection
    revertido: RegimeProjection


class DiagnoseVeredicto(BaseModel):
    regimen_actual: Regimen
    regimen_recomendado: RegimenConPresunta
    ahorro_3a_clp: Decimal
    ahorro_3a_uf: Decimal


class DiagnoseResponse(BaseModel):
    tax_year: int
    veredicto: DiagnoseVeredicto
    elegibilidad: list[EligibilityOut]
    proyecciones: list[RegimeProjection]
    proyeccion_dual_14d3: DualProjection | None
    riesgos: list[str]
    fuente_legal: list[str]
    disclaimer: str = PLACEHOLDER_DISCLAIMER


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


REGIMEN_LABEL: dict[RegimenConPresunta, str] = {
    "14_a": "14 A — Régimen general (semi-integrado)",
    "14_d_3": "14 D N°3 — Pro PyME General",
    "14_d_8": "14 D N°8 — Pro PyME Transparente",
    "renta_presunta": "Renta presunta (art. 34 LIR)",
}


def _to_eligibility_inputs(req: DiagnoseRequest) -> EligibilityInputs:
    return EligibilityInputs(
        ingresos_promedio_3a_uf=req.ingresos_promedio_3a_uf,
        ingresos_max_anual_uf=req.ingresos_max_anual_uf,
        capital_efectivo_inicial_uf=req.capital_efectivo_inicial_uf,
        pct_ingresos_pasivos=req.pct_ingresos_pasivos,
        todos_duenos_personas_naturales_chile=(
            req.todos_duenos_personas_naturales_chile
        ),
        participacion_empresas_no_14d_sobre_10pct=(
            req.participacion_empresas_no_14d_sobre_10pct
        ),
        sector=req.sector,
        ventas_anuales_uf=req.ventas_anuales_uf,
    )


def _requisitos_to_out(reqs: list[Requisito]) -> list[RequisitoOut]:
    return [
        RequisitoOut(texto=r.texto, ok=r.ok, fundamento=r.fundamento)
        for r in reqs
    ]


async def _projection_for(
    session: AsyncSession,
    *,
    regimen: Regimen,
    tax_year_start: int,
    rli_anual_clp: Decimal,
    plan_retiros_pct: Decimal,
    forced_idpc_rate: Decimal | None = None,
) -> RegimeProjection:
    """Construye una proyección de `_HORIZONTE_AÑOS` años para un régimen.

    `forced_idpc_rate` permite reemplazar el lookup de tax_params por una
    tasa fija (ej. 25% para escenario revertido 14 D N°3).
    """
    rows: list[ProjectionRow] = []
    total = Decimal("0")

    for offset in range(_HORIZONTE_AÑOS):
        año = tax_year_start + offset
        rli = rli_anual_clp

        if forced_idpc_rate is not None:
            idpc = (forced_idpc_rate * rli).quantize(Decimal("0.01"))
        else:
            idpc = await compute_idpc(
                session, regimen=regimen, tax_year=año, rli=rli
            )

        retiros = (rli * plan_retiros_pct).quantize(Decimal("0.01"))
        base_igc = rli if regimen == "14_d_8" else retiros
        igc = await compute_igc(
            session, tax_year=año, base_pesos=base_igc
        )
        carga = idpc + igc

        rows.append(
            ProjectionRow(
                año=año,
                rli=rli,
                idpc=idpc,
                retiros=retiros,
                igc_dueno=igc,
                carga_total=carga,
            )
        )
        total += carga

    return RegimeProjection(
        regimen=regimen,
        label=REGIMEN_LABEL[regimen],
        rows=rows,
        total_3a=total,
    )


def _riesgos_para(
    regimen_actual: Regimen, recomendado: RegimenConPresunta
) -> list[str]:
    """Lista cualitativa de implicancias del cambio (skill 7 §5)."""
    if regimen_actual == recomendado:
        return [
            "El régimen actual ya es el más conveniente bajo los inputs "
            "declarados; no se requiere acción de cambio."
        ]

    base = [
        "Cambio formal: aviso al SII durante abril del año siguiente "
        "(art. 14 LIR). Mantén la documentación del cambio.",
        "Ajustes contables: redefinir plan de cuentas y registrar "
        "saldos iniciales SAC/RAI/REX si corresponde.",
        "IVA: el cambio de régimen no altera la posición ante IVA.",
        "Reversibilidad: existen plazos mínimos de permanencia antes "
        "de volver al régimen anterior; coordinar con contador.",
    ]
    if recomendado == "14_d_3":
        base.append(
            "Ley 21.735 art. 4° transitorio: la tasa 12,5% queda "
            "condicionada al cumplimiento de obligaciones de cotización "
            "del empleador. Si se rompe, la tasa revierte a 25% — "
            "consulta el escenario revertido en la proyección dual."
        )
    if recomendado == "14_d_8":
        base.append(
            "14 D N°8 atribuye RLI completa a los dueños (IDPC = 0). "
            "Verifica que los dueños puedan absorber la base IGC "
            "atribuida sin problemas de caja."
        )
    return base


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.post("/diagnose", response_model=DiagnoseResponse)
async def diagnose(
    payload: DiagnoseRequest,
    _tenancy: Tenancy = Depends(current_tenancy),
    session: AsyncSession = Depends(get_db_session),
) -> DiagnoseResponse:
    elig_inputs = _to_eligibility_inputs(payload)

    ok_14a, req_14a = evaluar_14_a(elig_inputs)
    ok_14d3, req_14d3 = evaluar_14_d_3(elig_inputs)
    ok_14d8, req_14d8 = evaluar_14_d_8(elig_inputs)
    ok_rp, req_rp = evaluar_renta_presunta(elig_inputs)

    elegibilidad = [
        EligibilityOut(
            regimen="14_a",
            label=REGIMEN_LABEL["14_a"],
            elegible=ok_14a,
            requisitos=_requisitos_to_out(req_14a),
        ),
        EligibilityOut(
            regimen="14_d_3",
            label=REGIMEN_LABEL["14_d_3"],
            elegible=ok_14d3,
            requisitos=_requisitos_to_out(req_14d3),
        ),
        EligibilityOut(
            regimen="14_d_8",
            label=REGIMEN_LABEL["14_d_8"],
            elegible=ok_14d8,
            requisitos=_requisitos_to_out(req_14d8),
        ),
        EligibilityOut(
            regimen="renta_presunta",
            label=REGIMEN_LABEL["renta_presunta"],
            elegible=ok_rp,
            requisitos=_requisitos_to_out(req_rp),
        ),
    ]

    rli_clp = (payload.rli_proyectada_anual_uf * _UF_PLACEHOLDER_CLP).quantize(
        Decimal("0.01")
    )

    proyecciones: list[RegimeProjection] = []
    elegibles: list[Regimen] = ["14_a"]
    if ok_14d3:
        elegibles.append("14_d_3")
    if ok_14d8:
        elegibles.append("14_d_8")

    for reg in elegibles:
        proyecciones.append(
            await _projection_for(
                session,
                regimen=reg,
                tax_year_start=payload.tax_year,
                rli_anual_clp=rli_clp,
                plan_retiros_pct=payload.plan_retiros_pct,
            )
        )

    proyeccion_dual: DualProjection | None = None
    if ok_14d3:
        base_14d3 = next(p for p in proyecciones if p.regimen == "14_d_3")
        base_14d3 = base_14d3.model_copy(
            update={
                "es_transitoria": True,
                "nota": (
                    "Escenario base con tasa transitoria 12,5% AT 2026-2028 "
                    "(Ley 21.755 + Circular SII 53/2025)."
                ),
            }
        )
        revertido = await _projection_for(
            session,
            regimen="14_d_3",
            tax_year_start=payload.tax_year,
            rli_anual_clp=rli_clp,
            plan_retiros_pct=payload.plan_retiros_pct,
            forced_idpc_rate=_TASA_14D3_REVERTIDA,
        )
        revertido = revertido.model_copy(
            update={
                "label": REGIMEN_LABEL["14_d_3"] + " (tasa revertida 25%)",
                "nota": (
                    "Escenario revertido a 25% por incumplimiento de la "
                    "condicionalidad de cotización empleador (Ley 21.735 "
                    "art. 4° transitorio)."
                ),
            }
        )
        proyeccion_dual = DualProjection(base=base_14d3, revertido=revertido)

    # Selección del recomendado: menor total_3a entre proyecciones lícitas.
    # Para 14 D N°3 usamos el escenario base (transitorio); el revertido
    # se muestra como riesgo, no compite directamente.
    recomendado_proj = min(proyecciones, key=lambda p: p.total_3a)
    actual = payload.regimen_actual or "14_a"
    actual_proj = next(
        (p for p in proyecciones if p.regimen == actual), proyecciones[0]
    )
    ahorro_clp = actual_proj.total_3a - recomendado_proj.total_3a
    ahorro_uf = (ahorro_clp / _UF_PLACEHOLDER_CLP).quantize(Decimal("0.01"))

    veredicto = DiagnoseVeredicto(
        regimen_actual=actual,
        regimen_recomendado=recomendado_proj.regimen,
        ahorro_3a_clp=ahorro_clp,
        ahorro_3a_uf=ahorro_uf,
    )

    fuente = [
        "art. 14 LIR (regímenes tributarios vigentes)",
        "Ley 21.210 (estructura de regímenes Pro PyME)",
        "Ley 21.755 + Circular SII 53/2025 (tasa transitoria 14 D N°3)",
        "Ley 21.735 art. 4° transitorio (condicionalidad cotización empleador)",
    ]

    return DiagnoseResponse(
        tax_year=payload.tax_year,
        veredicto=veredicto,
        elegibilidad=elegibilidad,
        proyecciones=proyecciones,
        proyeccion_dual_14d3=proyeccion_dual,
        riesgos=_riesgos_para(actual, recomendado_proj.regimen),
        fuente_legal=fuente,
    )
