"""Onboarding empresa desde RUT vía SII (skill 4 + skill 9 closure).

Un solo endpoint compone:
  1. Validación módulo 11 del RUT.
  2. lookup_taxpayer (SII) para obtener razón social + giro + fecha
     inicio actividades. Si SII no responde, usa el fallback opcional
     que el contador puede haber tipeado.
  3. fetch_f22 del año tributario anterior para detectar régimen real.
     Si no hay F22 presentado, queda 'desconocido'.
  4. INSERT en core.empresas (validando role + duplicado).
  5. Sincronización inicial RCV últimos 12 meses (reusa la lógica de
     sii.sync_sii sin pasar por el endpoint).
  6. Audit log.

Returns: empresa creada + resumen del lookup + resumen de sync.

Reglas:
- workspace_id viene del JWT (nunca del payload).
- RUT viaja enmascarado en logs y audit.
- Si el lookup falla y no hay fallback, devuelve 422 — no se crea
  empresa con datos inventados.
"""

from __future__ import annotations

from datetime import date
from typing import Literal
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.tenancy import Tenancy, current_tenancy
from src.db import get_db_session, service_session
from src.domain.sii.adapter import RcvLine
from src.domain.sii.factory import make_sii_client, resolve_sii_provider
from src.lib.audit import log_audit, mask_rut
from src.lib.errors import SiiAuthError, SiiTimeout, SiiUnavailable
from src.lib.rut import InvalidRutError, validate_rut
from src.routers.sii import (
    _close_sync_log,
    _months_window,
    _open_sync_log,
    _persist_rcv,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/empresas", tags=["empresas-from-rut"])

_ALLOWED_ONBOARDING_ROLES = frozenset(
    {"owner", "cfo", "accountant_lead", "accountant_staff"}
)

RegimenActual = Literal[
    "14_a", "14_d_3", "14_d_8", "presunta", "desconocido"
]


class FromRutRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rut: str = Field(min_length=3, max_length=12)
    razon_social_fallback: str | None = Field(
        default=None,
        max_length=160,
        description=(
            "Si el SII no responde, se usa este nombre. Si SII responde, "
            "se ignora (fuente de verdad = SII)."
        ),
    )
    sync_meses: int = Field(default=12, ge=1, le=24)

    @field_validator("rut")
    @classmethod
    def _validate_rut(cls, v: str) -> str:
        try:
            return validate_rut(v)
        except InvalidRutError as exc:
            raise ValueError(str(exc)) from exc


class LookupSummary(BaseModel):
    razon_social: str
    giro: str | None
    fecha_inicio_actividades: str | None
    activo_en_sii: bool
    via_sii: bool


class SyncSummary(BaseModel):
    provider: str
    rcv_rows_inserted: int
    period_from: str
    period_to: str
    sync_id: UUID
    status: str


class FromRutResponse(BaseModel):
    empresa_id: UUID
    rut: str
    razon_social: str
    giro: str | None
    regimen_actual: RegimenActual
    fecha_inicio_actividades: str | None
    lookup: LookupSummary
    sync: SyncSummary | None
    warnings: list[str]


def _regimen_from_f22(declarado: str | None) -> RegimenActual:
    if declarado in ("14_a", "14_d_3", "14_d_8", "presunta"):
        return declarado  # type: ignore[return-value]
    return "desconocido"


@router.post(
    "/from-rut",
    response_model=FromRutResponse,
    status_code=status.HTTP_201_CREATED,
)
async def empresa_from_rut(
    payload: FromRutRequest,
    tenancy: Tenancy = Depends(current_tenancy),
    session: AsyncSession = Depends(get_db_session),
) -> FromRutResponse:
    if tenancy.role not in _ALLOWED_ONBOARDING_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Tu rol no puede dar de alta empresas en el workspace."
            ),
        )

    rut = payload.rut
    warnings: list[str] = []
    logger.info(
        "empresa_from_rut_started",
        rut=mask_rut(rut),
        workspace_id=str(tenancy.workspace_id),
    )

    # ----- 1) Lookup taxpayer ------------------------------------------------
    async with service_session() as svc:
        provider = await resolve_sii_provider(svc)
    client = make_sii_client(provider)
    lookup_via_sii = True
    razon_social: str | None = None
    giro: str | None = None
    fecha_inicio: date | None = None
    activo_sii = True
    try:
        info = await client.lookup_taxpayer(rut=rut)
    except (SiiUnavailable, SiiAuthError, SiiTimeout) as exc:
        info = None
        lookup_via_sii = False
        warnings.append(
            f"SII no respondió ({type(exc).__name__}); se usa razón "
            "social provista manualmente."
        )

    if info is None and lookup_via_sii:
        # SII respondió pero el RUT no existe en su padrón.
        if not payload.razon_social_fallback:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    "RUT no encontrado en SII y sin razón social de "
                    "respaldo. Vuelve a intentar con razon_social_fallback."
                ),
            )
        warnings.append(
            "RUT no figura en padrón SII; se usa razón social provista "
            "manualmente."
        )
        lookup_via_sii = False

    if info is not None:
        razon_social = info.razon_social
        giro = info.giro
        fecha_inicio = info.fecha_inicio_actividades
        activo_sii = info.activo
        if not info.activo:
            warnings.append(
                "El RUT figura como NO ACTIVO en SII. Verifica antes "
                "de operar la empresa en Renteo."
            )
    elif payload.razon_social_fallback:
        razon_social = payload.razon_social_fallback
    else:
        # No SII y sin fallback → ya retornado más arriba.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Sin información de SII ni razón social de respaldo. "
                "Vuelve a intentar incluyendo razon_social_fallback."
            ),
        )

    # ----- 2) Detectar régimen vía F22 (último año disponible) --------------
    target_year = date.today().year - 1
    regimen_actual: RegimenActual = "desconocido"
    try:
        f22 = await client.fetch_f22(rut=rut, tax_year=target_year)
    except (SiiUnavailable, SiiAuthError, SiiTimeout):
        f22 = None
        warnings.append(
            f"No se pudo leer F22 {target_year} para detectar régimen; "
            "queda como 'desconocido'."
        )
    if f22 is not None:
        regimen_actual = _regimen_from_f22(f22.regimen_declarado)

    # ----- 3) INSERT empresa ------------------------------------------------
    try:
        result = await session.execute(
            text(
                """
                insert into core.empresas
                    (workspace_id, rut, razon_social, giro,
                     regimen_actual, fecha_inicio_actividades)
                values
                    (:ws, :rut, :razon, :giro, :regimen, :fecha)
                returning id
                """
            ),
            {
                "ws": str(tenancy.workspace_id),
                "rut": rut,
                "razon": razon_social,
                "giro": giro,
                "regimen": regimen_actual,
                "fecha": fecha_inicio,
            },
        )
    except Exception as exc:
        if "empresas_workspace_id_rut_key" in str(exc):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Ya existe una empresa con RUT {rut} en este "
                    "workspace."
                ),
            ) from exc
        raise

    empresa_id = UUID(str(result.scalar_one()))

    # El sync_log abre una conexión separada (service_session); para
    # que la FK contra core.empresas se resuelva, la fila recién
    # insertada debe estar commiteada en su propia transacción antes
    # de abrir la otra conexión. La commit explícita del tenant
    # session cierra la transacción del get_db_session sin afectar el
    # context manager que la envuelve.
    await session.commit()

    # ----- 4) Sync inicial RCV (últimos N meses) ----------------------------
    sync: SyncSummary | None = None
    periods = _months_window(date.today(), payload.sync_meses)
    period_from = periods[0]
    period_to = periods[-1]
    async with service_session() as svc:
        sync_id = await _open_sync_log(
            svc,
            workspace_id=tenancy.workspace_id,
            empresa_id=empresa_id,
            provider=provider,
            period_from=period_from,
            period_to=period_to,
            user_id=tenancy.user_id,
        )

    all_lines: list[RcvLine] = []
    sync_failed_exc: Exception | None = None
    try:
        for period in periods:
            lines = await client.fetch_rcv(rut=rut, period=period)
            all_lines.extend(lines)
    except (SiiUnavailable, SiiAuthError, SiiTimeout) as exc:
        sync_failed_exc = exc

    if sync_failed_exc is not None:
        async with service_session() as svc:
            await _close_sync_log(
                svc,
                sync_id=sync_id,
                status_value="failed",
                rows_inserted=0,
                error=sync_failed_exc,
            )
        warnings.append(
            f"Sincronización RCV inicial falló ({type(sync_failed_exc).__name__}); "
            "puedes reintentarla desde el detalle de la empresa."
        )
        sync = SyncSummary(
            sync_id=sync_id,
            provider=provider,
            period_from=period_from,
            period_to=period_to,
            rcv_rows_inserted=0,
            status="failed",
        )
    else:
        async with service_session() as svc:
            rows_inserted = await _persist_rcv(
                svc,
                workspace_id=tenancy.workspace_id,
                empresa_id=empresa_id,
                lines=all_lines,
            )
            await _close_sync_log(
                svc,
                sync_id=sync_id,
                status_value="success",
                rows_inserted=rows_inserted,
            )
        sync = SyncSummary(
            sync_id=sync_id,
            provider=provider,
            period_from=period_from,
            period_to=period_to,
            rcv_rows_inserted=rows_inserted,
            status="success",
        )

    # Audit log via service_session: el tenant session ya commiteó
    # (perdió `request.jwt.claims`), por lo que un INSERT con la
    # policy WITH CHECK fallaría sin claims. service_session bypasea
    # RLS y persiste con el workspace_id derivado del JWT verificado.
    async with service_session() as svc:
        await log_audit(
            svc,
            workspace_id=tenancy.workspace_id,
            user_id=tenancy.user_id,
            action="onboarding_from_rut",
            resource_type="empresa",
            resource_id=empresa_id,
            empresa_id=empresa_id,
            metadata={
                "rut_masked": mask_rut(rut),
                "razon_social": razon_social,
                "regimen_actual": regimen_actual,
                "via_sii": lookup_via_sii,
                "sync_status": sync.status if sync else None,
                "rcv_rows_inserted": (
                    sync.rcv_rows_inserted if sync else 0
                ),
            },
        )

    logger.info(
        "empresa_from_rut_completed",
        empresa_id=str(empresa_id),
        rut=mask_rut(rut),
        regimen_actual=regimen_actual,
        via_sii=lookup_via_sii,
    )

    return FromRutResponse(
        empresa_id=empresa_id,
        rut=rut,
        razon_social=razon_social or "",
        giro=giro,
        regimen_actual=regimen_actual,
        fecha_inicio_actividades=(
            fecha_inicio.isoformat() if fecha_inicio else None
        ),
        lookup=LookupSummary(
            razon_social=razon_social or "",
            giro=giro,
            fecha_inicio_actividades=(
                fecha_inicio.isoformat() if fecha_inicio else None
            ),
            activo_en_sii=activo_sii,
            via_sii=lookup_via_sii,
        ),
        sync=sync,
        warnings=warnings,
    )
