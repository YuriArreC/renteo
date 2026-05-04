"""Vista cartera — feature exclusiva de cliente B (skill 9).

GET /api/cartera devuelve una fila por empresa del workspace activo
con datos densos pensados para una grilla tipo Bloomberg:

- empresa: RUT, razón social, régimen actual.
- alertas_abiertas: count de filas en core.alertas con estado
  ('nueva' | 'vista').
- ultima_simulacion: id, ahorro y fecha del escenario más reciente
  (si existe).
- ultima_recomendacion: id, regimen recomendado y ahorro 3a del
  diagnóstico más reciente (si existe).
- score_oportunidad: 0-100. MVP: cap_alertas + cap_sin_diagnostico.
  Cliente B usa este score para priorizar la cartera.

Auth: tenancy completa. RLS de core.empresas filtra por workspace.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.tenancy import Tenancy, current_tenancy
from src.db import get_db_session

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
