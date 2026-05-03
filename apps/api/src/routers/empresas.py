"""Gestión de empresas — track Empresas (skill 6 + skill 9).

POST /api/empresas      crea una empresa en el workspace activo.
GET  /api/empresas      lista las empresas visibles bajo RLS.

Auth: tenancy completa (workspace activo). Roles permitidos para
crear: owner, cfo, accountant_lead. RLS de `core.empresas` filtra
por workspace + rol.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.tenancy import Tenancy, current_tenancy
from src.db import get_db_session
from src.lib.audit import log_audit, mask_rut
from src.lib.rut import InvalidRutError, validate_rut

router = APIRouter(prefix="/api/empresas", tags=["empresas"])

RegimenActual = Literal[
    "14_a", "14_d_3", "14_d_8", "presunta", "desconocido"
]


class CreateEmpresaRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rut: str = Field(min_length=3, max_length=12)
    razon_social: str = Field(min_length=2, max_length=160)
    giro: str | None = Field(default=None, max_length=200)
    regimen_actual: RegimenActual = "desconocido"
    fecha_inicio_actividades: date | None = None
    capital_inicial_uf: Decimal | None = Field(default=None, ge=0)

    @field_validator("rut")
    @classmethod
    def _validate_rut(cls, v: str) -> str:
        try:
            return validate_rut(v)
        except InvalidRutError as exc:
            raise ValueError(str(exc)) from exc


class EmpresaResponse(BaseModel):
    id: UUID
    rut: str
    razon_social: str
    giro: str | None
    regimen_actual: RegimenActual
    fecha_inicio_actividades: date | None
    capital_inicial_uf: Decimal | None
    created_at: str


class EmpresasListResponse(BaseModel):
    empresas: list[EmpresaResponse]


_ALLOWED_CREATE_ROLES = frozenset({"owner", "cfo", "accountant_lead"})


def _row_to_empresa(row: dict[str, object]) -> EmpresaResponse:
    created_at = row["created_at"]
    fecha = row["fecha_inicio_actividades"]
    capital = row["capital_inicial_uf"]
    return EmpresaResponse.model_validate(
        {
            "id": UUID(str(row["id"])),
            "rut": str(row["rut"]),
            "razon_social": str(row["razon_social"]),
            "giro": None if row["giro"] is None else str(row["giro"]),
            "regimen_actual": str(row["regimen_actual"]),
            "fecha_inicio_actividades": fecha,
            "capital_inicial_uf": capital,
            "created_at": (
                created_at.isoformat()
                if hasattr(created_at, "isoformat")
                else str(created_at)
            ),
        }
    )


@router.post(
    "",
    response_model=EmpresaResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_empresa(
    payload: CreateEmpresaRequest,
    tenancy: Tenancy = Depends(current_tenancy),
    session: AsyncSession = Depends(get_db_session),
) -> EmpresaResponse:
    if tenancy.role not in _ALLOWED_CREATE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Tu rol no puede crear empresas. Solo owner, cfo o "
                "accountant_lead pueden registrar empresas en el workspace."
            ),
        )
    try:
        result = await session.execute(
            text(
                """
                insert into core.empresas
                    (workspace_id, rut, razon_social, giro,
                     regimen_actual, fecha_inicio_actividades,
                     capital_inicial_uf)
                values
                    (:ws, :rut, :razon, :giro,
                     :regimen, :fecha_inicio, :capital)
                returning id, rut, razon_social, giro, regimen_actual,
                          fecha_inicio_actividades, capital_inicial_uf,
                          created_at
                """
            ),
            {
                "ws": str(tenancy.workspace_id),
                "rut": payload.rut,
                "razon": payload.razon_social,
                "giro": payload.giro,
                "regimen": payload.regimen_actual,
                "fecha_inicio": payload.fecha_inicio_actividades,
                "capital": payload.capital_inicial_uf,
            },
        )
    except Exception as exc:
        # Unique violation (workspace_id, rut) → 409.
        if "empresas_workspace_id_rut_key" in str(exc):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Ya existe una empresa con RUT {payload.rut} en "
                    "este workspace."
                ),
            ) from exc
        raise

    row = result.mappings().one()
    empresa = _row_to_empresa(dict(row))
    await log_audit(
        session,
        workspace_id=tenancy.workspace_id,
        user_id=tenancy.user_id,
        action="create",
        resource_type="empresa",
        resource_id=empresa.id,
        empresa_id=empresa.id,
        metadata={
            "rut_masked": mask_rut(payload.rut),
            "regimen_actual": payload.regimen_actual,
        },
    )
    return empresa


@router.get("", response_model=EmpresasListResponse)
async def list_empresas(
    _tenancy: Tenancy = Depends(current_tenancy),
    session: AsyncSession = Depends(get_db_session),
) -> EmpresasListResponse:
    """Lista empresas visibles bajo RLS, ordenadas por created_at desc."""
    result = await session.execute(
        text(
            """
            select id, rut, razon_social, giro, regimen_actual,
                   fecha_inicio_actividades, capital_inicial_uf,
                   created_at
              from core.empresas
             where deleted_at is null
             order by created_at desc
            """
        )
    )
    empresas = [_row_to_empresa(dict(r)) for r in result.mappings().all()]
    return EmpresasListResponse(empresas=empresas)
