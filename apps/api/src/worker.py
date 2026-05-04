"""Celery worker app — schedule + tareas batch.

Levantar el worker:

    celery -A src.worker worker --loglevel=info -B

`-B` activa el beat scheduler embebido. Para producción corremos
worker y beat en services separados de Render para no perder beats
si el worker reinicia.

Sin REDIS_URL, importar este módulo es seguro pero `current_app.send_task`
fallará. La función `register_tasks_dryrun()` permite probar las tareas
sin broker.
"""

from __future__ import annotations

from celery import Celery  # type: ignore[import-untyped]
from celery.schedules import crontab  # type: ignore[import-untyped]

from src.config import settings


def _make_celery() -> Celery:
    broker = settings.redis_url or "memory://"
    app = Celery("renteo", broker=broker, backend=broker)
    app.conf.update(
        timezone="America/Santiago",
        enable_utc=True,
        task_acks_late=True,
        worker_prefetch_multiplier=1,
        task_default_retry_delay=30,
        # Retry hasta 3 veces ante errores transientes (DB / Redis).
        task_default_max_retries=3,
        task_track_started=True,
    )
    # Beat schedule: 03:00 CL todas las noches → evaluar alertas de
    # todos los workspaces. Si más adelante agregamos watchdog SII,
    # entra como tarea adicional con su propio cron.
    app.conf.beat_schedule = {
        "alertas-batch-nocturno": {
            "task": "src.tasks.alertas.evaluate_all_workspaces",
            "schedule": crontab(hour=3, minute=0),
            "options": {"queue": "default"},
        },
    }
    # Auto-discover tasks bajo src.tasks.*
    app.autodiscover_tasks(["src.tasks"])
    return app


app = _make_celery()
