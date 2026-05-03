"""Tests que certifican que el simulador lee los topes paramétricos
desde tax_params.beneficios_topes (track 11b), no de constantes Python.

El motor del simulador llama `get_beneficio(...)` para resolver:
- rebaja_14e_porcentaje (50% RLI máximo)
- rebaja_14e_uf (5.000 UF tope absoluto)
- sueldo_empresarial_tope_mensual_uf (250 UF heurística MVP)
- uf_valor_clp (38.000 UF placeholder)
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import tenant_session
from src.domain.tax_engine.beneficios import get_beneficio
from src.lib.errors import MissingTaxYearParams


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
            {"id": str(user_id), "e": f"topes-{user_id}@renteo.local"},
        )
        await admin_session.execute(
            text(
                "insert into core.workspaces (id, name, type) "
                "values (:id, 'Topes test', 'pyme')"
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
async def test_get_beneficio_returns_seeded_value(
    workspace_id: UUID,
) -> None:
    async with tenant_session(_claims(workspace_id)) as session:
        tope = await get_beneficio(
            session, key="rebaja_14e_uf", tax_year=2026
        )
        pct = await get_beneficio(
            session, key="rebaja_14e_porcentaje", tax_year=2026
        )
        sueldo = await get_beneficio(
            session,
            key="sueldo_empresarial_tope_mensual_uf",
            tax_year=2026,
        )
        uf = await get_beneficio(
            session, key="uf_valor_clp", tax_year=2026
        )
    assert tope == Decimal("5000.0000")
    assert pct == Decimal("0.5000")
    assert sueldo == Decimal("250.0000")
    assert uf == Decimal("38000.0000")


@pytest.mark.integration
async def test_get_beneficio_raises_when_year_missing(
    workspace_id: UUID,
) -> None:
    async with tenant_session(_claims(workspace_id)) as session:
        with pytest.raises(MissingTaxYearParams):
            await get_beneficio(
                session, key="rebaja_14e_uf", tax_year=2099
            )
