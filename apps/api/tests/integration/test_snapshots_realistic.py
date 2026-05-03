"""Tests del track 11c — snapshots reales de cálculo.

Cada escenario y cada recomendación persistida debe llevar:
- rule_set_snapshot con dumps reales de las reglas vigentes.
- tax_year_params_snapshot con tasas / tramos / topes vigentes.
- rules_snapshot_hash SHA-256 hex determinístico.

Si dos llamadas al motor sobre el mismo tax_year producen el mismo
hash, el cálculo es bit-a-bit reproducible.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import tenant_session
from src.domain.tax_engine.snapshot import build_snapshots


def _claims(workspace_id: UUID) -> dict[str, object]:
    return {
        "sub": str(uuid4()),
        "aud": "authenticated",
        "role": "authenticated",
        "app_metadata": {
            "provider": "email",
            "workspace_id": str(workspace_id),
            "workspace_type": "pyme",
            "role": "owner",
            "empresa_ids": [],
        },
    }


@pytest_asyncio.fixture
async def workspace_id(
    admin_session: AsyncSession,
) -> AsyncIterator[UUID]:
    ws_id = uuid4()
    user_id = uuid4()
    async with admin_session.begin():
        await admin_session.execute(
            text("insert into auth.users (id, email) values (:id, :e)"),
            {"id": str(user_id), "e": f"snap-{user_id}@renteo.local"},
        )
        await admin_session.execute(
            text(
                "insert into core.workspaces (id, name, type) "
                "values (:id, 'Snap test', 'pyme')"
            ),
            {"id": str(ws_id)},
        )
    yield ws_id
    async with admin_session.begin():
        await admin_session.execute(
            text("set local session_replication_role = 'replica'")
        )
        await admin_session.execute(
            text("delete from core.workspaces where id = :id"),
            {"id": str(ws_id)},
        )
        await admin_session.execute(
            text("delete from auth.users where id = :id"),
            {"id": str(user_id)},
        )


@pytest.mark.integration
async def test_build_snapshots_returns_real_rule_dump(
    workspace_id: UUID,
) -> None:
    async with tenant_session(_claims(workspace_id)) as session:
        rule_snap, params_snap, snap_hash = await build_snapshots(
            session, tax_year=2026
        )

    # Las 4 reglas regime_eligibility + 1 whitelist deben aparecer.
    assert "regime_eligibility/14_a" in rule_snap
    assert "regime_eligibility/14_d_3" in rule_snap
    assert "regime_eligibility/14_d_8" in rule_snap
    assert "regime_eligibility/renta_presunta" in rule_snap
    assert "recomendacion_whitelist/global" in rule_snap

    # Cada entrada incluye id, version y rules.
    pyme = rule_snap["regime_eligibility/14_d_3"]
    assert pyme is not None
    assert "rule_set_id" in pyme
    assert pyme["version"] >= 1
    assert "all_of" in pyme["rules"]

    # tax_year_params_snapshot trae los conjuntos esperados.
    assert params_snap["tax_year"] == 2026
    assert len(params_snap["idpc_rates"]) >= 3
    assert len(params_snap["igc_brackets"]) >= 1
    assert len(params_snap["beneficios_topes"]) >= 5

    # Hash es SHA-256 hex (64 chars).
    assert len(snap_hash) == 64
    assert all(c in "0123456789abcdef" for c in snap_hash)


@pytest.mark.integration
async def test_build_snapshots_is_deterministic(
    workspace_id: UUID,
) -> None:
    """Mismo tax_year → mismo hash en ejecuciones distintas."""
    async with tenant_session(_claims(workspace_id)) as session:
        _, _, hash_1 = await build_snapshots(session, tax_year=2026)
    async with tenant_session(_claims(workspace_id)) as session:
        _, _, hash_2 = await build_snapshots(session, tax_year=2026)
    assert hash_1 == hash_2


@pytest.mark.integration
async def test_build_snapshots_differs_by_tax_year(
    workspace_id: UUID,
) -> None:
    """Distinto tax_year → distinto hash (UTM y tasas cambian por año)."""
    async with tenant_session(_claims(workspace_id)) as session:
        _, _, hash_2025 = await build_snapshots(session, tax_year=2025)
        _, _, hash_2026 = await build_snapshots(session, tax_year=2026)
    assert hash_2025 != hash_2026
