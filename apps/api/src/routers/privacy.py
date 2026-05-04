"""Solicitudes ARCOP — derechos del titular bajo Ley 21.719 (skill 5).

Endpoints:
- POST /api/privacy/arcop      crea una solicitud (acceso, rectificación,
                               cancelación, oposición o portabilidad).
- GET  /api/privacy/arcop      lista las propias del usuario; owner /
                               accountant_lead ven todas las del workspace
                               (RLS de privacy.arcop_requests).

Plazo legal de respuesta: 30 días corridos. La gestión la hace el DPO
desde un panel admin (skill 5, fase 6+); este endpoint cubre la
recepción.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.tenancy import Tenancy, current_tenancy
from src.db import get_db_session
from src.lib.audit import log_audit

router = APIRouter(prefix="/api/privacy", tags=["privacy"])


ArcopTipo = Literal[
    "acceso", "rectificacion", "cancelacion", "oposicion", "portabilidad"
]
ArcopEstado = Literal["recibida", "en_proceso", "cumplida", "rechazada"]


class CreateArcopRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tipo: ArcopTipo
    descripcion: str | None = Field(
        default=None,
        max_length=2000,
        description=(
            "Detalle libre del titular. Para 'rectificacion' incluir qué "
            "dato corregir y el valor solicitado."
        ),
    )


class UpdateArcopRequest(BaseModel):
    """PATCH del DPO (skill 5b). Cambia estado y/o registra respuesta."""

    model_config = ConfigDict(extra="forbid")

    estado: ArcopEstado | None = None
    respuesta: str | None = Field(default=None, max_length=4000)


class ArcopResponse(BaseModel):
    id: UUID
    tipo: ArcopTipo
    estado: ArcopEstado
    descripcion: str | None
    recibida_at: str
    respondida_at: str | None
    respuesta: str | None


class ArcopListResponse(BaseModel):
    solicitudes: list[ArcopResponse]


def _to_iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _row_to_arcop(row: dict[str, object]) -> ArcopResponse:
    recibida = row["recibida_at"]
    respondida = row["respondida_at"]
    return ArcopResponse.model_validate(
        {
            "id": UUID(str(row["id"])),
            "tipo": str(row["tipo"]),
            "estado": str(row["estado"]),
            "descripcion": (
                None
                if row["descripcion"] is None
                else str(row["descripcion"])
            ),
            "recibida_at": (
                recibida.isoformat()
                if isinstance(recibida, datetime)
                else str(recibida)
            ),
            "respondida_at": (
                respondida.isoformat()
                if isinstance(respondida, datetime)
                else None
            ),
            "respuesta": (
                None if row["respuesta"] is None else str(row["respuesta"])
            ),
        }
    )


@router.post(
    "/arcop",
    response_model=ArcopResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_arcop(
    payload: CreateArcopRequest,
    tenancy: Tenancy = Depends(current_tenancy),
    session: AsyncSession = Depends(get_db_session),
) -> ArcopResponse:
    """Recibe una solicitud ARCOP. Estado inicial = 'recibida'.

    Gatilla audit_log con `action='create'` y `resource_type='arcop'` para
    cumplir el principio de trazabilidad de la Ley 21.719.
    """
    result = await session.execute(
        text(
            """
            insert into privacy.arcop_requests
                (workspace_id, user_id, tipo, descripcion)
            values
                (:ws, :uid, :tipo, :desc)
            returning id, tipo, estado, descripcion, recibida_at,
                      respondida_at, respuesta
            """
        ),
        {
            "ws": str(tenancy.workspace_id),
            "uid": str(tenancy.user_id),
            "tipo": payload.tipo,
            "desc": payload.descripcion,
        },
    )
    row = result.mappings().one()
    arcop = _row_to_arcop(dict(row))

    await log_audit(
        session,
        workspace_id=tenancy.workspace_id,
        user_id=tenancy.user_id,
        action="create",
        resource_type="arcop",
        resource_id=arcop.id,
        metadata={"tipo": payload.tipo},
    )
    return arcop


_ADMIN_ROLES = frozenset({"owner", "accountant_lead"})

# Estados terminales: una vez cumplida o rechazada no se reabre. El DPO
# debe crear una nota nueva si necesita reanudar la gestión.
_TERMINAL_ESTADOS = frozenset({"cumplida", "rechazada"})


@router.get("/arcop", response_model=ArcopListResponse)
async def list_arcop(
    tenancy: Tenancy = Depends(current_tenancy),
    session: AsyncSession = Depends(get_db_session),
) -> ArcopListResponse:
    """Lista solicitudes del titular. Admins (owner / accountant_lead)
    ven todas las del workspace activo.

    `tenant_session` del backend corre como postgres (superuser) y
    bypassa RLS, por eso filtramos explícito por workspace_id +
    user_id según rol — defensa en profundidad.
    """
    if tenancy.role in _ADMIN_ROLES:
        result = await session.execute(
            text(
                """
                select id, tipo, estado, descripcion, recibida_at,
                       respondida_at, respuesta
                  from privacy.arcop_requests
                 where workspace_id = :ws
                 order by recibida_at desc
                """
            ),
            {"ws": str(tenancy.workspace_id)},
        )
    else:
        result = await session.execute(
            text(
                """
                select id, tipo, estado, descripcion, recibida_at,
                       respondida_at, respuesta
                  from privacy.arcop_requests
                 where workspace_id = :ws
                   and user_id = :uid
                 order by recibida_at desc
                """
            ),
            {
                "ws": str(tenancy.workspace_id),
                "uid": str(tenancy.user_id),
            },
        )
    items = [_row_to_arcop(dict(r)) for r in result.mappings().all()]
    return ArcopListResponse(solicitudes=items)


@router.patch("/arcop/{arcop_id}", response_model=ArcopResponse)
async def update_arcop(
    arcop_id: UUID,
    payload: UpdateArcopRequest,
    tenancy: Tenancy = Depends(current_tenancy),
    session: AsyncSession = Depends(get_db_session),
) -> ArcopResponse:
    """PATCH para el DPO: avanza estado y registra respuesta.

    Solo `owner` y `accountant_lead` pueden gestionar. Pasar a estado
    terminal (cumplida / rechazada) setea `respondida_at = now()`. Si
    ya está terminal, rechazar el PATCH.
    """
    if tenancy.role not in _ADMIN_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Solo owner o accountant_lead pueden gestionar "
                "solicitudes ARCOP (DPO interno)."
            ),
        )
    if payload.estado is None and payload.respuesta is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Debes enviar estado o respuesta.",
        )

    current = await session.execute(
        text(
            """
            select id, tipo, estado, descripcion, recibida_at,
                   respondida_at, respuesta
              from privacy.arcop_requests
             where id = :id and workspace_id = :ws
            """
        ),
        {"id": str(arcop_id), "ws": str(tenancy.workspace_id)},
    )
    current_row = current.mappings().one_or_none()
    if current_row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"solicitud ARCOP {arcop_id} no encontrada.",
        )
    if current_row["estado"] in _TERMINAL_ESTADOS:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"La solicitud ya está {current_row['estado']!r} y no "
                "puede reabrirse."
            ),
        )

    nuevo_estado = payload.estado or current_row["estado"]
    nueva_respuesta = (
        payload.respuesta
        if payload.respuesta is not None
        else current_row["respuesta"]
    )
    es_terminal = nuevo_estado in _TERMINAL_ESTADOS

    result = await session.execute(
        text(
            """
            update privacy.arcop_requests
               set estado = :estado,
                   respuesta = :respuesta,
                   respondida_at = case
                        when :terminal then coalesce(respondida_at, now())
                        else respondida_at
                   end
             where id = :id and workspace_id = :ws
            returning id, tipo, estado, descripcion, recibida_at,
                      respondida_at, respuesta
            """
        ),
        {
            "id": str(arcop_id),
            "ws": str(tenancy.workspace_id),
            "estado": nuevo_estado,
            "respuesta": nueva_respuesta,
            "terminal": es_terminal,
        },
    )
    row = result.mappings().one()
    arcop = _row_to_arcop(dict(row))

    await log_audit(
        session,
        workspace_id=tenancy.workspace_id,
        user_id=tenancy.user_id,
        action="update",
        resource_type="arcop",
        resource_id=arcop.id,
        metadata={
            "estado_anterior": current_row["estado"],
            "estado_nuevo": nuevo_estado,
            "respondida": payload.respuesta is not None,
        },
    )
    return arcop
