"""Tests integration del worker batch de alertas (track 5c).

No depende de Redis ni Celery: invocamos directamente la coroutine
`_evaluate_all_workspaces` y verificamos persistencia + dedup.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.tasks.alertas import _evaluate_all_workspaces


@pytest_asyncio.fixture
async def workspace_with_diagnostico(
    admin_session: AsyncSession,
) -> AsyncIterator[dict[str, UUID]]:
    """Workspace con 1 empresa y 1 recomendación previa con
    inputs_snapshot que el evaluador puede leer."""
    user_id = uuid4()
    workspace_id = uuid4()
    empresa_id = uuid4()
    async with admin_session.begin():
        await admin_session.execute(
            text("insert into auth.users (id, email) values (:id, :e)"),
            {"id": str(user_id), "e": f"worker-{user_id}@renteo.local"},
        )
        await admin_session.execute(
            text(
                "insert into core.workspaces (id, name, type) "
                "values (:id, 'Worker Test', 'pyme')"
            ),
            {"id": str(workspace_id)},
        )
        await admin_session.execute(
            text(
                "insert into core.empresas "
                "(id, workspace_id, rut, razon_social, regimen_actual) "
                "values (:e, :ws, '11111111-1', 'Empresa Worker', '14_d_3')"
            ),
            {"e": str(empresa_id), "ws": str(workspace_id)},
        )
        # Recomendación previa con template usable.
        inputs_snapshot = {
            "tax_year": 2026,
            "regimen_actual": "14_d_3",
            "via": "test",
            "template": {
                "tax_year": 2026,
                "rli_proyectada_anual_uf": 1000,
                "plan_retiros_pct": 0.30,
            },
        }
        await admin_session.execute(
            text(
                """
                insert into core.recomendaciones
                    (workspace_id, empresa_id, tax_year, tipo,
                     descripcion, fundamento_legal, ahorro_estimado_clp,
                     disclaimer_version, engine_version,
                     inputs_snapshot, outputs,
                     rule_set_snapshot, tax_year_params_snapshot,
                     rules_snapshot_hash, created_by)
                values
                    (:ws, :emp, 2026, 'cambio_regimen',
                     'd', '[]'::jsonb, 1000000.00,
                     'v1', 'test',
                     cast(:inp as jsonb), '{}'::jsonb,
                     '{}'::jsonb, '{}'::jsonb, 'h', :uid)
                """
            ),
            {
                "ws": str(workspace_id),
                "emp": str(empresa_id),
                "uid": str(user_id),
                "inp": json.dumps(inputs_snapshot),
            },
        )
    yield {
        "user_id": user_id,
        "workspace_id": workspace_id,
        "empresa_id": empresa_id,
    }
    async with admin_session.begin():
        await admin_session.execute(
            text("set local session_replication_role = 'replica'")
        )
        await admin_session.execute(
            text("delete from core.alertas where workspace_id = :w"),
            {"w": str(workspace_id)},
        )
        await admin_session.execute(
            text(
                "delete from core.recomendaciones where workspace_id = :w"
            ),
            {"w": str(workspace_id)},
        )
        await admin_session.execute(
            text("delete from core.empresas where workspace_id = :w"),
            {"w": str(workspace_id)},
        )
        await admin_session.execute(
            text("delete from core.workspaces where id = :w"),
            {"w": str(workspace_id)},
        )
        await admin_session.execute(
            text("delete from auth.users where id = :u"),
            {"u": str(user_id)},
        )


@pytest.mark.integration
async def test_batch_creates_alertas_for_diagnosed_empresa(
    workspace_with_diagnostico: dict[str, UUID],
    admin_session: AsyncSession,
) -> None:
    """Empresa 14 D N°3 con RLI > 0 sin palancas dispara las 3
    candidatas iniciales (rebaja_14e, dep_instantanea, apv)."""
    ctx = workspace_with_diagnostico

    summary = await _evaluate_all_workspaces()

    procesadas = summary["workspaces_procesados"]
    assert procesadas >= 1
    creadas_total = sum(
        s["alertas_creadas"]
        for s in summary["summaries"]
        if s["workspace_id"] == str(ctx["workspace_id"])
    )
    assert creadas_total >= 3

    async with admin_session.begin():
        result = await admin_session.execute(
            text(
                "select tipo from core.alertas where workspace_id = :w"
            ),
            {"w": str(ctx["workspace_id"])},
        )
        tipos = {r[0] for r in result.all()}
    assert tipos.issuperset(
        {"rebaja_14e_disponible", "dep_instantanea_disponible", "apv_disponible"}
    )


@pytest.mark.integration
async def test_batch_dedupes_open_alertas_on_second_run(
    workspace_with_diagnostico: dict[str, UUID],
    admin_session: AsyncSession,
) -> None:
    """Llamar el batch dos veces no duplica alertas abiertas."""
    ctx = workspace_with_diagnostico

    await _evaluate_all_workspaces()
    await _evaluate_all_workspaces()

    async with admin_session.begin():
        result = await admin_session.execute(
            text(
                "select count(*) from core.alertas "
                "where workspace_id = :w"
            ),
            {"w": str(ctx["workspace_id"])},
        )
        count = result.scalar_one()
    # Las 3 alertas iniciales sin duplicar.
    assert count == 3
