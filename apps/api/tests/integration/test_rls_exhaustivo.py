"""Suite RLS exhaustiva (CLAUDE.md pre-merge requirement).

CLAUDE.md exige "Tests de RLS multi-tenant pasan". `test_rls_isolation`
ya cubría `core.empresas` y `core.workspaces`; este archivo amplía
la auditoría a las tablas con `workspace_id` que se han ido sumando
con cada track:

  - core.escenarios_simulacion
  - core.recomendaciones
  - core.alertas
  - tax_data.rcv_lines
  - tax_data.f22_anios
  - tax_data.f29_periodos
  - tax_data.sii_sync_log
  - privacy.rat_records
  - privacy.dpia_records

Patrón:
  1. Plantamos 1 fila en workspace A y 1 fila en workspace B vía
     admin_session (bypass RLS).
  2. Tenant A (claims con workspace_id=A) ejecuta SELECT sobre la
     tabla — debe ver SOLO la fila A.
  3. Tenant B (claims con workspace_id=B) — debe ver SOLO la fila B.
  4. Cleanup vía admin_session.

Para tablas con RLS pero sin SELECT policy (sólo service_role) hay
un test separado que verifica que authenticated NO ve nada.

Para write-protection probamos que tenant A no puede INSERT con
workspace_id=B.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, ProgrammingError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from tests.integration.conftest import tenant_session


def _claims_for(
    *,
    user_id: UUID,
    workspace_id: UUID,
    workspace_type: str = "pyme",
    role: str = "owner",
    empresa_ids: list[UUID] | None = None,
) -> dict[str, Any]:
    return {
        "sub": str(user_id),
        "aud": "authenticated",
        "role": "authenticated",
        "app_metadata": {
            "workspace_id": str(workspace_id),
            "workspace_type": workspace_type,
            "role": role,
            "empresa_ids": [str(e) for e in (empresa_ids or [])],
        },
    }


# ---------------------------------------------------------------------------
# Fixture compartida: dos workspaces con dos empresas asignadas a sus owners.
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def two_isolated_workspaces(
    admin_session: AsyncSession,
) -> AsyncIterator[dict[str, UUID]]:
    """Dos workspaces independientes con owner + empresa cada uno.

    A diferencia de `two_workspaces` (de conftest), este fixture deja
    los owners con sus empresas en `empresa_ids` para que las policies
    `app.has_empresa_access` no rechacen el SELECT.
    """
    user_a = uuid4()
    user_b = uuid4()
    ws_a = uuid4()
    ws_b = uuid4()
    emp_a = uuid4()
    emp_b = uuid4()

    async with admin_session.begin():
        await admin_session.execute(
            text(
                "insert into auth.users (id, email) values "
                "(:ua, :ea), (:ub, :eb)"
            ),
            {
                "ua": str(user_a),
                "ea": f"a-{user_a}@renteo.local",
                "ub": str(user_b),
                "eb": f"b-{user_b}@renteo.local",
            },
        )
        await admin_session.execute(
            text(
                "insert into core.workspaces (id, name, type) values "
                "(:wa, 'RLS A', 'pyme'), (:wb, 'RLS B', 'pyme')"
            ),
            {"wa": str(ws_a), "wb": str(ws_b)},
        )
        await admin_session.execute(
            text(
                "insert into core.workspace_members "
                "(workspace_id, user_id, role, accepted_at) values "
                "(:wa, :ua, 'owner', now()), "
                "(:wb, :ub, 'owner', now())"
            ),
            {
                "wa": str(ws_a),
                "ua": str(user_a),
                "wb": str(ws_b),
                "ub": str(user_b),
            },
        )
        await admin_session.execute(
            text(
                "insert into core.empresas "
                "(id, workspace_id, rut, razon_social) values "
                "(:ea, :wa, '11111111-1', 'Empresa RLS A'), "
                "(:eb, :wb, '22222222-2', 'Empresa RLS B')"
            ),
            {
                "ea": str(emp_a),
                "wa": str(ws_a),
                "eb": str(emp_b),
                "wb": str(ws_b),
            },
        )

    yield {
        "user_a": user_a,
        "user_b": user_b,
        "ws_a": ws_a,
        "ws_b": ws_b,
        "emp_a": emp_a,
        "emp_b": emp_b,
    }

    async with admin_session.begin():
        await admin_session.execute(
            text("set local session_replication_role = 'replica'")
        )
        for table in (
            "tax_data.sii_sync_log",
            "tax_data.rcv_lines",
            "tax_data.f29_periodos",
            "tax_data.f22_anios",
            "tax_calc.rli_calculations",
            "core.alertas",
            "core.recomendaciones",
            "core.escenarios_simulacion",
            "privacy.rat_records",
            "privacy.dpia_records",
        ):
            # table viene de un literal whitelist en el código; no hay
            # input externo, por eso silenciamos S608 explícitamente.
            sql = f"delete from {table} where workspace_id in (:a, :b)"  # noqa: S608
            await admin_session.execute(
                text(sql),
                {"a": str(ws_a), "b": str(ws_b)},
            )
        await admin_session.execute(
            text("delete from core.empresas where workspace_id in (:a, :b)"),
            {"a": str(ws_a), "b": str(ws_b)},
        )
        await admin_session.execute(
            text("delete from core.workspaces where id in (:a, :b)"),
            {"a": str(ws_a), "b": str(ws_b)},
        )
        await admin_session.execute(
            text("delete from auth.users where id in (:a, :b)"),
            {"a": str(user_a), "b": str(user_b)},
        )


# ---------------------------------------------------------------------------
# Helpers de plantado por tabla. Cada uno toma (admin_session, ws_id, emp_id)
# y deja una fila identificable en la tabla.
# ---------------------------------------------------------------------------


SeedFn = Callable[[AsyncSession, UUID, UUID], Awaitable[UUID]]


async def _seed_escenario(
    session: AsyncSession, ws: UUID, emp: UUID
) -> UUID:
    sid = uuid4()
    await session.execute(
        text(
            """
            insert into core.escenarios_simulacion
                (id, workspace_id, empresa_id, tax_year, nombre,
                 inputs, outputs, engine_version,
                 rule_set_snapshot, tax_year_params_snapshot,
                 rules_snapshot_hash)
            values
                (:id, :ws, :emp, 2026, 'rls-test',
                 cast('{}' as jsonb), cast('{}' as jsonb), 'rls-test',
                 cast('{}' as jsonb), cast('{}' as jsonb),
                 'rls-test-hash')
            """
        ),
        {"id": str(sid), "ws": str(ws), "emp": str(emp)},
    )
    return sid


async def _seed_recomendacion(
    session: AsyncSession, ws: UUID, emp: UUID
) -> UUID:
    rid = uuid4()
    await session.execute(
        text(
            """
            insert into core.recomendaciones
                (id, workspace_id, empresa_id, tax_year, tipo,
                 descripcion, fundamento_legal, disclaimer_version,
                 engine_version, inputs_snapshot, outputs,
                 rule_set_snapshot, tax_year_params_snapshot,
                 rules_snapshot_hash)
            values
                (:id, :ws, :emp, 2026, 'cambio_regimen',
                 'rls-test', cast('[]' as jsonb), 'v1', 'rls-test',
                 cast('{}' as jsonb), cast('{}' as jsonb),
                 cast('{}' as jsonb), cast('{}' as jsonb),
                 'rls-test-hash')
            """
        ),
        {"id": str(rid), "ws": str(ws), "emp": str(emp)},
    )
    return rid


async def _seed_alerta(
    session: AsyncSession, ws: UUID, emp: UUID
) -> UUID:
    aid = uuid4()
    await session.execute(
        text(
            """
            insert into core.alertas
                (id, workspace_id, empresa_id, tipo, severidad,
                 titulo, descripcion, estado)
            values
                (:id, :ws, :emp, 'rebaja_14e_disponible', 'info',
                 'rls-test', 'rls-test', 'nueva')
            """
        ),
        {"id": str(aid), "ws": str(ws), "emp": str(emp)},
    )
    return aid


async def _seed_rcv_line(
    session: AsyncSession, ws: UUID, emp: UUID
) -> UUID:
    rid = uuid4()
    await session.execute(
        text(
            """
            insert into tax_data.rcv_lines
                (id, workspace_id, empresa_id, period, tipo,
                 neto, iva, total)
            values
                (:id, :ws, :emp, '2026-04', 'venta',
                 100000, 19000, 119000)
            """
        ),
        {"id": str(rid), "ws": str(ws), "emp": str(emp)},
    )
    return rid


async def _seed_f29(
    session: AsyncSession, ws: UUID, emp: UUID
) -> UUID:
    rid = uuid4()
    await session.execute(
        text(
            """
            insert into tax_data.f29_periodos
                (id, workspace_id, empresa_id, period,
                 iva_debito, iva_credito, ppm)
            values
                (:id, :ws, :emp, '2026-04', 100000, 80000, 50000)
            """
        ),
        {"id": str(rid), "ws": str(ws), "emp": str(emp)},
    )
    return rid


async def _seed_f22(
    session: AsyncSession, ws: UUID, emp: UUID
) -> UUID:
    rid = uuid4()
    await session.execute(
        text(
            """
            insert into tax_data.f22_anios
                (id, workspace_id, empresa_id, tax_year,
                 regimen_declarado, rli_declarada, idpc_pagado)
            values
                (:id, :ws, :emp, 2025, '14_d_3', 50000000, 6250000)
            """
        ),
        {"id": str(rid), "ws": str(ws), "emp": str(emp)},
    )
    return rid


async def _seed_sii_sync_log(
    session: AsyncSession, ws: UUID, emp: UUID
) -> UUID:
    rid = uuid4()
    await session.execute(
        text(
            """
            insert into tax_data.sii_sync_log
                (id, workspace_id, empresa_id, provider, kind,
                 status, period_from, period_to)
            values
                (:id, :ws, :emp, 'mock', 'rcv', 'success',
                 '2026-01', '2026-04')
            """
        ),
        {"id": str(rid), "ws": str(ws), "emp": str(emp)},
    )
    return rid


async def _seed_rat(
    session: AsyncSession, ws: UUID, _emp: UUID
) -> UUID:
    rid = uuid4()
    await session.execute(
        text(
            """
            insert into privacy.rat_records
                (id, workspace_id, nombre_actividad, finalidad,
                 base_legal, plazo_conservacion, responsable_email)
            values
                (:id, :ws, 'rls-test', 'rls-test', 'contrato',
                 '5 años', 'dpo@renteo.cl')
            """
        ),
        {"id": str(rid), "ws": str(ws)},
    )
    return rid


async def _seed_dpia(
    session: AsyncSession, ws: UUID, _emp: UUID
) -> UUID:
    rid = uuid4()
    await session.execute(
        text(
            """
            insert into privacy.dpia_records
                (id, workspace_id, nombre_evaluacion,
                 descripcion_tratamiento, necesidad_proporcionalidad,
                 riesgo_residual)
            values
                (:id, :ws, 'rls-test', 'rls-test', 'rls-test',
                 'medio')
            """
        ),
        {"id": str(rid), "ws": str(ws)},
    )
    return rid


# ---------------------------------------------------------------------------
# Read-isolation parametrizado: cada caso planta dos filas (A y B) y
# verifica que tenant A solo ve la suya y tenant B solo la suya.
# ---------------------------------------------------------------------------


_ISOLATION_CASES: list[tuple[str, str, SeedFn]] = [
    ("core.escenarios_simulacion", "core.escenarios_simulacion", _seed_escenario),
    ("core.recomendaciones", "core.recomendaciones", _seed_recomendacion),
    ("core.alertas", "core.alertas", _seed_alerta),
    ("tax_data.rcv_lines", "tax_data.rcv_lines", _seed_rcv_line),
    ("tax_data.f29_periodos", "tax_data.f29_periodos", _seed_f29),
    ("tax_data.f22_anios", "tax_data.f22_anios", _seed_f22),
    ("tax_data.sii_sync_log", "tax_data.sii_sync_log", _seed_sii_sync_log),
    ("privacy.rat_records", "privacy.rat_records", _seed_rat),
    ("privacy.dpia_records", "privacy.dpia_records", _seed_dpia),
]


@pytest.mark.integration
@pytest.mark.rls
@pytest.mark.parametrize(
    ("table_label", "table_name", "seed_fn"),
    _ISOLATION_CASES,
    ids=[case[0] for case in _ISOLATION_CASES],
)
async def test_workspace_isolation_per_table(
    engine: AsyncEngine,
    admin_session: AsyncSession,
    two_isolated_workspaces: dict[str, UUID],
    table_label: str,
    table_name: str,
    seed_fn: SeedFn,
) -> None:
    """Cada tabla con workspace_id aísla A vs B bajo tenant_session."""
    ctx = two_isolated_workspaces

    async with admin_session.begin():
        id_a = await seed_fn(admin_session, ctx["ws_a"], ctx["emp_a"])
        id_b = await seed_fn(admin_session, ctx["ws_b"], ctx["emp_b"])

    claims_a = _claims_for(
        user_id=ctx["user_a"],
        workspace_id=ctx["ws_a"],
        empresa_ids=[ctx["emp_a"]],
    )
    async with tenant_session(engine, claims_a) as session:
        result = await session.execute(
            text(f"select id from {table_name}")  # noqa: S608
        )
        visible_a = {UUID(str(row[0])) for row in result.fetchall()}
    assert id_a in visible_a, (
        f"{table_label}: tenant A no ve su propia fila"
    )
    assert id_b not in visible_a, (
        f"{table_label}: tenant A ve fila del workspace B (RLS rota)"
    )

    claims_b = _claims_for(
        user_id=ctx["user_b"],
        workspace_id=ctx["ws_b"],
        empresa_ids=[ctx["emp_b"]],
    )
    async with tenant_session(engine, claims_b) as session:
        result = await session.execute(
            text(f"select id from {table_name}")  # noqa: S608
        )
        visible_b = {UUID(str(row[0])) for row in result.fetchall()}
    assert id_b in visible_b, (
        f"{table_label}: tenant B no ve su propia fila"
    )
    assert id_a not in visible_b, (
        f"{table_label}: tenant B ve fila del workspace A (RLS rota)"
    )


# ---------------------------------------------------------------------------
# Write protection: tenant A no puede INSERT con workspace_id=B.
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.rls
async def test_write_protection_alertas_cross_workspace(
    engine: AsyncEngine,
    two_isolated_workspaces: dict[str, UUID],
) -> None:
    """Tenant A no puede insertar una alerta con workspace_id=B
    (la WITH CHECK policy debe rechazar el INSERT)."""
    ctx = two_isolated_workspaces
    claims_a = _claims_for(
        user_id=ctx["user_a"],
        workspace_id=ctx["ws_a"],
        empresa_ids=[ctx["emp_a"]],
    )
    async with tenant_session(engine, claims_a) as session:
        with pytest.raises((DBAPIError, ProgrammingError)):
            await session.execute(
                text(
                    """
                    insert into core.alertas
                        (workspace_id, empresa_id, tipo, severidad,
                         titulo, descripcion)
                    values
                        (:ws_b, :emp_b, 'rebaja_14e_disponible', 'info',
                         'attempt cross-workspace', 'tenant A escribe en B')
                    """
                ),
                {
                    "ws_b": str(ctx["ws_b"]),
                    "emp_b": str(ctx["emp_b"]),
                },
            )


@pytest.mark.integration
@pytest.mark.rls
async def test_write_protection_rat_cross_workspace(
    engine: AsyncEngine,
    two_isolated_workspaces: dict[str, UUID],
) -> None:
    """Mismo principio para RAT: tenant A intenta plantar un RAT en
    el workspace B → policy rechaza."""
    ctx = two_isolated_workspaces
    claims_a = _claims_for(
        user_id=ctx["user_a"],
        workspace_id=ctx["ws_a"],
        empresa_ids=[ctx["emp_a"]],
    )
    async with tenant_session(engine, claims_a) as session:
        with pytest.raises((DBAPIError, ProgrammingError)):
            await session.execute(
                text(
                    """
                    insert into privacy.rat_records
                        (workspace_id, nombre_actividad, finalidad,
                         base_legal, plazo_conservacion,
                         responsable_email)
                    values
                        (:ws_b, 'attempt', 'attempt', 'contrato',
                         '5 años', 'dpo@renteo.cl')
                    """
                ),
                {"ws_b": str(ctx["ws_b"])},
            )


# ---------------------------------------------------------------------------
# Service-only tables: tax_rules.legislative_alerts no tiene policy
# para authenticated → tenant_session no ve nada.
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.rls
async def test_legislative_alerts_invisible_to_authenticated(
    engine: AsyncEngine,
    admin_session: AsyncSession,
    two_isolated_workspaces: dict[str, UUID],
) -> None:
    ctx = two_isolated_workspaces
    aid = uuid4()
    async with admin_session.begin():
        await admin_session.execute(
            text(
                """
                insert into tax_rules.legislative_alerts
                    (id, source, source_id, title, publication_date,
                     status, propuesta_diff)
                values
                    (:id, 'dof', :sid, 'rls test', '2026-04-13',
                     'open', cast('{}' as jsonb))
                """
            ),
            {"id": str(aid), "sid": f"rls-test-{aid}"},
        )

    try:
        claims_a = _claims_for(
            user_id=ctx["user_a"],
            workspace_id=ctx["ws_a"],
            empresa_ids=[ctx["emp_a"]],
        )
        async with tenant_session(engine, claims_a) as session:
            result = await session.execute(
                text(
                    "select id from tax_rules.legislative_alerts "
                    "where id = :id"
                ),
                {"id": str(aid)},
            )
            rows = result.fetchall()
        assert rows == [], (
            "tax_rules.legislative_alerts NO debe ser visible a "
            "authenticated (sólo service_role / backoffice)"
        )
    finally:
        async with admin_session.begin():
            await admin_session.execute(
                text(
                    "delete from tax_rules.legislative_alerts "
                    "where id = :id"
                ),
                {"id": str(aid)},
            )


# ---------------------------------------------------------------------------
# Smoke check: la fixture funciona y los inserts cross-workspace fallan.
# Útil como sanity para el setup del test, descubre regressions del
# fixture sin necesidad de auditar todas las tablas.
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.rls
async def test_two_isolated_workspaces_fixture_seeds_clean(
    engine: AsyncEngine,
    two_isolated_workspaces: dict[str, UUID],
) -> None:
    ctx = two_isolated_workspaces
    claims_a = _claims_for(
        user_id=ctx["user_a"],
        workspace_id=ctx["ws_a"],
        empresa_ids=[ctx["emp_a"]],
    )
    async with tenant_session(engine, claims_a) as session:
        result = await session.execute(
            text("select rut from core.empresas")
        )
        ruts_visibles = {row[0] for row in result.fetchall()}
    # Sólo la empresa A es visible (la B existe en DB pero RLS la oculta).
    assert "11111111-1" in ruts_visibles
    assert "22222222-2" not in ruts_visibles


