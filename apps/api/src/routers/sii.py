"""Sincronización con SII — track skill 4 (MVP).

Endpoints:
- POST /api/empresas/{id}/sync-sii     dispara sincronización RCV de
                                       los últimos N meses contra el
                                       proveedor activo (mock por
                                       default; SimpleAPI cuando el
                                       feature flag lo apunta).
- GET  /api/empresas/{id}/sync-status  devuelve la última sync y un
                                       resumen de RCV/F29/F22 cargados.

Reglas (skill 4):
- workspace_id y empresa_id se derivan del JWT y del row de
  core.empresas; nunca del payload.
- Llamadas se hacen con `service_session` para escribir en
  tax_data.* y en sii_sync_log; los SELECTs usan tenant_session
  para que RLS filtre por workspace.
- El RUT se enmascara en logs (`mask_rut`).
- Si el proveedor lanza SiiUnavailable / SiiAuthError / SiiTimeout,
  el handler global de main.py los mapea a HTTP 503 / 502 / 504.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.tenancy import Tenancy, current_tenancy
from src.db import get_db_session, service_session
from src.domain.sii.adapter import RcvLine
from src.domain.sii.factory import make_sii_client, resolve_sii_provider
from src.lib.audit import log_audit, mask_rut
from src.lib.errors import SiiAuthError, SiiTimeout, SiiUnavailable

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/empresas", tags=["sii"])


class SyncSiiRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    months: int = Field(default=12, ge=1, le=24)


class SyncSiiResponse(BaseModel):
    sync_id: UUID
    provider: str
    period_from: str
    period_to: str
    rcv_rows_inserted: int
    rcv_rows_total: int
    status: str


class SyncStatusResponse(BaseModel):
    empresa_id: UUID
    last_sync_at: str | None
    last_sync_status: str | None
    last_sync_provider: str | None
    rcv_rows_total: int
    f29_periodos_total: int
    f22_anios_total: int


_ALLOWED_SYNC_ROLES = frozenset(
    {"owner", "cfo", "accountant_lead", "accountant_staff"}
)


def _months_window(end: date, n: int) -> list[str]:
    """Devuelve los últimos `n` meses como lista YYYY-MM, en orden
    cronológico ascendente, terminando en el mes anterior a `end`."""
    periods: list[str] = []
    cursor = date(end.year, end.month, 1) - timedelta(days=1)
    for _ in range(n):
        periods.append(f"{cursor.year:04d}-{cursor.month:02d}")
        cursor = date(cursor.year, cursor.month, 1) - timedelta(days=1)
    periods.reverse()
    return periods


async def _fetch_empresa(
    session: AsyncSession, empresa_id: UUID
) -> tuple[UUID, str, str]:
    """Recupera (workspace_id, rut, razon_social) bajo RLS."""
    result = await session.execute(
        text(
            """
            select workspace_id, rut, razon_social
              from core.empresas
             where id = :id
               and deleted_at is null
            """
        ),
        {"id": str(empresa_id)},
    )
    row = result.first()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="empresa no encontrada",
        )
    return UUID(str(row[0])), str(row[1]), str(row[2])


async def _persist_rcv(
    session: AsyncSession,
    *,
    workspace_id: UUID,
    empresa_id: UUID,
    lines: list[RcvLine],
) -> int:
    """Inserta las líneas RCV. Idempotencia: borramos las líneas previas
    de los períodos sincronizados antes de insertar las nuevas. Esto
    evita duplicados al reintentar y mantiene un snapshot consistente
    del RCV para esos meses."""
    if not lines:
        return 0
    periods = sorted({line.period for line in lines})
    await session.execute(
        text(
            """
            delete from tax_data.rcv_lines
             where empresa_id = :emp
               and period = any(cast(:periods as text[]))
            """
        ),
        {"emp": str(empresa_id), "periods": periods},
    )
    for line in lines:
        await session.execute(
            text(
                """
                insert into tax_data.rcv_lines
                    (workspace_id, empresa_id, period, tipo,
                     neto, iva, total, categoria)
                values
                    (:ws, :emp, :period, :tipo,
                     :neto, :iva, :total, :categoria)
                """
            ),
            {
                "ws": str(workspace_id),
                "emp": str(empresa_id),
                "period": line.period,
                "tipo": line.tipo,
                "neto": line.neto,
                "iva": line.iva,
                "total": line.total,
                "categoria": None,
            },
        )
    return len(lines)


async def _open_sync_log(
    session: AsyncSession,
    *,
    workspace_id: UUID,
    empresa_id: UUID,
    provider: str,
    period_from: str,
    period_to: str,
    user_id: UUID,
) -> UUID:
    result = await session.execute(
        text(
            """
            insert into tax_data.sii_sync_log
                (workspace_id, empresa_id, provider, kind, status,
                 period_from, period_to, created_by)
            values
                (:ws, :emp, :prov, 'rcv', 'started',
                 :pf, :pt, :uid)
            returning id
            """
        ),
        {
            "ws": str(workspace_id),
            "emp": str(empresa_id),
            "prov": provider,
            "pf": period_from,
            "pt": period_to,
            "uid": str(user_id),
        },
    )
    return UUID(str(result.scalar_one()))


async def _close_sync_log(
    session: AsyncSession,
    *,
    sync_id: UUID,
    status_value: str,
    rows_inserted: int,
    error: Exception | None = None,
) -> None:
    await session.execute(
        text(
            """
            update tax_data.sii_sync_log
               set status = :status,
                   rows_inserted = :rows,
                   finished_at = now(),
                   error_class = :ec,
                   error_message = :em
             where id = :id
            """
        ),
        {
            "id": str(sync_id),
            "status": status_value,
            "rows": rows_inserted,
            "ec": type(error).__name__ if error else None,
            "em": str(error) if error else None,
        },
    )


@router.post(
    "/{empresa_id}/sync-sii",
    response_model=SyncSiiResponse,
)
async def sync_sii(
    empresa_id: UUID,
    payload: SyncSiiRequest | None = None,
    tenancy: Tenancy = Depends(current_tenancy),
    session: AsyncSession = Depends(get_db_session),
) -> SyncSiiResponse:
    if tenancy.role not in _ALLOWED_SYNC_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Tu rol no puede sincronizar con SII. Solo roles con "
                "acceso de escritura tributaria pueden iniciar la sync."
            ),
        )

    workspace_id, rut, razon_social = await _fetch_empresa(
        session, empresa_id
    )
    months = (payload or SyncSiiRequest()).months
    periods = _months_window(date.today(), months)
    period_from = periods[0]
    period_to = periods[-1]

    # Toda la escritura va por service_session (RLS bypass).
    async with service_session() as svc:
        provider = await resolve_sii_provider(svc)
        sync_id = await _open_sync_log(
            svc,
            workspace_id=workspace_id,
            empresa_id=empresa_id,
            provider=provider,
            period_from=period_from,
            period_to=period_to,
            user_id=tenancy.user_id,
        )

    logger.info(
        "sii_sync_started",
        sync_id=str(sync_id),
        empresa_id=str(empresa_id),
        rut=mask_rut(rut),
        provider=provider,
        periods=len(periods),
    )

    client = make_sii_client(provider)
    all_lines: list[RcvLine] = []
    try:
        for period in periods:
            lines = await client.fetch_rcv(rut=rut, period=period)
            all_lines.extend(lines)
    except (SiiUnavailable, SiiAuthError, SiiTimeout) as exc:
        async with service_session() as svc:
            await _close_sync_log(
                svc,
                sync_id=sync_id,
                status_value="failed",
                rows_inserted=0,
                error=exc,
            )
        logger.warning(
            "sii_sync_failed",
            sync_id=str(sync_id),
            empresa_id=str(empresa_id),
            error_type=type(exc).__name__,
        )
        raise

    async with service_session() as svc:
        rows_inserted = await _persist_rcv(
            svc,
            workspace_id=workspace_id,
            empresa_id=empresa_id,
            lines=all_lines,
        )
        await _close_sync_log(
            svc,
            sync_id=sync_id,
            status_value="success",
            rows_inserted=rows_inserted,
        )

    await log_audit(
        session,
        workspace_id=tenancy.workspace_id,
        user_id=tenancy.user_id,
        action="sync",
        resource_type="sii",
        resource_id=sync_id,
        empresa_id=empresa_id,
        metadata={
            "rut_masked": mask_rut(rut),
            "razon_social": razon_social,
            "provider": provider,
            "period_from": period_from,
            "period_to": period_to,
            "rows_inserted": rows_inserted,
        },
    )

    logger.info(
        "sii_sync_completed",
        sync_id=str(sync_id),
        empresa_id=str(empresa_id),
        rows_inserted=rows_inserted,
    )

    return SyncSiiResponse(
        sync_id=sync_id,
        provider=provider,
        period_from=period_from,
        period_to=period_to,
        rcv_rows_inserted=rows_inserted,
        rcv_rows_total=len(all_lines),
        status="success",
    )


@router.get(
    "/{empresa_id}/sync-status",
    response_model=SyncStatusResponse,
)
async def sync_status(
    empresa_id: UUID,
    _tenancy: Tenancy = Depends(current_tenancy),
    session: AsyncSession = Depends(get_db_session),
) -> SyncStatusResponse:
    # Verifica acceso bajo RLS.
    await _fetch_empresa(session, empresa_id)

    last = await session.execute(
        text(
            """
            select started_at, status, provider
              from tax_data.sii_sync_log
             where empresa_id = :emp
             order by started_at desc
             limit 1
            """
        ),
        {"emp": str(empresa_id)},
    )
    last_row = last.first()

    counts: dict[str, Any] = {}
    for kind, sql in (
        ("rcv", "select count(*) from tax_data.rcv_lines where empresa_id = :emp"),
        ("f29", "select count(*) from tax_data.f29_periodos where empresa_id = :emp"),
        ("f22", "select count(*) from tax_data.f22_anios where empresa_id = :emp"),
    ):
        r = await session.execute(text(sql), {"emp": str(empresa_id)})
        counts[kind] = int(r.scalar_one())

    return SyncStatusResponse(
        empresa_id=empresa_id,
        last_sync_at=(
            last_row[0].isoformat()
            if last_row and hasattr(last_row[0], "isoformat")
            else None
        ),
        last_sync_status=str(last_row[1]) if last_row else None,
        last_sync_provider=str(last_row[2]) if last_row else None,
        rcv_rows_total=counts["rcv"],
        f29_periodos_total=counts["f29"],
        f22_anios_total=counts["f22"],
    )
