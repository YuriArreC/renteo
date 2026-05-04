"""Tarea Celery: watchdog legislativo (skill 11 closure).

Cada noche corre un `LegislativeMonitor` (mock por default; HTTP
real bajo feature flag track 11d), trae los hits de los últimos 7
días y persiste en `tax_rules.legislative_alerts` con dedup por
(source, source_id).

Idempotente: la segunda corrida del mismo día no agrega filas.
"""

from __future__ import annotations

import asyncio
import json
from datetime import date, timedelta
from typing import Any

import structlog
from sqlalchemy import text

from src.db import service_session
from src.domain.legislation.monitor import (
    LegislativeAlert,
    LegislativeMonitor,
    MockLegislativeMonitor,
)
from src.worker import app

logger = structlog.get_logger(__name__)

# Ventana de retroactividad para capturar publicaciones que pudieron
# haberse caído (worker reiniciado, Sentry alertando, etc.).
_LOOKBACK_DAYS = 7


def _make_monitor() -> LegislativeMonitor:
    """Factory: por ahora solo mock. Track 11d agrega Real con flag."""
    return MockLegislativeMonitor()


@app.task(name="src.tasks.legislation.check_legislation")  # type: ignore[untyped-decorator]
def check_legislation_task() -> dict[str, Any]:
    """Entrypoint Celery: ejecuta la corrutina async."""
    return asyncio.run(_check_legislation())


async def _check_legislation() -> dict[str, Any]:
    """Corre el monitor y persiste hits nuevos con dedup."""
    monitor = _make_monitor()
    since = date.today() - timedelta(days=_LOOKBACK_DAYS)
    alerts = await monitor.check_all(since=since)
    summary = await _persist_alerts(alerts, monitor_name=monitor.name)
    logger.info(
        "watchdog_legislativo_done",
        monitor=monitor.name,
        since=since.isoformat(),
        candidates=len(alerts),
        nuevos=summary["nuevos"],
        existentes=summary["existentes"],
    )
    return summary


async def _persist_alerts(
    alerts: list[LegislativeAlert], *, monitor_name: str
) -> dict[str, Any]:
    """INSERT con ON CONFLICT DO NOTHING para dedup por unique
    (source, source_id). Devuelve conteo de nuevos vs ya existentes."""
    nuevos = 0
    existentes = 0
    if not alerts:
        return {
            "monitor": monitor_name,
            "nuevos": 0,
            "existentes": 0,
        }
    async with service_session() as svc:
        for alert in alerts:
            result = await svc.execute(
                text(
                    """
                    insert into tax_rules.legislative_alerts
                        (source, source_id, title, summary, url,
                         publication_date, target_domain, target_key,
                         propuesta_diff)
                    values
                        (:source, :sid, :title, :summary, :url,
                         :pub, :tdom, :tkey, cast(:diff as jsonb))
                    on conflict (source, source_id) do nothing
                    returning id
                    """
                ),
                {
                    "source": alert.source,
                    "sid": alert.source_id,
                    "title": alert.title,
                    "summary": alert.summary,
                    "url": alert.url,
                    "pub": alert.publication_date,
                    "tdom": alert.target_domain,
                    "tkey": alert.target_key,
                    "diff": json.dumps(alert.propuesta_diff),
                },
            )
            row = result.first()
            if row is None:
                existentes += 1
            else:
                nuevos += 1
    return {
        "monitor": monitor_name,
        "nuevos": nuevos,
        "existentes": existentes,
    }
