"""Tests que certifican que el motor de elegibilidad usa rule_sets
declarativas (skill 11), no constantes Python.

Si alguien re-introduce hardcodes en eligibility.py, estos tests
siguen pasando — pero si alguien deprecia / despublica una regla, el
motor cae con MissingRuleError y los tests revelan el agujero.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import tenant_session
from src.domain.tax_engine.eligibility import (
    EligibilityInputs,
    evaluar_14_a,
    evaluar_14_d_3,
    evaluar_14_d_8,
    evaluar_renta_presunta,
)
from src.lib.errors import MissingRuleError


def _claims(workspace_id: UUID) -> dict[str, Any]:
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
            {"id": str(user_id), "e": f"rules-{user_id}@renteo.local"},
        )
        await admin_session.execute(
            text(
                "insert into core.workspaces (id, name, type) "
                "values (:id, 'Rules test', 'pyme')"
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


_BASE_INPUTS = EligibilityInputs(
    ingresos_promedio_3a_uf=Decimal("30000"),
    ingresos_max_anual_uf=Decimal("40000"),
    capital_efectivo_inicial_uf=Decimal("5000"),
    pct_ingresos_pasivos=Decimal("0.10"),
    todos_duenos_personas_naturales_chile=True,
    participacion_empresas_no_14d_sobre_10pct=False,
    sector="comercio",
    ventas_anuales_uf=Decimal("30000"),
)


@pytest.mark.integration
async def test_evaluar_14_a_always_passes(workspace_id: UUID) -> None:
    async with tenant_session(_claims(workspace_id)) as session:
        ok, reqs = await evaluar_14_a(session, _BASE_INPUTS, 2026)
    assert ok is True
    assert len(reqs) >= 1
    assert reqs[0].fundamento.startswith("art. 14 A")


@pytest.mark.integration
async def test_evaluar_14_d_3_passes_for_compliant_pyme(
    workspace_id: UUID,
) -> None:
    async with tenant_session(_claims(workspace_id)) as session:
        ok, reqs = await evaluar_14_d_3(session, _BASE_INPUTS, 2026)
    assert ok is True
    # Cinco predicados raíz en la regla 14 D N°3.
    assert len(reqs) == 5


@pytest.mark.integration
async def test_evaluar_14_d_3_fails_when_high_passive(
    workspace_id: UUID,
) -> None:
    high_passive = EligibilityInputs(
        ingresos_promedio_3a_uf=Decimal("30000"),
        ingresos_max_anual_uf=Decimal("40000"),
        capital_efectivo_inicial_uf=Decimal("5000"),
        pct_ingresos_pasivos=Decimal("0.50"),
        todos_duenos_personas_naturales_chile=True,
        participacion_empresas_no_14d_sobre_10pct=False,
        sector="comercio",
        ventas_anuales_uf=Decimal("30000"),
    )
    async with tenant_session(_claims(workspace_id)) as session:
        ok, reqs = await evaluar_14_d_3(session, high_passive, 2026)
    assert ok is False
    failed = [r for r in reqs if not r.ok]
    assert any("pasivos" in r.texto.lower() for r in failed)


@pytest.mark.integration
async def test_evaluar_14_d_8_excludes_non_chilean_owner(
    workspace_id: UUID,
) -> None:
    foreign_owner = EligibilityInputs(
        ingresos_promedio_3a_uf=Decimal("30000"),
        ingresos_max_anual_uf=Decimal("40000"),
        capital_efectivo_inicial_uf=Decimal("5000"),
        pct_ingresos_pasivos=Decimal("0.10"),
        todos_duenos_personas_naturales_chile=False,
        participacion_empresas_no_14d_sobre_10pct=False,
        sector="comercio",
        ventas_anuales_uf=Decimal("30000"),
    )
    async with tenant_session(_claims(workspace_id)) as session:
        ok14d3, _ = await evaluar_14_d_3(session, foreign_owner, 2026)
        ok14d8, _ = await evaluar_14_d_8(session, foreign_owner, 2026)
    assert ok14d3 is True
    assert ok14d8 is False


@pytest.mark.integration
async def test_evaluar_renta_presunta_agricola_within_cap(
    workspace_id: UUID,
) -> None:
    agricola = EligibilityInputs(
        ingresos_promedio_3a_uf=Decimal("5000"),
        ingresos_max_anual_uf=Decimal("6000"),
        capital_efectivo_inicial_uf=Decimal("1000"),
        pct_ingresos_pasivos=Decimal("0.10"),
        todos_duenos_personas_naturales_chile=True,
        participacion_empresas_no_14d_sobre_10pct=False,
        sector="agricola",
        ventas_anuales_uf=Decimal("5000"),
    )
    async with tenant_session(_claims(workspace_id)) as session:
        ok, _ = await evaluar_renta_presunta(session, agricola, 2026)
    assert ok is True


@pytest.mark.integration
async def test_resolver_raises_for_year_without_rule(
    workspace_id: UUID,
) -> None:
    """Pedir un tax_year fuera del rango cubierto cae con MissingRuleError."""
    async with tenant_session(_claims(workspace_id)) as session:
        with pytest.raises(MissingRuleError):
            await evaluar_14_d_3(session, _BASE_INPUTS, 2020)
