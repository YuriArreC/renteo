"""Tarea Celery: evaluación batch nocturna de alertas pre-cierre.

Recorre todos los workspaces activos y, para cada empresa con
diagnóstico previo (`core.recomendaciones` cambio_regimen), reusa
los inputs persistidos para alimentar el evaluador y persistir
alertas nuevas con dedup.

El task corre con `service_session` (sin RLS) porque actúa como el
sistema. La promesa de aislamiento se mantiene: cada alerta queda
con su `workspace_id` + `empresa_id`, y todos los lectores siguen
viéndolas a través de RLS.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import structlog
from sqlalchemy import text

from src.db import service_session
from src.domain.tax_engine.alertas import (
    AlertaCandidate,
    AlertaInputs,
    Regimen,
    evaluate_pre_cierre,
)
from src.domain.tax_engine.beneficios import get_beneficio
from src.lib.errors import MissingTaxYearParams
from src.worker import app

logger = structlog.get_logger(__name__)


_OPEN_ESTADOS = ("nueva", "vista")


@dataclass(frozen=True)
class WorkspaceBatchSummary:
    workspace_id: str
    empresas_evaluadas: int
    alertas_creadas: int
    alertas_existentes: int


@app.task(name="src.tasks.alertas.evaluate_all_workspaces")  # type: ignore[untyped-decorator]
def evaluate_all_workspaces_task() -> dict[str, Any]:
    """Entrypoint Celery: ejecuta la corrutina async."""
    return asyncio.run(_evaluate_all_workspaces())


async def _evaluate_all_workspaces() -> dict[str, Any]:
    """Recorre workspaces activos y dispara `_evaluate_one_workspace`
    para cada uno. Se ejecuta en serie (los volúmenes esperados al
    inicio son chicos; cuando cliente B tenga 50+ workspaces se
    paraleliza)."""
    async with service_session() as session:
        result = await session.execute(
            text(
                """
                select id from core.workspaces
                 where deleted_at is null
                """
            )
        )
        workspace_ids = [str(r[0]) for r in result.all()]

    summaries: list[dict[str, Any]] = []
    for ws_id in workspace_ids:
        try:
            summary = await _evaluate_one_workspace(ws_id)
            summaries.append(
                {
                    "workspace_id": summary.workspace_id,
                    "empresas_evaluadas": summary.empresas_evaluadas,
                    "alertas_creadas": summary.alertas_creadas,
                    "alertas_existentes": summary.alertas_existentes,
                }
            )
        except Exception as exc:
            logger.error(
                "evaluate_workspace_failed",
                workspace_id=ws_id,
                error=str(exc),
            )
    logger.info(
        "evaluate_all_workspaces_done",
        workspaces=len(workspace_ids),
        summaries=summaries,
    )
    return {
        "workspaces_procesados": len(workspace_ids),
        "summaries": summaries,
    }


async def _evaluate_one_workspace(
    workspace_id: str,
) -> WorkspaceBatchSummary:
    """Para cada empresa del workspace con diagnóstico previo, lee
    los inputs persistidos y persiste alertas nuevas con dedup."""
    creadas = 0
    existentes = 0
    empresas_evaluadas = 0

    async with service_session() as session:
        # Trae empresas con su última recomendación cambio_regimen
        # (necesitamos los inputs_snapshot para alimentar al
        # evaluador; sin diagnóstico previo no inventamos inputs).
        rows = await session.execute(
            text(
                """
                select distinct on (e.id)
                       e.id as empresa_id, e.regimen_actual,
                       r.tax_year, r.inputs_snapshot
                  from core.empresas e
                  join core.recomendaciones r on r.empresa_id = e.id
                 where e.workspace_id = :ws
                   and e.deleted_at is null
                   and r.tipo = 'cambio_regimen'
                 order by e.id, r.created_at desc
                """
            ),
            {"ws": workspace_id},
        )
        candidates_per_empresa: list[
            tuple[str, list[AlertaCandidate]]
        ] = []
        for row in rows.mappings().all():
            empresas_evaluadas += 1
            empresa_id = str(row["empresa_id"])
            regimen_db = str(row["regimen_actual"])
            inputs = row["inputs_snapshot"] or {}

            regimen: Regimen
            if regimen_db == "14_d_3":
                regimen = "14_d_3"
            elif regimen_db == "14_d_8":
                regimen = "14_d_8"
            else:
                regimen = "14_a"
            tpl = inputs.get("template") or {}
            tax_year = int(row["tax_year"])

            try:
                uf_clp = await get_beneficio(
                    session, key="uf_valor_clp", tax_year=tax_year
                )
            except MissingTaxYearParams:
                logger.warning(
                    "evaluate_skipped_no_uf",
                    workspace_id=workspace_id,
                    empresa_id=empresa_id,
                    tax_year=tax_year,
                )
                continue

            rli_uf = Decimal(
                str(tpl.get("rli_proyectada_anual_uf", "0"))
            )
            plan_pct = Decimal(str(tpl.get("plan_retiros_pct", "0")))
            rli_clp = (rli_uf * uf_clp).quantize(Decimal("0.01"))
            retiros_clp = (rli_clp * plan_pct).quantize(Decimal("0.01"))

            candidates = evaluate_pre_cierre(
                AlertaInputs(
                    regimen=regimen,
                    tax_year=tax_year,
                    rli_proyectada_pesos=rli_clp,
                    retiros_declarados_pesos=retiros_clp,
                )
            )
            candidates_per_empresa.append((empresa_id, candidates))

        # Dedup + persistencia.
        for empresa_id, candidates in candidates_per_empresa:
            if not candidates:
                continue
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
                    "ws": workspace_id,
                    "emp": empresa_id,
                    "estados": list(_OPEN_ESTADOS),
                    "tipos": [c.tipo for c in candidates],
                },
            )
            existing_tipos = {row[0] for row in existing.all()}
            for cand in candidates:
                if cand.tipo in existing_tipos:
                    existentes += 1
                    continue
                await session.execute(
                    text(
                        """
                        insert into core.alertas
                            (workspace_id, empresa_id, tipo, severidad,
                             titulo, descripcion, accion_recomendada,
                             fecha_limite)
                        values
                            (:ws, :emp, :tipo, :sev,
                             :titulo, :desc, :accion, :fecha)
                        """
                    ),
                    {
                        "ws": workspace_id,
                        "emp": empresa_id,
                        "tipo": cand.tipo,
                        "sev": cand.severidad,
                        "titulo": cand.titulo,
                        "desc": cand.descripcion,
                        "accion": cand.accion_recomendada,
                        "fecha": cand.fecha_limite,
                    },
                )
                creadas += 1

    return WorkspaceBatchSummary(
        workspace_id=workspace_id,
        empresas_evaluadas=empresas_evaluadas,
        alertas_creadas=creadas,
        alertas_existentes=existentes,
    )
