"""Vista cartera — feature exclusiva de cliente B (skill 9).

Endpoints:
- GET  /api/cartera                fila por empresa del workspace
                                   activo con score y últimos
                                   cálculos.
- POST /api/cartera/batch-diagnose recibe N empresa_ids + inputs
                                   template del wizard skill 7 y
                                   ejecuta diagnose por cada una en
                                   serie. Devuelve resumen por empresa
                                   (régimen actual / recomendado /
                                   ahorro) + total agregado.

Auth: tenancy completa. RLS de core.empresas filtra por workspace.
"""

from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from typing import Literal
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
    evaluar_14_a,
    evaluar_14_d_3,
    evaluar_14_d_8,
)
from src.domain.tax_engine.idpc import compute_idpc
from src.domain.tax_engine.igc import compute_igc
from src.domain.tax_engine.snapshot import build_snapshots
from src.lib.audit import log_audit
from src.lib.legal_texts import get_legal_text

router = APIRouter(prefix="/api/cartera", tags=["cartera"])


RegimenActual = Literal[
    "14_a", "14_d_3", "14_d_8", "presunta", "desconocido"
]


class UltimaSimulacion(BaseModel):
    id: UUID
    ahorro_total_clp: Decimal
    created_at: str


class UltimaRecomendacion(BaseModel):
    id: UUID
    regimen_recomendado: str
    ahorro_estimado_clp: Decimal | None
    created_at: str


class CarteraEmpresaItem(BaseModel):
    empresa_id: UUID
    rut: str
    razon_social: str
    regimen_actual: RegimenActual
    alertas_abiertas: int
    ultima_simulacion: UltimaSimulacion | None
    ultima_recomendacion: UltimaRecomendacion | None
    score_oportunidad: int


class CarteraResponse(BaseModel):
    empresas: list[CarteraEmpresaItem]
    total_empresas: int
    total_alertas_abiertas: int
    ahorro_potencial_estimado_clp: Decimal


# ---------------------------------------------------------------------------
# Batch diagnóstico — modelos
# ---------------------------------------------------------------------------


Sector = Literal[
    "comercio", "servicios", "agricola", "transporte", "mineria", "otro"
]


class DiagnoseInputsTemplate(BaseModel):
    """Template aplicado a TODAS las empresas seleccionadas en el batch.

    Cliente B usualmente atiende empresas con perfiles similares
    (mismo giro, ingresos parecidos). Este template es el "first pass"
    rápido; el contador refina cada caso después en el wizard.
    """

    model_config = ConfigDict(extra="forbid")

    tax_year: int = Field(ge=2024, le=2030)
    ingresos_promedio_3a_uf: Decimal = Field(ge=0)
    ingresos_max_anual_uf: Decimal = Field(ge=0)
    capital_efectivo_inicial_uf: Decimal = Field(ge=0)
    pct_ingresos_pasivos: Decimal = Field(ge=0, le=1)
    todos_duenos_personas_naturales_chile: bool = True
    participacion_empresas_no_14d_sobre_10pct: bool = False
    sector: Sector = "comercio"
    ventas_anuales_uf: Decimal = Field(ge=0)
    rli_proyectada_anual_uf: Decimal = Field(ge=0)
    plan_retiros_pct: Decimal = Field(ge=0, le=1)


class BatchDiagnoseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    empresa_ids: list[UUID] = Field(min_length=1, max_length=50)
    inputs: DiagnoseInputsTemplate


Regimen = Literal["14_a", "14_d_3", "14_d_8"]


class BatchDiagnoseItem(BaseModel):
    empresa_id: UUID
    razon_social: str
    regimen_actual: Regimen
    regimen_recomendado: Regimen
    ahorro_estimado_clp: Decimal
    recomendacion_id: UUID
    error: str | None = None


class BatchDiagnoseFailure(BaseModel):
    empresa_id: UUID
    error: str


class BatchDiagnoseResponse(BaseModel):
    procesadas: int
    creadas: int
    fallidas: int
    items: list[BatchDiagnoseItem]
    failures: list[BatchDiagnoseFailure]
    ahorro_total_clp: Decimal
    disclaimer_version: str


def _score(*, alertas_abiertas: int, sin_diagnostico: bool) -> int:
    """Cálculo MVP del score 0-100.

    - 25 puntos por cada alerta abierta hasta 75 (cap).
    - +25 puntos si la empresa nunca fue diagnosticada. El gap de
      información es oportunidad para el contador.
    - cap final 100.
    """
    score = min(alertas_abiertas * 25, 75)
    if sin_diagnostico:
        score += 25
    return min(score, 100)


@router.get("", response_model=CarteraResponse)
async def get_cartera(
    _tenancy: Tenancy = Depends(current_tenancy),
    session: AsyncSession = Depends(get_db_session),
) -> CarteraResponse:
    """Devuelve la cartera enriquecida del workspace activo."""
    result = await session.execute(
        text(
            """
            with alertas_abiertas as (
                select empresa_id, count(*)::int as n
                  from core.alertas
                 where estado in ('nueva', 'vista')
                   and empresa_id is not null
              group by empresa_id
            ),
            ultima_sim as (
                select distinct on (empresa_id)
                       empresa_id, id, outputs, created_at
                  from core.escenarios_simulacion
                 where empresa_id is not null
              order by empresa_id, created_at desc
            ),
            ultima_rec as (
                select distinct on (empresa_id)
                       empresa_id, id,
                       outputs->'veredicto'->>'regimen_recomendado' as reg,
                       ahorro_estimado_clp,
                       created_at
                  from core.recomendaciones
                 where empresa_id is not null
                   and tipo = 'cambio_regimen'
              order by empresa_id, created_at desc
            )
            select e.id, e.rut, e.razon_social, e.regimen_actual,
                   coalesce(a.n, 0) as alertas_abiertas,
                   s.id as sim_id,
                   s.outputs->>'ahorro_total' as sim_ahorro,
                   s.created_at as sim_at,
                   r.id as rec_id, r.reg as rec_regimen,
                   r.ahorro_estimado_clp as rec_ahorro,
                   r.created_at as rec_at
              from core.empresas e
         left join alertas_abiertas a on a.empresa_id = e.id
         left join ultima_sim s on s.empresa_id = e.id
         left join ultima_rec r on r.empresa_id = e.id
             where e.deleted_at is null
          order by e.created_at desc
            """
        )
    )
    rows = result.mappings().all()

    items: list[CarteraEmpresaItem] = []
    total_alertas = 0
    ahorro_acum = Decimal("0")

    for row in rows:
        sim_id = row["sim_id"]
        rec_id = row["rec_id"]
        ultima_sim: UltimaSimulacion | None = None
        ultima_rec: UltimaRecomendacion | None = None

        if sim_id is not None:
            sim_at = row["sim_at"]
            ultima_sim = UltimaSimulacion(
                id=UUID(str(sim_id)),
                ahorro_total_clp=Decimal(str(row["sim_ahorro"] or "0")),
                created_at=(
                    sim_at.isoformat()
                    if isinstance(sim_at, datetime)
                    else str(sim_at)
                ),
            )

        if rec_id is not None:
            rec_at = row["rec_at"]
            ultima_rec = UltimaRecomendacion(
                id=UUID(str(rec_id)),
                regimen_recomendado=str(row["rec_regimen"] or "14_a"),
                ahorro_estimado_clp=row["rec_ahorro"],
                created_at=(
                    rec_at.isoformat()
                    if isinstance(rec_at, datetime)
                    else str(rec_at)
                ),
            )

        alertas_abiertas = int(row["alertas_abiertas"])
        score = _score(
            alertas_abiertas=alertas_abiertas,
            sin_diagnostico=ultima_rec is None,
        )

        items.append(
            CarteraEmpresaItem.model_validate(
                {
                    "empresa_id": UUID(str(row["id"])),
                    "rut": str(row["rut"]),
                    "razon_social": str(row["razon_social"]),
                    "regimen_actual": str(row["regimen_actual"]),
                    "alertas_abiertas": alertas_abiertas,
                    "ultima_simulacion": ultima_sim,
                    "ultima_recomendacion": ultima_rec,
                    "score_oportunidad": score,
                }
            )
        )
        total_alertas += alertas_abiertas
        if ultima_rec and ultima_rec.ahorro_estimado_clp:
            ahorro_acum += ultima_rec.ahorro_estimado_clp

    items.sort(key=lambda x: x.score_oportunidad, reverse=True)

    return CarteraResponse(
        empresas=items,
        total_empresas=len(items),
        total_alertas_abiertas=total_alertas,
        ahorro_potencial_estimado_clp=ahorro_acum,
    )


# ---------------------------------------------------------------------------
# Batch diagnóstico — endpoint
# ---------------------------------------------------------------------------


_HORIZONTE_AÑOS = 3


async def _carga_anual(
    session: AsyncSession,
    *,
    regimen: Regimen,
    tax_year: int,
    rli: Decimal,
    retiros: Decimal,
) -> Decimal:
    idpc = await compute_idpc(
        session, regimen=regimen, tax_year=tax_year, rli=rli
    )
    base_igc = rli if regimen == "14_d_8" else retiros
    igc = await compute_igc(
        session, tax_year=tax_year, base_pesos=base_igc
    )
    return idpc + igc


async def _proyeccion_3a(
    session: AsyncSession,
    *,
    regimen: Regimen,
    tax_year: int,
    rli_clp: Decimal,
    plan_retiros_pct: Decimal,
) -> Decimal:
    total = Decimal("0")
    retiros = (rli_clp * plan_retiros_pct).quantize(Decimal("0.01"))
    for offset in range(_HORIZONTE_AÑOS):
        total += await _carga_anual(
            session,
            regimen=regimen,
            tax_year=tax_year + offset,
            rli=rli_clp,
            retiros=retiros,
        )
    return total


def _resolve_actual(regimen_db: str) -> Regimen:
    """Mapea core.empresas.regimen_actual a un régimen elegible. Para
    'desconocido' o 'presunta' usamos 14 A como baseline."""
    if regimen_db in ("14_a", "14_d_3", "14_d_8"):
        return regimen_db  # type: ignore[return-value]
    return "14_a"


async def _diagnose_one(
    session: AsyncSession,
    *,
    workspace_id: UUID,
    user_id: UUID,
    empresa_id: UUID,
    razon_social: str,
    regimen_db: str,
    tpl: DiagnoseInputsTemplate,
) -> BatchDiagnoseItem:
    """Mini-diagnose: evalúa elegibilidad + proyecta carga 3a por
    régimen elegible y recomienda el de menor carga total. Persiste
    en core.recomendaciones con engine_version=batch-cliente-b-v2.
    """
    elig_inputs = EligibilityInputs(
        ingresos_promedio_3a_uf=tpl.ingresos_promedio_3a_uf,
        ingresos_max_anual_uf=tpl.ingresos_max_anual_uf,
        capital_efectivo_inicial_uf=tpl.capital_efectivo_inicial_uf,
        pct_ingresos_pasivos=tpl.pct_ingresos_pasivos,
        todos_duenos_personas_naturales_chile=(
            tpl.todos_duenos_personas_naturales_chile
        ),
        participacion_empresas_no_14d_sobre_10pct=(
            tpl.participacion_empresas_no_14d_sobre_10pct
        ),
        sector=tpl.sector,
        ventas_anuales_uf=tpl.ventas_anuales_uf,
    )
    ok_14a, _ = await evaluar_14_a(session, elig_inputs, tpl.tax_year)
    ok_14d3, _ = await evaluar_14_d_3(session, elig_inputs, tpl.tax_year)
    ok_14d8, _ = await evaluar_14_d_8(session, elig_inputs, tpl.tax_year)

    elegibles: list[Regimen] = []
    if ok_14a:
        elegibles.append("14_a")
    if ok_14d3:
        elegibles.append("14_d_3")
    if ok_14d8:
        elegibles.append("14_d_8")

    uf_clp = await get_beneficio(
        session, key="uf_valor_clp", tax_year=tpl.tax_year
    )
    rli_clp = (tpl.rli_proyectada_anual_uf * uf_clp).quantize(
        Decimal("0.01")
    )

    proyecciones: dict[Regimen, Decimal] = {}
    for reg in elegibles:
        proyecciones[reg] = await _proyeccion_3a(
            session,
            regimen=reg,
            tax_year=tpl.tax_year,
            rli_clp=rli_clp,
            plan_retiros_pct=tpl.plan_retiros_pct,
        )

    actual = _resolve_actual(regimen_db)
    recomendado: Regimen = (
        min(proyecciones, key=lambda r: proyecciones[r])
        if proyecciones
        else actual
    )
    actual_carga = proyecciones.get(
        actual, await _proyeccion_3a(
            session,
            regimen=actual,
            tax_year=tpl.tax_year,
            rli_clp=rli_clp,
            plan_retiros_pct=tpl.plan_retiros_pct,
        )
    )
    ahorro = actual_carga - proyecciones.get(recomendado, actual_carga)

    legal = await get_legal_text(session, "disclaimer-recomendacion")
    rule_snap, params_snap, snap_hash = await build_snapshots(
        session, tax_year=tpl.tax_year
    )

    descripcion = (
        f"Batch: {actual.upper()} → {recomendado.upper()}. "
        f"Ahorro 3a estimado: {ahorro} CLP."
    )
    inputs_payload = {
        "tax_year": tpl.tax_year,
        "regimen_actual": actual,
        "template": json.loads(tpl.model_dump_json()),
        "via": "batch-cartera-v2",
    }
    outputs_payload = {
        "veredicto": {
            "regimen_actual": actual,
            "regimen_recomendado": recomendado,
            "ahorro_3a_clp": str(ahorro),
        },
        "proyecciones_3a": {
            r: str(v) for r, v in proyecciones.items()
        },
        "elegibles": elegibles,
    }
    fundamento_payload = [
        {"texto": "art. 14 LIR (regímenes vigentes)"},
        {"texto": "Ley 21.210 (estructura Pro PyME)"},
    ]

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
                (:ws, :emp, :year,
                 'cambio_regimen', :desc, cast(:fund as jsonb),
                 :ahorro,
                 :disc_v, 'batch-cliente-b-v2',
                 cast(:inp as jsonb), cast(:out as jsonb),
                 cast(:rule_snap as jsonb),
                 cast(:params_snap as jsonb),
                 :hash,
                 :uid)
            returning id
            """
        ),
        {
            "ws": str(workspace_id),
            "emp": str(empresa_id),
            "year": tpl.tax_year,
            "desc": descripcion,
            "fund": json.dumps(fundamento_payload),
            "ahorro": ahorro,
            "disc_v": legal.version,
            "inp": json.dumps(inputs_payload, default=str),
            "out": json.dumps(outputs_payload, default=str),
            "rule_snap": json.dumps(rule_snap, default=str),
            "params_snap": json.dumps(params_snap, default=str),
            "hash": snap_hash,
            "uid": str(user_id),
        },
    )
    rec_id = UUID(str(result.scalar_one()))

    return BatchDiagnoseItem(
        empresa_id=empresa_id,
        razon_social=razon_social,
        regimen_actual=actual,
        regimen_recomendado=recomendado,
        ahorro_estimado_clp=ahorro,
        recomendacion_id=rec_id,
    )


@router.post(
    "/batch-diagnose", response_model=BatchDiagnoseResponse
)
async def batch_diagnose(
    payload: BatchDiagnoseRequest,
    tenancy: Tenancy = Depends(current_tenancy),
    session: AsyncSession = Depends(get_db_session),
) -> BatchDiagnoseResponse:
    """Ejecuta diagnose simplificado sobre N empresas con un mismo
    template de inputs. Cada empresa queda con su recomendación
    persistida (auditable como las del wizard individual).
    """
    # Trae las empresas seleccionadas; RLS filtra por workspace.
    empresa_ids_str = [str(e) for e in payload.empresa_ids]
    rows = await session.execute(
        text(
            """
            select id, razon_social, regimen_actual
              from core.empresas
             where id = any(cast(:ids as uuid[]))
               and deleted_at is null
            """
        ),
        {"ids": empresa_ids_str},
    )
    empresas = {
        UUID(str(r["id"])): {
            "razon_social": str(r["razon_social"]),
            "regimen_actual": str(r["regimen_actual"]),
        }
        for r in rows.mappings().all()
    }

    missing = [eid for eid in payload.empresa_ids if eid not in empresas]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "empresa_ids fuera del workspace o inexistentes: "
                f"{', '.join(str(m) for m in missing)}"
            ),
        )

    items: list[BatchDiagnoseItem] = []
    failures: list[BatchDiagnoseFailure] = []
    ahorro_total = Decimal("0")
    legal = await get_legal_text(session, "disclaimer-recomendacion")

    for emp_id in payload.empresa_ids:
        info = empresas[emp_id]
        try:
            item = await _diagnose_one(
                session,
                workspace_id=tenancy.workspace_id,
                user_id=tenancy.user_id,
                empresa_id=emp_id,
                razon_social=info["razon_social"],
                regimen_db=info["regimen_actual"],
                tpl=payload.inputs,
            )
            items.append(item)
            ahorro_total += item.ahorro_estimado_clp
        except Exception as exc:
            failures.append(
                BatchDiagnoseFailure(empresa_id=emp_id, error=str(exc))
            )

    await log_audit(
        session,
        workspace_id=tenancy.workspace_id,
        user_id=tenancy.user_id,
        action="batch_diagnose",
        resource_type="recomendacion",
        metadata={
            "n_empresas": len(payload.empresa_ids),
            "creadas": len(items),
            "fallidas": len(failures),
            "tax_year": payload.inputs.tax_year,
        },
    )

    return BatchDiagnoseResponse(
        procesadas=len(payload.empresa_ids),
        creadas=len(items),
        fallidas=len(failures),
        items=items,
        failures=failures,
        ahorro_total_clp=ahorro_total,
        disclaimer_version=legal.version,
    )
