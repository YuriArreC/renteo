"""Diagnóstico de régimen tributario — Track 7 + 7b (skill 7).

Endpoints:
- POST /api/regime/diagnose: ejecuta el motor + persiste la
  recomendación (track 7b) en core.recomendaciones con
  disclaimer_version, engine_version, fundamento_legal e
  inputs/outputs serializados.
- GET /api/regime/recomendaciones: lista recomendaciones del
  workspace activo (RLS filtra), ordenadas por created_at desc.

Auth: tenancy completa (workspace activo).
"""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.tenancy import Tenancy, current_tenancy
from src.db import get_db_session
from src.domain.tax_engine.beneficios import get_beneficio
from src.domain.tax_engine.eligibility import (
    EligibilityInputs,
    Requisito,
    evaluar_14_a,
    evaluar_14_d_3,
    evaluar_14_d_8,
    evaluar_renta_presunta,
)
from src.domain.tax_engine.guardrails import is_recomendacion_whitelisted
from src.domain.tax_engine.idpc import compute_idpc
from src.domain.tax_engine.igc import compute_igc
from src.domain.tax_engine.snapshot import build_snapshots
from src.lib.errors import RedFlagBlocked
from src.lib.legal_texts import get_legal_text

router = APIRouter(prefix="/api/regime", tags=["regime"])

PLACEHOLDER_DISCLAIMER = (
    "Disclaimer pendiente de carga desde privacy.legal_texts."
)

# Track 7b: ID lógico del motor que produjo la recomendación. Incluido
# en cada fila persistida para reproducibilidad. Track 11 oficial lo
# derivará del rules_snapshot_hash.
ENGINE_VERSION = "track-7b-mvp-001"

_FLAG_14D3_REVERTIDA = "idpc_14d3_revertida_rate"


async def _get_revertida_rate(
    session: AsyncSession, tax_year: int
) -> Decimal:
    """Lee el feature flag publicado para `tax_year` y devuelve la tasa.

    Track 11: la tasa permanente 14 D N°3 cuando se rompe la
    condicionalidad de Ley 21.735 art. 4° transitorio vive en
    `tax_rules.feature_flags_by_year` con vigencia por effective_from.
    """
    from datetime import date

    target_date = date(tax_year, 12, 31)
    result = await session.execute(
        text(
            """
            select value
              from tax_rules.feature_flags_by_year
             where flag_key = :k
               and effective_from <= :t
             order by effective_from desc
             limit 1
            """
        ),
        {"k": _FLAG_14D3_REVERTIDA, "t": target_date},
    )
    row = result.first()
    if row is None:
        # Sin flag publicado para el año: se respeta la promesa de skill 11
        # (motor jamás opera con valores asumidos en silencio) propagando
        # 0 — el escenario revertido queda señalizado como vacío y la UI
        # muestra que no hay flag aplicable.
        return Decimal("0")
    return Decimal(str(row[0]))


# UF estimada se lee de tax_params.beneficios_topes (track 11b).
_UF_KEY = "uf_valor_clp"

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
    empresa_id: UUID | None = Field(
        default=None,
        description=(
            "Empresa del workspace activo a la que se asocia el "
            "diagnóstico. Si se omite, queda como recomendación "
            "workspace-level."
        ),
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
    id: UUID
    tax_year: int
    veredicto: DiagnoseVeredicto
    elegibilidad: list[EligibilityOut]
    proyecciones: list[RegimeProjection]
    proyeccion_dual_14d3: DualProjection | None
    riesgos: list[str]
    fuente_legal: list[str]
    disclaimer: str = PLACEHOLDER_DISCLAIMER
    disclaimer_version: str = "v1"
    engine_version: str = ENGINE_VERSION


class RecomendacionListItem(BaseModel):
    """Resumen de una recomendación persistida (skill 7b)."""

    id: UUID
    tax_year: int
    tipo: str
    descripcion: str
    regimen_actual: Literal["14_a", "14_d_3", "14_d_8"]
    regimen_recomendado: Literal["14_a", "14_d_3", "14_d_8", "renta_presunta"]
    ahorro_estimado_clp: Decimal | None
    disclaimer_version: str
    engine_version: str
    empresa_id: UUID | None
    created_at: str


class RecomendacionListResponse(BaseModel):
    recomendaciones: list[RecomendacionListItem]


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


async def _assert_empresa_in_workspace(
    session: AsyncSession, empresa_id: UUID
) -> None:
    """Bajo RLS, ver una empresa implica pertenecer al workspace activo."""
    result = await session.execute(
        text("select 1 from core.empresas where id = :id and deleted_at is null"),
        {"id": str(empresa_id)},
    )
    if result.first() is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"empresa_id {empresa_id} no existe en el workspace o no "
                "tienes acceso bajo tu rol."
            ),
        )


@router.post("/diagnose", response_model=DiagnoseResponse)
async def diagnose(
    payload: DiagnoseRequest,
    tenancy: Tenancy = Depends(current_tenancy),
    session: AsyncSession = Depends(get_db_session),
) -> DiagnoseResponse:
    if payload.empresa_id is not None:
        await _assert_empresa_in_workspace(session, payload.empresa_id)

    elig_inputs = _to_eligibility_inputs(payload)

    ok_14a, req_14a = await evaluar_14_a(
        session, elig_inputs, payload.tax_year
    )
    ok_14d3, req_14d3 = await evaluar_14_d_3(
        session, elig_inputs, payload.tax_year
    )
    ok_14d8, req_14d8 = await evaluar_14_d_8(
        session, elig_inputs, payload.tax_year
    )
    ok_rp, req_rp = await evaluar_renta_presunta(
        session, elig_inputs, payload.tax_year
    )

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

    uf_clp = await get_beneficio(
        session, key=_UF_KEY, tax_year=payload.tax_year
    )
    rli_clp = (payload.rli_proyectada_anual_uf * uf_clp).quantize(
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
        revertida_rate = await _get_revertida_rate(session, payload.tax_year)
        revertido = await _projection_for(
            session,
            regimen="14_d_3",
            tax_year_start=payload.tax_year,
            rli_anual_clp=rli_clp,
            plan_retiros_pct=payload.plan_retiros_pct,
            forced_idpc_rate=revertida_rate,
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
    ahorro_uf = (ahorro_clp / uf_clp).quantize(Decimal("0.01"))

    # Skill 1: si la recomendación implica cambio de régimen, validar
    # que `cambio_regimen` esté en lista blanca antes de devolverla.
    if recomendado_proj.regimen != actual and not await is_recomendacion_whitelisted(
        session, "cambio_regimen", payload.tax_year
    ):
        raise RedFlagBlocked(
            "cambio_regimen no está en la lista blanca de recomendaciones"
        )

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

    legal = await get_legal_text(session, "disclaimer-recomendacion")

    descripcion = (
        f"Régimen actual {actual.upper()} → recomendado "
        f"{recomendado_proj.regimen.upper()}. "
        f"Ahorro estimado 3 años: {ahorro_clp} CLP."
    )
    inputs_payload = json.loads(payload.model_dump_json())
    outputs_payload = {
        "veredicto": json.loads(veredicto.model_dump_json()),
        "elegibilidad": [
            json.loads(e.model_dump_json()) for e in elegibilidad
        ],
        "proyecciones": [
            json.loads(p.model_dump_json()) for p in proyecciones
        ],
        "proyeccion_dual_14d3": (
            json.loads(proyeccion_dual.model_dump_json())
            if proyeccion_dual
            else None
        ),
        "riesgos": _riesgos_para(actual, recomendado_proj.regimen),
        "fuente_legal": fuente,
    }
    fundamento_payload = [{"texto": f} for f in fuente]
    rule_snap, params_snap, snap_hash = await build_snapshots(
        session, tax_year=payload.tax_year
    )

    result = await session.execute(
        text(
            """
            insert into core.recomendaciones
                (workspace_id, empresa_id, tax_year,
                 tipo, descripcion, fundamento_legal,
                 ahorro_estimado_clp,
                 disclaimer_version, engine_version,
                 inputs_snapshot, outputs,
                 rule_set_snapshot, tax_year_params_snapshot,
                 rules_snapshot_hash,
                 created_by)
            values
                (:ws, :empresa, :year,
                 'cambio_regimen', :desc, cast(:fund as jsonb),
                 :ahorro,
                 :disc_v, :ver,
                 cast(:inp as jsonb), cast(:out as jsonb),
                 cast(:rule_snap as jsonb),
                 cast(:params_snap as jsonb),
                 :hash,
                 :uid)
            returning id
            """
        ),
        {
            "ws": str(tenancy.workspace_id),
            "empresa": (
                str(payload.empresa_id)
                if payload.empresa_id is not None
                else None
            ),
            "year": payload.tax_year,
            "desc": descripcion,
            "fund": json.dumps(fundamento_payload),
            "ahorro": ahorro_clp,
            "disc_v": legal.version,
            "ver": ENGINE_VERSION,
            "inp": json.dumps(inputs_payload, default=str),
            "out": json.dumps(outputs_payload, default=str),
            "rule_snap": json.dumps(rule_snap, default=str),
            "params_snap": json.dumps(params_snap, default=str),
            "hash": snap_hash,
            "uid": str(tenancy.user_id),
        },
    )
    rec_id = UUID(str(result.scalar_one()))

    return DiagnoseResponse(
        id=rec_id,
        tax_year=payload.tax_year,
        veredicto=veredicto,
        elegibilidad=elegibilidad,
        proyecciones=proyecciones,
        proyeccion_dual_14d3=proyeccion_dual,
        riesgos=_riesgos_para(actual, recomendado_proj.regimen),
        fuente_legal=fuente,
        disclaimer=legal.body,
        disclaimer_version=legal.version,
    )


@router.get(
    "/recomendaciones", response_model=RecomendacionListResponse
)
async def list_recomendaciones(
    tax_year: int | None = None,
    empresa_id: UUID | None = None,
    limit: int = 50,
    _tenancy: Tenancy = Depends(current_tenancy),
    session: AsyncSession = Depends(get_db_session),
) -> RecomendacionListResponse:
    """Lista recomendaciones del workspace activo (RLS filtra)."""
    params: dict[str, Any] = {
        "limit": limit,
        "year": tax_year,
        "empresa": str(empresa_id) if empresa_id is not None else None,
    }
    result = await session.execute(
        text(
            """
            select id, tax_year, tipo, descripcion,
                   ahorro_estimado_clp, disclaimer_version,
                   engine_version, empresa_id, outputs, created_at
              from core.recomendaciones
             where tipo = 'cambio_regimen'
               and tax_year = coalesce(:year, tax_year)
               and (
                    :empresa::uuid is null
                    or empresa_id = :empresa::uuid
               )
             order by created_at desc
             limit :limit
            """
        ),
        params,
    )
    rows = result.mappings().all()
    items: list[RecomendacionListItem] = []
    for row in rows:
        outputs = row["outputs"] or {}
        veredicto = outputs.get("veredicto") or {}
        items.append(
            RecomendacionListItem(
                id=UUID(str(row["id"])),
                tax_year=row["tax_year"],
                tipo=row["tipo"],
                descripcion=row["descripcion"],
                regimen_actual=veredicto.get("regimen_actual", "14_a"),
                regimen_recomendado=veredicto.get(
                    "regimen_recomendado", "14_a"
                ),
                ahorro_estimado_clp=row["ahorro_estimado_clp"],
                disclaimer_version=row["disclaimer_version"],
                engine_version=row["engine_version"],
                empresa_id=(
                    UUID(str(row["empresa_id"]))
                    if row["empresa_id"] is not None
                    else None
                ),
                created_at=row["created_at"].isoformat(),
            )
        )
    return RecomendacionListResponse(recomendaciones=items)
