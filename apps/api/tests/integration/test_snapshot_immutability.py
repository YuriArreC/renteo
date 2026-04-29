"""Tests integration que verifican el trigger de inmutabilidad de snapshots
y el CHECK constraint de doble firma (skill 11)."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError, InternalError
from sqlalchemy.ext.asyncio import AsyncSession


async def _insert_recomendacion(
    session: AsyncSession, ws_id: UUID, emp_id: UUID, *, engine_version: str = "v1"
) -> UUID:
    rec_id = uuid4()
    await session.execute(
        text(
            """
            insert into core.recomendaciones (
                id, workspace_id, empresa_id, tax_year,
                tipo, descripcion, fundamento_legal,
                disclaimer_version, engine_version,
                inputs_snapshot, outputs,
                rule_set_snapshot, tax_year_params_snapshot
            ) values (
                :id, :ws, :emp, 2026,
                'cambio_regimen', 'test',
                cast('[]' as jsonb),
                'disclaimer-recomendacion-v1', :engine,
                cast('{}' as jsonb), cast('{}' as jsonb),
                cast('{"rules":[]}' as jsonb), cast('{}' as jsonb)
            )
            """
        ),
        {
            "id": str(rec_id),
            "ws": str(ws_id),
            "emp": str(emp_id),
            "engine": engine_version,
        },
    )
    return rec_id


# ---------------------------------------------------------------------------
# Snapshot immutability — trigger app.prevent_snapshot_modification
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_snapshot_engine_version_is_immutable(
    admin_session: AsyncSession, two_workspaces: dict[str, UUID]
) -> None:
    rec_id: UUID | None = None
    try:
        async with admin_session.begin():
            rec_id = await _insert_recomendacion(
                admin_session, two_workspaces["ws_a"], two_workspaces["emp_a"]
            )

        with pytest.raises((DBAPIError, InternalError)):
            async with admin_session.begin():
                await admin_session.execute(
                    text(
                        "update core.recomendaciones set engine_version = 'v2' "
                        "where id = :id"
                    ),
                    {"id": str(rec_id)},
                )
    finally:
        if rec_id is not None:
            async with admin_session.begin():
                await admin_session.execute(
                    text("delete from core.recomendaciones where id = :id"),
                    {"id": str(rec_id)},
                )


@pytest.mark.integration
async def test_snapshot_rule_set_snapshot_is_immutable(
    admin_session: AsyncSession, two_workspaces: dict[str, UUID]
) -> None:
    rec_id: UUID | None = None
    try:
        async with admin_session.begin():
            rec_id = await _insert_recomendacion(
                admin_session, two_workspaces["ws_a"], two_workspaces["emp_a"]
            )

        with pytest.raises((DBAPIError, InternalError)):
            async with admin_session.begin():
                # El JSON va como bind parameter; un literal inline con
                # `:true` lo parsea SQLAlchemy como bind name llamado `true`
                # y rompe la query.
                await admin_session.execute(
                    text(
                        "update core.recomendaciones "
                        "set rule_set_snapshot = cast(:tampered as jsonb) "
                        "where id = :id"
                    ),
                    {"id": str(rec_id), "tampered": '{"tampered":true}'},
                )
    finally:
        if rec_id is not None:
            async with admin_session.begin():
                await admin_session.execute(
                    text("delete from core.recomendaciones where id = :id"),
                    {"id": str(rec_id)},
                )


@pytest.mark.integration
async def test_can_update_dismissed_at(
    admin_session: AsyncSession, two_workspaces: dict[str, UUID]
) -> None:
    """El trigger NO bloquea otros campos — dismissed_at sí se puede setear."""
    rec_id: UUID | None = None
    try:
        async with admin_session.begin():
            rec_id = await _insert_recomendacion(
                admin_session, two_workspaces["ws_a"], two_workspaces["emp_a"]
            )

        async with admin_session.begin():
            await admin_session.execute(
                text(
                    "update core.recomendaciones set dismissed_at = now() "
                    "where id = :id"
                ),
                {"id": str(rec_id)},
            )
            result = await admin_session.execute(
                text(
                    "select dismissed_at from core.recomendaciones where id = :id"
                ),
                {"id": str(rec_id)},
            )
            dismissed = result.scalar_one()
            assert dismissed is not None
    finally:
        if rec_id is not None:
            async with admin_session.begin():
                await admin_session.execute(
                    text("delete from core.recomendaciones where id = :id"),
                    {"id": str(rec_id)},
                )


# ---------------------------------------------------------------------------
# Double signature — CHECK constraint en tax_rules.rule_sets
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_publishing_rule_with_same_signer_fails(
    admin_session: AsyncSession, two_workspaces: dict[str, UUID]
) -> None:
    """published_by_contador == published_by_admin viola CHECK."""
    same_signer = two_workspaces["user_a"]
    with pytest.raises((DBAPIError, IntegrityError)):
        async with admin_session.begin():
            await admin_session.execute(
                text(
                    """
                    insert into tax_rules.rule_sets (
                        domain, key, version, vigencia_desde,
                        rules, fuente_legal, status,
                        published_by_contador, published_by_admin, published_at
                    ) values (
                        'test_double_sig', 'self_signed', 1, '2026-01-01',
                        cast('{}' as jsonb),
                        cast('[{"tipo":"ley","id":"test"}]' as jsonb),
                        'published', :s, :s, now()
                    )
                    """
                ),
                {"s": str(same_signer)},
            )


@pytest.mark.integration
async def test_publishing_rule_without_published_at_fails(
    admin_session: AsyncSession, two_workspaces: dict[str, UUID]
) -> None:
    with pytest.raises((DBAPIError, IntegrityError)):
        async with admin_session.begin():
            await admin_session.execute(
                text(
                    """
                    insert into tax_rules.rule_sets (
                        domain, key, version, vigencia_desde,
                        rules, fuente_legal, status,
                        published_by_contador, published_by_admin, published_at
                    ) values (
                        'test_double_sig', 'no_published_at', 1, '2026-01-01',
                        cast('{}' as jsonb),
                        cast('[{"tipo":"ley","id":"test"}]' as jsonb),
                        'published', :sa, :sb, null
                    )
                    """
                ),
                {
                    "sa": str(two_workspaces["user_a"]),
                    "sb": str(two_workspaces["user_b"]),
                },
            )


@pytest.mark.integration
async def test_draft_rule_does_not_require_signers(
    admin_session: AsyncSession,
) -> None:
    """Un draft puede existir sin firmantes; el CHECK solo aplica al publicar."""
    domain = "test_draft_rule"
    try:
        async with admin_session.begin():
            await admin_session.execute(
                text(
                    """
                    insert into tax_rules.rule_sets (
                        domain, key, version, vigencia_desde,
                        rules, fuente_legal, status
                    ) values (
                        :d, 'in_progress', 1, '2026-01-01',
                        cast('{}' as jsonb),
                        cast('[{"tipo":"ley","id":"test"}]' as jsonb),
                        'draft'
                    )
                    """
                ),
                {"d": domain},
            )
    finally:
        async with admin_session.begin():
            await admin_session.execute(
                text("delete from tax_rules.rule_sets where domain = :d"),
                {"d": domain},
            )
