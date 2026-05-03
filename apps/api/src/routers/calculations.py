"""Endpoints de cálculo del motor tributario (placeholder).

🟡 Los valores devueltos son placeholder hasta firma del contador socio.
Cada response incluye un `disclaimer` explícito y la `fuente_legal` que
viene del seed (que también dice PLACEHOLDER —). El frontend renderea
el disclaimer prominentemente.

Auth: requiere usuario autenticado pero NO requiere workspace
(las tablas tax_params son globales, RLS abierta a authenticated).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.tenancy import current_user
from src.db import get_db_session
from src.domain.tax_engine.idpc import Regimen, compute_idpc
from src.domain.tax_engine.igc import compute_igc
from src.domain.tax_engine.ppm import PPMRegimen, compute_ppm

router = APIRouter(prefix="/api/calc", tags=["calc"])


PLACEHOLDER_DISCLAIMER = (
    "🟡 Resultado calculado con parámetros tributarios PLACEHOLDER "
    "pendientes de validación por contador socio. NO usar para decisiones "
    "tributarias reales hasta que se publique la versión firmada."
)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class CalculationResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    value: Decimal
    currency: Literal["CLP"] = "CLP"
    tax_year: int
    fuente_legal: str
    disclaimer: str = PLACEHOLDER_DISCLAIMER


class IdpcRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    regimen: Regimen
    tax_year: int = Field(ge=2024, le=2030)
    rli: Decimal = Field(description="Renta Líquida Imponible en CLP")


class IgcRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tax_year: int = Field(ge=2024, le=2030)
    base_pesos: Decimal = Field(
        description="Base afecta a IGC del dueño en CLP",
        ge=0,
    )


class PpmRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    regimen: PPMRegimen
    tax_year: int = Field(ge=2024, le=2030)
    ingresos_mes_pesos: Decimal = Field(ge=0)
    ingresos_anio_anterior_uf: Decimal = Field(ge=0)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _fuente_idpc(
    session: AsyncSession, regimen: str, tax_year: int
) -> str:
    result = await session.execute(
        text(
            "select fuente_legal from tax_params.idpc_rates "
            "where tax_year = :y and regimen = :r"
        ),
        {"y": tax_year, "r": regimen},
    )
    row = result.first()
    return str(row[0]) if row else "(sin fuente)"


async def _fuente_igc(session: AsyncSession, tax_year: int) -> str:
    # IGC brackets no tienen fuente_legal por fila; la cita corresponde
    # a tax_year_params + art. 52 LIR. Usamos la fuente del año.
    result = await session.execute(
        text(
            "select fuente_legal from tax_params.tax_year_params "
            "where tax_year = :y"
        ),
        {"y": tax_year},
    )
    row = result.first()
    return f"art. 52 LIR. {row[0] if row else '(sin fuente)'}"


async def _fuente_ppm(
    session: AsyncSession, regimen: str, tax_year: int
) -> str:
    result = await session.execute(
        text(
            "select fuente_legal from tax_params.ppm_pyme_rates "
            "where tax_year = :y and regimen = :r"
        ),
        {"y": tax_year, "r": regimen},
    )
    row = result.first()
    return str(row[0]) if row else "(sin fuente)"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/idpc", response_model=CalculationResponse)
async def calc_idpc(
    payload: IdpcRequest,
    _user_id: UUID = Depends(current_user),
    session: AsyncSession = Depends(get_db_session),
) -> CalculationResponse:
    value = await compute_idpc(
        session,
        regimen=payload.regimen,
        tax_year=payload.tax_year,
        rli=payload.rli,
    )
    fuente = await _fuente_idpc(session, payload.regimen, payload.tax_year)
    return CalculationResponse(
        value=value, tax_year=payload.tax_year, fuente_legal=fuente
    )


@router.post("/igc", response_model=CalculationResponse)
async def calc_igc(
    payload: IgcRequest,
    _user_id: UUID = Depends(current_user),
    session: AsyncSession = Depends(get_db_session),
) -> CalculationResponse:
    value = await compute_igc(
        session, tax_year=payload.tax_year, base_pesos=payload.base_pesos
    )
    fuente = await _fuente_igc(session, payload.tax_year)
    return CalculationResponse(
        value=value, tax_year=payload.tax_year, fuente_legal=fuente
    )


@router.post("/ppm", response_model=CalculationResponse)
async def calc_ppm(
    payload: PpmRequest,
    _user_id: UUID = Depends(current_user),
    session: AsyncSession = Depends(get_db_session),
) -> CalculationResponse:
    value = await compute_ppm(
        session,
        regimen=payload.regimen,
        tax_year=payload.tax_year,
        ingresos_mes_pesos=payload.ingresos_mes_pesos,
        ingresos_anio_anterior_uf=payload.ingresos_anio_anterior_uf,
    )
    fuente = await _fuente_ppm(session, payload.regimen, payload.tax_year)
    return CalculationResponse(
        value=value, tax_year=payload.tax_year, fuente_legal=fuente
    )
