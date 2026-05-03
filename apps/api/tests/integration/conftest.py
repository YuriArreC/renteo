"""Fixtures específicas de tests integration.

Las fixtures `engine` y `admin_session` viven en `tests/conftest.py`
(raíz) para que también las hereden tests golden.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID, uuid4

import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
)


@asynccontextmanager
async def tenant_session(
    engine: AsyncEngine, claims: dict[str, Any]
) -> AsyncIterator[AsyncSession]:
    """Sesión que aplica RLS bajo los claims dados (rol authenticated)."""
    factory = async_sessionmaker(
        engine, expire_on_commit=False, class_=AsyncSession
    )
    async with factory() as session, session.begin():
        # Postgres NO acepta parámetros bindable en `SET LOCAL`; usamos la
        # función `set_config(key, value, is_local=true)` que es equivalente
        # y sí los soporta.
        await session.execute(
            text("select set_config('role', 'authenticated', true)")
        )
        await session.execute(
            text("select set_config('request.jwt.claims', :c, true)"),
            {"c": json.dumps(claims)},
        )
        yield session


@pytest_asyncio.fixture
async def two_workspaces(
    admin_session: AsyncSession,
) -> AsyncIterator[dict[str, UUID]]:
    """Crea 2 workspaces (1 pyme, 1 accounting_firm) con 1 empresa cada uno."""
    ws_a = uuid4()
    ws_b = uuid4()
    user_a = uuid4()
    user_b = uuid4()
    emp_a = uuid4()
    emp_b = uuid4()

    async with admin_session.begin():
        for uid in (user_a, user_b):
            await admin_session.execute(
                text(
                    """
                    insert into auth.users (id, email)
                    values (:id, :email)
                    on conflict (id) do nothing
                    """
                ),
                {"id": str(uid), "email": f"test-{uid}@renteo.local"},
            )
        await admin_session.execute(
            text(
                """
                insert into core.workspaces (id, name, type) values
                    (:wa, 'Test A', 'pyme'),
                    (:wb, 'Test B', 'accounting_firm')
                """
            ),
            {"wa": str(ws_a), "wb": str(ws_b)},
        )
        await admin_session.execute(
            text(
                """
                insert into core.empresas
                    (id, workspace_id, rut, razon_social) values
                    (:ea, :wa, '11111111-1', 'Empresa A'),
                    (:eb, :wb, '22222222-2', 'Empresa B')
                """
            ),
            {
                "ea": str(emp_a),
                "wa": str(ws_a),
                "eb": str(emp_b),
                "wb": str(ws_b),
            },
        )

    yield {
        "ws_a": ws_a,
        "ws_b": ws_b,
        "user_a": user_a,
        "user_b": user_b,
        "emp_a": emp_a,
        "emp_b": emp_b,
    }

    async with admin_session.begin():
        await admin_session.execute(
            text("delete from core.empresas where id in (:ea, :eb)"),
            {"ea": str(emp_a), "eb": str(emp_b)},
        )
        await admin_session.execute(
            text("delete from core.workspaces where id in (:wa, :wb)"),
            {"wa": str(ws_a), "wb": str(ws_b)},
        )
        await admin_session.execute(
            text("delete from auth.users where id in (:ua, :ub)"),
            {"ua": str(user_a), "ub": str(user_b)},
        )
