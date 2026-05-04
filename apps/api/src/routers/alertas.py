"""Alertas pre-cierre — track Alertas (skill 8 / 9).

Endpoints:
- POST /api/alertas/evaluate    evalúa estado declarado y persiste las
                                candidatas nuevas en core.alertas.
- GET  /api/alertas             lista alertas del workspace activo
                                (filtros opcionales: empresa_id, estado).
- PATCH /api/alertas/{id}       marca vista | descartada | accionada.

Auth: tenancy completa.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.tenancy import Tenancy, current_tenancy
from src.db import get_db_session
from src.domain.tax_engine.alertas import (
    AlertaInputs,
    Regimen,
    Severidad,
    evaluate_pre_cierre,
)
from src.lib.audit import log_audit

router = APIRouter(prefix="/api/alertas", tags=["alertas"])


AlertaEstado = Literal["nueva", "vista", "descartada", "accionada"]
_OPEN_ESTADOS: tuple[AlertaEstado, ...] = ("nueva", "vista")


class EvaluateAlertasRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    empresa_id: UUID
    tax_year: int = Field(ge=2024, le=2030)
    regimen: Regimen
    rli_proyectada_pesos: Decimal = Field(ge=0)
    retiros_declarados_pesos: Decimal = Field(default=Decimal("0"), ge=0)
    palancas_aplicadas: list[str] = Field(default_factory=list)


class AlertaResponse(BaseModel):
    id: UUID
    empresa_id: UUID | None
    tipo: str
    severidad: Severidad
    titulo: str
    descripcion: str
    accion_recomendada: str | None
    estado: AlertaEstado
    fecha_limite: date | None
    created_at: str


class AlertasListResponse(BaseModel):
    alertas: list[AlertaResponse]


class EvaluateAlertasResponse(BaseModel):
    creadas: int
    ya_existentes: int
    alertas: list[AlertaResponse]


class UpdateAlertaRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    estado: AlertaEstado


def _row_to_alerta(row: dict[str, object]) -> AlertaResponse:
    created_at = row["created_at"]
    fecha_limite = row["fecha_limite"]
    return AlertaResponse.model_validate(
        {
            "id": UUID(str(row["id"])),
            "empresa_id": (
                UUID(str(row["empresa_id"]))
                if row["empresa_id"] is not None
                else None
            ),
            "tipo": str(row["tipo"]),
            "severidad": str(row["severidad"]),
            "titulo": str(row["titulo"]),
            "descripcion": str(row["descripcion"]),
            "accion_recomendada": (
                None
                if row["accion_recomendada"] is None
                else str(row["accion_recomendada"])
            ),
            "estado": str(row["estado"]),
            "fecha_limite": fecha_limite,
            "created_at": (
                created_at.isoformat()
                if isinstance(created_at, datetime)
                else str(created_at)
            ),
        }
    )


async def _assert_empresa_in_workspace(
    session: AsyncSession, empresa_id: UUID, workspace_id: UUID
) -> None:
    result = await session.execute(
        text(
            """
            select 1 from core.empresas
             where id = :id and workspace_id = :ws and deleted_at is null
            """
        ),
        {"id": str(empresa_id), "ws": str(workspace_id)},
    )
    if result.first() is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"empresa_id {empresa_id} no existe en el workspace o "
                "no tienes acceso bajo tu rol."
            ),
        )


@router.post("/evaluate", response_model=EvaluateAlertasResponse)
async def evaluate_alertas(
    payload: EvaluateAlertasRequest,
    tenancy: Tenancy = Depends(current_tenancy),
    session: AsyncSession = Depends(get_db_session),
) -> EvaluateAlertasResponse:
    """Evalúa el estado declarado y persiste las alertas nuevas.

    Dedup por (workspace_id, empresa_id, tax_year, tipo) sobre alertas
    abiertas (estado in nueva|vista). Si el usuario descartó la alerta
    antes, vuelve a aparecer en la próxima evaluación si la condición
    persiste.
    """
    await _assert_empresa_in_workspace(
        session, payload.empresa_id, tenancy.workspace_id
    )

    inputs = AlertaInputs(
        regimen=payload.regimen,
        tax_year=payload.tax_year,
        rli_proyectada_pesos=payload.rli_proyectada_pesos,
        retiros_declarados_pesos=payload.retiros_declarados_pesos,
        palancas_aplicadas=frozenset(payload.palancas_aplicadas),
    )
    candidates = evaluate_pre_cierre(inputs)
    if not candidates:
        return EvaluateAlertasResponse(creadas=0, ya_existentes=0, alertas=[])

    # Trae alertas abiertas existentes para dedup.
    existing = await session.execute(
        text(
            """
            select tipo from core.alertas
             where workspace_id = :ws
               and empresa_id = :emp
               and estado = any(cast(:estados as text[]))
               and tipo = any(cast(:tipos as text[]))
            """
        ),
        {
            "ws": str(tenancy.workspace_id),
            "emp": str(payload.empresa_id),
            "estados": list(_OPEN_ESTADOS),
            "tipos": [c.tipo for c in candidates],
        },
    )
    existing_tipos = {row[0] for row in existing.all()}

    creadas: list[AlertaResponse] = []
    for cand in candidates:
        if cand.tipo in existing_tipos:
            continue
        result = await session.execute(
            text(
                """
                insert into core.alertas
                    (workspace_id, empresa_id, tipo, severidad,
                     titulo, descripcion, accion_recomendada,
                     fecha_limite)
                values
                    (:ws, :emp, :tipo, :sev,
                     :titulo, :desc, :accion, :fecha)
                returning id, empresa_id, tipo, severidad, titulo,
                          descripcion, accion_recomendada, estado,
                          fecha_limite, created_at
                """
            ),
            {
                "ws": str(tenancy.workspace_id),
                "emp": str(payload.empresa_id),
                "tipo": cand.tipo,
                "sev": cand.severidad,
                "titulo": cand.titulo,
                "desc": cand.descripcion,
                "accion": cand.accion_recomendada,
                "fecha": cand.fecha_limite,
            },
        )
        row = result.mappings().one()
        alerta = _row_to_alerta(dict(row))
        creadas.append(alerta)
        await log_audit(
            session,
            workspace_id=tenancy.workspace_id,
            user_id=tenancy.user_id,
            action="create",
            resource_type="alerta",
            resource_id=alerta.id,
            empresa_id=payload.empresa_id,
            metadata={"tipo": cand.tipo, "severidad": cand.severidad},
        )

    return EvaluateAlertasResponse(
        creadas=len(creadas),
        ya_existentes=len(existing_tipos),
        alertas=creadas,
    )


@router.get("", response_model=AlertasListResponse)
async def list_alertas(
    empresa_id: UUID | None = None,
    incluir_cerradas: bool = False,
    tenancy: Tenancy = Depends(current_tenancy),
    session: AsyncSession = Depends(get_db_session),
) -> AlertasListResponse:
    """Lista alertas del workspace activo (RLS filtra). Por defecto solo
    abiertas (`nueva` y `vista`)."""
    estados = (
        ("nueva", "vista", "descartada", "accionada")
        if incluir_cerradas
        else _OPEN_ESTADOS
    )
    result = await session.execute(
        text(
            """
            select id, empresa_id, tipo, severidad, titulo,
                   descripcion, accion_recomendada, estado,
                   fecha_limite, created_at
              from core.alertas
             where workspace_id = :ws
               and estado = any(cast(:estados as text[]))
               and (
                    cast(:empresa as uuid) is null
                    or empresa_id = cast(:empresa as uuid)
               )
             order by
                case severidad
                    when 'critical' then 0
                    when 'warning'  then 1
                    when 'info'     then 2
                    else 3
                end,
                created_at desc
            """
        ),
        {
            "ws": str(tenancy.workspace_id),
            "estados": list(estados),
            "empresa": str(empresa_id) if empresa_id is not None else None,
        },
    )
    items = [_row_to_alerta(dict(r)) for r in result.mappings().all()]
    return AlertasListResponse(alertas=items)


@router.patch("/{alerta_id}", response_model=AlertaResponse)
async def update_alerta(
    alerta_id: UUID,
    payload: UpdateAlertaRequest,
    tenancy: Tenancy = Depends(current_tenancy),
    session: AsyncSession = Depends(get_db_session),
) -> AlertaResponse:
    """Cambia el estado de una alerta (vista | descartada | accionada)."""
    result = await session.execute(
        text(
            """
            update core.alertas
               set estado = :estado
             where id = :id and workspace_id = :ws
            returning id, empresa_id, tipo, severidad, titulo,
                      descripcion, accion_recomendada, estado,
                      fecha_limite, created_at
            """
        ),
        {
            "id": str(alerta_id),
            "ws": str(tenancy.workspace_id),
            "estado": payload.estado,
        },
    )
    row = result.mappings().one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"alerta {alerta_id} no encontrada en este workspace.",
        )
    alerta = _row_to_alerta(dict(row))
    await log_audit(
        session,
        workspace_id=tenancy.workspace_id,
        user_id=tenancy.user_id,
        action="update",
        resource_type="alerta",
        resource_id=alerta.id,
        empresa_id=alerta.empresa_id,
        metadata={"estado_nuevo": payload.estado, "tipo": alerta.tipo},
    )
    return alerta
