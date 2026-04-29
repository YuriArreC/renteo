"""Fixtures para tests de integración con DB real (Supabase local o preview).

Los tests se saltan automáticamente si `DATABASE_URL` no está configurada,
así el test_smoke unitario no requiere infraestructura.

Patrón:
- `engine` (session scope): AsyncEngine compartido.
- `admin_session`: sesión que NO aplica RLS (rol superuser/postgres) usada
  para setup/teardown.
- `tenant_session(engine, claims)`: context manager que abre una sesión
  con `set local role authenticated` y `set local request.jwt.claims = ...`,
  para que RLS evalúe las policies del Bloque 0B.
"""

from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

DATABASE_URL = os.getenv("DATABASE_URL")


def _skip_if_no_db() -> None:
    if not DATABASE_URL:
        pytest.skip("DATABASE_URL not set; integration tests skipped")


@pytest_asyncio.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    # Function-scoped: pytest-asyncio crea un event loop por test y un engine
    # con scope=session se ata al primer loop, lanzando "Task attached to a
    # different loop" en los tests siguientes.
    _skip_if_no_db()
    eng = create_async_engine(DATABASE_URL, future=True)
    try:
        yield eng
    finally:
        await eng.dispose()


@pytest_asyncio.fixture
async def admin_session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """Conexión sin RLS (postgres/service_role) para setup/teardown."""
    factory = async_sessionmaker(
        engine, expire_on_commit=False, class_=AsyncSession
    )
    async with factory() as session:
        yield session


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
