"""Tests integration de resolve_rule contra una DB real con migraciones aplicadas."""

from __future__ import annotations

import json
from datetime import date
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.tax_engine.rule_resolver import resolve_rule
from src.lib.errors import MissingRuleError


async def _insert_published_rule(
    session: AsyncSession,
    *,
    domain: str,
    key: str,
    version: int,
    vigencia_desde: date,
    vigencia_hasta: date | None,
    rules: dict,
    signer_a: UUID,
    signer_b: UUID,
) -> UUID:
    result = await session.execute(
        text(
            """
            insert into tax_rules.rule_sets (
                domain, key, version,
                vigencia_desde, vigencia_hasta,
                rules, fuente_legal, status,
                published_by_contador, published_by_admin, published_at
            ) values (
                :domain, :key, :version,
                :vd, :vh,
                cast(:rules as jsonb),
                cast(:fl as jsonb),
                'published',
                :sa, :sb, now()
            )
            returning id
            """
        ),
        {
            "domain": domain,
            "key": key,
            "version": version,
            "vd": vigencia_desde,
            "vh": vigencia_hasta,
            "rules": json.dumps(rules),
            "fl": json.dumps([{"tipo": "ley", "id": "test"}]),
            "sa": str(signer_a),
            "sb": str(signer_b),
        },
    )
    return UUID(str(result.scalar_one()))


@pytest.mark.integration
async def test_resolve_rule_returns_correct_version_for_year(
    admin_session: AsyncSession, two_workspaces: dict[str, UUID]
) -> None:
    domain = "test_resolver_correct_version"
    key = "demo_key"
    signer_a = two_workspaces["user_a"]
    signer_b = two_workspaces["user_b"]

    rule_v1_id = rule_v2_id = None
    try:
        async with admin_session.begin():
            rule_v1_id = await _insert_published_rule(
                admin_session,
                domain=domain,
                key=key,
                version=1,
                vigencia_desde=date(2024, 1, 1),
                vigencia_hasta=date(2026, 12, 31),
                rules={"v": 1},
                signer_a=signer_a,
                signer_b=signer_b,
            )
            rule_v2_id = await _insert_published_rule(
                admin_session,
                domain=domain,
                key=key,
                version=2,
                vigencia_desde=date(2027, 1, 1),
                vigencia_hasta=None,
                rules={"v": 2},
                signer_a=signer_a,
                signer_b=signer_b,
            )

        async with admin_session.begin():
            v1 = await resolve_rule(admin_session, domain, key, 2025)
            v2 = await resolve_rule(admin_session, domain, key, 2027)

        assert v1.id == rule_v1_id
        assert v1.rules == {"v": 1}
        assert v2.id == rule_v2_id
        assert v2.rules == {"v": 2}
    finally:
        async with admin_session.begin():
            await admin_session.execute(
                text("delete from tax_rules.rule_sets where domain = :d"),
                {"d": domain},
            )


@pytest.mark.integration
async def test_resolve_rule_raises_on_missing(
    admin_session: AsyncSession,
) -> None:
    with pytest.raises(MissingRuleError):
        async with admin_session.begin():
            await resolve_rule(
                admin_session,
                domain="nonexistent_domain",
                key="nonexistent_key",
                tax_year=2026,
            )


@pytest.mark.integration
async def test_resolve_rule_picks_latest_when_overlap(
    admin_session: AsyncSession, two_workspaces: dict[str, UUID]
) -> None:
    """Si dos versiones publicadas se solapan, gana vigencia_desde más reciente."""
    domain = "test_resolver_overlap"
    key = "demo_key"
    signer_a = two_workspaces["user_a"]
    signer_b = two_workspaces["user_b"]

    try:
        async with admin_session.begin():
            await _insert_published_rule(
                admin_session,
                domain=domain,
                key=key,
                version=1,
                vigencia_desde=date(2024, 1, 1),
                vigencia_hasta=None,
                rules={"v": 1},
                signer_a=signer_a,
                signer_b=signer_b,
            )
            v2_id = await _insert_published_rule(
                admin_session,
                domain=domain,
                key=key,
                version=2,
                vigencia_desde=date(2026, 1, 1),
                vigencia_hasta=None,
                rules={"v": 2},
                signer_a=signer_a,
                signer_b=signer_b,
            )

        async with admin_session.begin():
            resolved = await resolve_rule(admin_session, domain, key, 2026)

        assert resolved.id == v2_id
    finally:
        async with admin_session.begin():
            await admin_session.execute(
                text("delete from tax_rules.rule_sets where domain = :d"),
                {"d": domain},
            )
