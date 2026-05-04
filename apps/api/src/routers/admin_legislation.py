"""Panel admin del watchdog legislativo (skill 11 closure).

Endpoints (requieren `internal_admin`):
- GET   /api/admin/legislative-alerts        list (filters status/source).
- PATCH /api/admin/legislative-alerts/{id}   transición de estado.
- POST  /api/admin/legislative-alerts/run    dispara el watchdog ad-hoc
                                             (útil para demo / testing
                                             sin esperar al cron 04:00).

El listado y mutaciones corren con `service_session`: la tabla no
tiene policy de SELECT para authenticated (escape-hatch del skill 11
para tablas exclusivas del backoffice).
"""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

from src.auth.internal_admin import require_internal_admin
from src.db import service_session
from src.tasks.legislation import _check_legislation

router = APIRouter(
    prefix="/api/admin/legislative-alerts", tags=["admin"]
)


AlertStatus = Literal["open", "dismissed", "ignored", "drafted"]
AlertSource = Literal[
    "dof",
    "sii_circular",
    "sii_oficio",
    "sii_resolucion",
    "presupuestos",
]


class AlertSummary(BaseModel):
    id: UUID
    source: AlertSource
    source_id: str
    title: str
    summary: str | None
    url: str | None
    publication_date: str
    status: AlertStatus
    target_domain: str | None
    target_key: str | None
    propuesta_diff: dict[str, Any]
    drafted_rule_set_id: UUID | None
    reviewed_by: UUID | None
    reviewed_at: str | None
    review_note: str | None
    created_at: str
    updated_at: str


class AlertListResponse(BaseModel):
    records: list[AlertSummary]


class AlertPatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: AlertStatus
    review_note: str | None = Field(default=None, max_length=2000)


class WatchdogRunResponse(BaseModel):
    monitor: str
    nuevos: int
    existentes: int


def _row_to_alert(row: dict[str, Any]) -> AlertSummary:
    pub = row["publication_date"]
    reviewed = row["reviewed_at"]
    return AlertSummary(
        id=UUID(str(row["id"])),
        source=row["source"],
        source_id=str(row["source_id"]),
        title=str(row["title"]),
        summary=(
            str(row["summary"]) if row["summary"] is not None else None
        ),
        url=str(row["url"]) if row["url"] is not None else None,
        publication_date=(
            pub.isoformat() if hasattr(pub, "isoformat") else str(pub)
        ),
        status=row["status"],
        target_domain=(
            str(row["target_domain"])
            if row["target_domain"] is not None
            else None
        ),
        target_key=(
            str(row["target_key"])
            if row["target_key"] is not None
            else None
        ),
        propuesta_diff=dict(row["propuesta_diff"] or {}),
        drafted_rule_set_id=(
            UUID(str(row["drafted_rule_set_id"]))
            if row["drafted_rule_set_id"] is not None
            else None
        ),
        reviewed_by=(
            UUID(str(row["reviewed_by"]))
            if row["reviewed_by"] is not None
            else None
        ),
        reviewed_at=(
            reviewed.isoformat()
            if hasattr(reviewed, "isoformat")
            else None
        ),
        review_note=(
            str(row["review_note"])
            if row["review_note"] is not None
            else None
        ),
        created_at=row["created_at"].isoformat(),
        updated_at=row["updated_at"].isoformat(),
    )


@router.get("", response_model=AlertListResponse)
async def list_alerts(
    status_filter: AlertStatus | None = None,
    source: AlertSource | None = None,
    limit: int = 100,
    _admin: UUID = Depends(require_internal_admin),
) -> AlertListResponse:
    if limit < 1 or limit > 500:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="limit debe estar entre 1 y 500",
        )
    # Cast explícito de los parámetros opcionales: cuando son NULL,
    # asyncpg necesita el tipo declarado para preparar el statement
    # (AmbiguousParameterError si solo viaja `:st is null`).
    async with service_session() as svc:
        result = await svc.execute(
            text(
                """
                select id, source, source_id, title, summary, url,
                       publication_date, status, target_domain,
                       target_key, propuesta_diff, drafted_rule_set_id,
                       reviewed_by, reviewed_at, review_note,
                       created_at, updated_at
                  from tax_rules.legislative_alerts
                 where (cast(:st as text) is null
                        or status = cast(:st as text))
                   and (cast(:src as text) is null
                        or source = cast(:src as text))
                 order by publication_date desc, created_at desc
                 limit :lim
                """
            ),
            {
                "st": status_filter,
                "src": source,
                "lim": limit,
            },
        )
        records = [
            _row_to_alert(dict(r)) for r in result.mappings().all()
        ]
    return AlertListResponse(records=records)


@router.patch("/{alert_id}", response_model=AlertSummary)
async def patch_alert(
    alert_id: UUID,
    payload: AlertPatchRequest,
    admin_user_id: UUID = Depends(require_internal_admin),
) -> AlertSummary:
    """Transición de estado: open → dismissed | ignored | drafted.

    El revisor queda registrado en reviewed_by + reviewed_at + nota."""
    async with service_session() as svc:
        result = await svc.execute(
            text(
                """
                update tax_rules.legislative_alerts
                   set status = :st,
                       reviewed_by = :uid,
                       reviewed_at = now(),
                       review_note = :note
                 where id = :id
                returning id, source, source_id, title, summary, url,
                          publication_date, status, target_domain,
                          target_key, propuesta_diff,
                          drafted_rule_set_id, reviewed_by,
                          reviewed_at, review_note,
                          created_at, updated_at
                """
            ),
            {
                "id": str(alert_id),
                "st": payload.status,
                "uid": str(admin_user_id),
                "note": payload.review_note,
            },
        )
        row = result.mappings().first()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alerta legislativa no encontrada.",
        )
    return _row_to_alert(dict(row))


@router.post("/run", response_model=WatchdogRunResponse)
async def run_watchdog(
    _admin: UUID = Depends(require_internal_admin),
) -> WatchdogRunResponse:
    """Ejecuta el watchdog on-demand. Idempotente — la segunda
    invocación no agrega filas duplicadas."""
    summary = await _check_legislation()
    return WatchdogRunResponse(
        monitor=str(summary["monitor"]),
        nuevos=int(summary["nuevos"]),
        existentes=int(summary["existentes"]),
    )
