"""Encargados de tratamiento — registro Ley 21.719 (skill 5).

Endpoints:
- GET  /api/public/encargados            lista pública (sin auth) para
                                          que la página de privacidad
                                          consuma el listado vigente.
- GET  /api/admin/encargados             lista completa con DPAs y
                                          fechas (require_internal_admin).
- POST /api/admin/encargados             crea un encargado nuevo.
- PATCH /api/admin/encargados/{id}       edita campos no críticos.
- DELETE /api/admin/encargados/{id}      soft-delete.

Datos: nombre, propósito, país de tratamiento, DPA firmado (fecha +
vigencia + URL), contacto del DPO del proveedor.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from src.auth.internal_admin import require_internal_admin
from src.db import service_session

router = APIRouter(prefix="/api/admin/encargados", tags=["admin"])
public_router = APIRouter(
    prefix="/api/public/encargados", tags=["public"]
)


class EncargadoPublic(BaseModel):
    nombre: str
    proposito: str
    pais_tratamiento: str


class EncargadoListPublicResponse(BaseModel):
    encargados: list[EncargadoPublic]


class EncargadoAdmin(BaseModel):
    id: UUID
    nombre: str
    proposito: str
    pais_tratamiento: str
    dpa_firmado_at: date | None
    dpa_vigente_hasta: date | None
    dpa_url: str | None
    contacto_dpo: str | None
    notas: str | None
    activo: bool
    created_at: str
    updated_at: str


class EncargadoListAdminResponse(BaseModel):
    encargados: list[EncargadoAdmin]


class CreateEncargadoRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nombre: str = Field(min_length=1, max_length=160)
    proposito: str = Field(min_length=1, max_length=600)
    pais_tratamiento: str = Field(default="CL", min_length=2, max_length=4)
    dpa_firmado_at: date | None = None
    dpa_vigente_hasta: date | None = None
    dpa_url: str | None = Field(default=None, max_length=400)
    contacto_dpo: str | None = Field(default=None, max_length=160)
    notas: str | None = Field(default=None, max_length=2000)


class UpdateEncargadoRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proposito: str | None = Field(default=None, max_length=600)
    pais_tratamiento: str | None = Field(default=None, min_length=2, max_length=4)
    dpa_firmado_at: date | None = None
    dpa_vigente_hasta: date | None = None
    dpa_url: str | None = Field(default=None, max_length=400)
    contacto_dpo: str | None = Field(default=None, max_length=160)
    notas: str | None = Field(default=None, max_length=2000)
    activo: bool | None = None


def _row_to_admin(row: dict[str, Any]) -> EncargadoAdmin:
    created_at = row["created_at"]
    updated_at = row["updated_at"]
    return EncargadoAdmin.model_validate(
        {
            "id": UUID(str(row["id"])),
            "nombre": str(row["nombre"]),
            "proposito": str(row["proposito"]),
            "pais_tratamiento": str(row["pais_tratamiento"]),
            "dpa_firmado_at": row["dpa_firmado_at"],
            "dpa_vigente_hasta": row["dpa_vigente_hasta"],
            "dpa_url": row["dpa_url"],
            "contacto_dpo": row["contacto_dpo"],
            "notas": row["notas"],
            "activo": bool(row["activo"]),
            "created_at": (
                created_at.isoformat()
                if isinstance(created_at, datetime)
                else str(created_at)
            ),
            "updated_at": (
                updated_at.isoformat()
                if isinstance(updated_at, datetime)
                else str(updated_at)
            ),
        }
    )


@public_router.get("", response_model=EncargadoListPublicResponse)
async def list_public() -> EncargadoListPublicResponse:
    """Lista pública: solo datos no sensibles (nombre, propósito, país)."""
    async with service_session() as session:
        result = await session.execute(
            text(
                """
                select nombre, proposito, pais_tratamiento
                  from privacy.encargados
                 where activo = true and deleted_at is null
                 order by nombre
                """
            )
        )
        return EncargadoListPublicResponse(
            encargados=[
                EncargadoPublic.model_validate(dict(r))
                for r in result.mappings().all()
            ]
        )


@router.get("", response_model=EncargadoListAdminResponse)
async def list_admin(
    _admin: UUID = Depends(require_internal_admin),
) -> EncargadoListAdminResponse:
    async with service_session() as session:
        result = await session.execute(
            text(
                """
                select id, nombre, proposito, pais_tratamiento,
                       dpa_firmado_at, dpa_vigente_hasta, dpa_url,
                       contacto_dpo, notas, activo, created_at,
                       updated_at
                  from privacy.encargados
                 where deleted_at is null
                 order by nombre
                """
            )
        )
        return EncargadoListAdminResponse(
            encargados=[
                _row_to_admin(dict(r)) for r in result.mappings().all()
            ]
        )


def _map_check_violation(exc: IntegrityError) -> HTTPException:
    """El CHECK del schema exige dpa_vigente_hasta > dpa_firmado_at.
    Lo mapeamos a 422 con un mensaje útil para el panel admin."""
    if "encargados_check" in str(exc.orig):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "dpa_vigente_hasta debe ser posterior a dpa_firmado_at."
            ),
        )
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=str(exc.orig),
    )


@router.post(
    "", response_model=EncargadoAdmin, status_code=status.HTTP_201_CREATED
)
async def create_encargado(
    payload: CreateEncargadoRequest,
    _admin: UUID = Depends(require_internal_admin),
) -> EncargadoAdmin:
    async with service_session() as session:
        try:
            result = await session.execute(
                text(
                    """
                    insert into privacy.encargados
                        (nombre, proposito, pais_tratamiento,
                         dpa_firmado_at, dpa_vigente_hasta, dpa_url,
                         contacto_dpo, notas)
                    values
                        (:nombre, :proposito, :pais,
                         :firmado, :vigente, :url, :dpo, :notas)
                    returning id, nombre, proposito, pais_tratamiento,
                              dpa_firmado_at, dpa_vigente_hasta, dpa_url,
                              contacto_dpo, notas, activo, created_at,
                              updated_at
                    """
                ),
                {
                    "nombre": payload.nombre,
                    "proposito": payload.proposito,
                    "pais": payload.pais_tratamiento,
                    "firmado": payload.dpa_firmado_at,
                    "vigente": payload.dpa_vigente_hasta,
                    "url": payload.dpa_url,
                    "dpo": payload.contacto_dpo,
                    "notas": payload.notas,
                },
            )
            row = result.mappings().one()
        except IntegrityError as exc:
            raise _map_check_violation(exc) from exc
    return _row_to_admin(dict(row))


@router.patch("/{encargado_id}", response_model=EncargadoAdmin)
async def update_encargado(
    encargado_id: UUID,
    payload: UpdateEncargadoRequest,
    _admin: UUID = Depends(require_internal_admin),
) -> EncargadoAdmin:
    """Actualiza campos no críticos. `nombre` no se cambia (mantener
    el log claro: si cambia el proveedor real, crear uno nuevo y
    deactivar el anterior)."""
    diff = payload.model_dump(exclude_none=True)
    if not diff:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Sin campos a actualizar.",
        )

    async with service_session() as session:
        try:
            result = await session.execute(
                text(
                    """
                    update privacy.encargados
                       set proposito        = coalesce(:proposito, proposito),
                           pais_tratamiento = coalesce(:pais, pais_tratamiento),
                           dpa_firmado_at   = coalesce(:firmado, dpa_firmado_at),
                           dpa_vigente_hasta= coalesce(:vigente, dpa_vigente_hasta),
                           dpa_url          = coalesce(:url, dpa_url),
                           contacto_dpo     = coalesce(:dpo, contacto_dpo),
                           notas            = coalesce(:notas, notas),
                           activo           = coalesce(:activo, activo)
                     where id = :id and deleted_at is null
                    returning id, nombre, proposito, pais_tratamiento,
                              dpa_firmado_at, dpa_vigente_hasta, dpa_url,
                              contacto_dpo, notas, activo, created_at,
                              updated_at
                    """
                ),
                {
                    "id": str(encargado_id),
                    "proposito": diff.get("proposito"),
                    "pais": diff.get("pais_tratamiento"),
                    "firmado": diff.get("dpa_firmado_at"),
                    "vigente": diff.get("dpa_vigente_hasta"),
                    "url": diff.get("dpa_url"),
                    "dpo": diff.get("contacto_dpo"),
                    "notas": diff.get("notas"),
                    "activo": diff.get("activo"),
                },
            )
            row = result.mappings().one_or_none()
        except IntegrityError as exc:
            raise _map_check_violation(exc) from exc
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"encargado {encargado_id} no encontrado.",
        )
    return _row_to_admin(dict(row))


@router.delete("/{encargado_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_encargado(
    encargado_id: UUID,
    _admin: UUID = Depends(require_internal_admin),
) -> None:
    """Soft-delete: marca deleted_at = now(). El registro queda en BD
    para auditoría histórica (qué encargados tuvimos en cada momento)."""
    async with service_session() as session:
        result = await session.execute(
            text(
                """
                update privacy.encargados
                   set deleted_at = now()
                 where id = :id and deleted_at is null
                returning id
                """
            ),
            {"id": str(encargado_id)},
        )
        row = result.first()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"encargado {encargado_id} no encontrado.",
        )
