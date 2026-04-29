"""Tests bloqueantes de aislamiento multi-tenant (RLS).

El Done Criteria del Bloque 0C exige que estos tests pasen:
- C6: usuario de workspace A no ve datos de workspace B.
- C7: accountant_staff sin asignación no ve empresas de su mismo workspace.

Los tests asumen que las migraciones del Bloque 0B fueron aplicadas a la DB
que apunta DATABASE_URL.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.integration.conftest import tenant_session


def _claims_for(
    *,
    user_id: UUID,
    workspace_id: UUID,
    workspace_type: str,
    role: str,
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


@pytest.mark.integration
@pytest.mark.rls
async def test_workspace_isolation_select_empresas(
    engine: AsyncEngine, two_workspaces: dict[str, UUID]
) -> None:
    """C6: owner de workspace A solo ve la empresa A; jamás la de B."""
    ctx = two_workspaces
    claims = _claims_for(
        user_id=ctx["user_a"],
        workspace_id=ctx["ws_a"],
        workspace_type="pyme",
        role="owner",
    )
    async with tenant_session(engine, claims) as session:
        result = await session.execute(text("select id from core.empresas"))
        visible = {UUID(str(row[0])) for row in result.fetchall()}

    assert ctx["emp_a"] in visible, "user A no ve su propia empresa"
    assert ctx["emp_b"] not in visible, (
        "RLS rota: workspace A puede leer empresa de workspace B"
    )


@pytest.mark.integration
@pytest.mark.rls
async def test_workspace_isolation_select_workspaces_table(
    engine: AsyncEngine, two_workspaces: dict[str, UUID]
) -> None:
    """C6: la propia tabla `workspaces` también respeta el aislamiento."""
    ctx = two_workspaces
    claims = _claims_for(
        user_id=ctx["user_a"],
        workspace_id=ctx["ws_a"],
        workspace_type="pyme",
        role="owner",
    )
    async with tenant_session(engine, claims) as session:
        result = await session.execute(text("select id from core.workspaces"))
        visible = {UUID(str(row[0])) for row in result.fetchall()}

    assert ctx["ws_a"] in visible
    assert ctx["ws_b"] not in visible, (
        "RLS rota: usuario ve workspaces ajenos"
    )


@pytest.mark.integration
@pytest.mark.rls
async def test_accountant_staff_without_assignment_cannot_see_empresa(
    engine: AsyncEngine, two_workspaces: dict[str, UUID]
) -> None:
    """C7: accountant_staff con empresa_ids[]=[] no ve empresas del workspace."""
    ctx = two_workspaces
    claims = _claims_for(
        user_id=ctx["user_b"],
        workspace_id=ctx["ws_b"],
        workspace_type="accounting_firm",
        role="accountant_staff",
        empresa_ids=[],
    )
    async with tenant_session(engine, claims) as session:
        result = await session.execute(
            text("select id from core.empresas where id = :id"),
            {"id": str(ctx["emp_b"])},
        )
        rows = result.fetchall()

    assert rows == [], (
        "RLS rota: accountant_staff sin asignación ve empresa de su workspace"
    )


@pytest.mark.integration
@pytest.mark.rls
async def test_accountant_staff_with_assignment_can_see_assigned_empresa(
    engine: AsyncEngine, two_workspaces: dict[str, UUID]
) -> None:
    """C7 contra-prueba: con la empresa en empresa_ids[], el staff sí accede."""
    ctx = two_workspaces
    claims = _claims_for(
        user_id=ctx["user_b"],
        workspace_id=ctx["ws_b"],
        workspace_type="accounting_firm",
        role="accountant_staff",
        empresa_ids=[ctx["emp_b"]],
    )
    async with tenant_session(engine, claims) as session:
        result = await session.execute(
            text("select id from core.empresas where id = :id"),
            {"id": str(ctx["emp_b"])},
        )
        rows = result.fetchall()

    assert len(rows) == 1, (
        "RLS demasiado restrictiva: staff con empresa_id asignada no la ve"
    )
    assert UUID(str(rows[0][0])) == ctx["emp_b"]
