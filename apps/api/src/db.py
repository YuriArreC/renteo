"""Async SQLAlchemy engine, session factory and tenant-aware session helpers.

The session helper opens a transaction and runs `SET LOCAL request.jwt.claims`
so Postgres RLS policies (B12) evaluate `auth.jwt()` correctly. Without this,
RLS would see no JWT and reject every authenticated query.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.auth.jwt import verify_jwt
from src.config import settings


def _make_engine() -> AsyncEngine | None:
    if not settings.database_url:
        return None
    return create_async_engine(
        settings.database_url,
        pool_pre_ping=True,
        future=True,
    )


engine: AsyncEngine | None = _make_engine()
SessionLocal: async_sessionmaker[AsyncSession] | None = (
    async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    if engine is not None
    else None
)


@asynccontextmanager
async def tenant_session(
    claims: dict[str, Any],
) -> AsyncIterator[AsyncSession]:
    """Open a session with `request.jwt.claims` set for RLS evaluation.

    `SET LOCAL` requires an active transaction; we open one with
    `session.begin()` and rely on SQLAlchemy to commit/rollback on exit.
    """
    if SessionLocal is None:
        raise RuntimeError("database is not configured (DATABASE_URL missing)")
    async with SessionLocal() as session, session.begin():
        # Postgres NO acepta parámetros bindable en `SET LOCAL`; usamos la
        # función `set_config(key, value, is_local=true)` para inyectar los
        # claims sin caer en `syntax error at or near "$1"`.
        await session.execute(
            text("select set_config('request.jwt.claims', :claims, true)"),
            {"claims": json.dumps(claims)},
        )
        yield session


async def get_db_session(
    claims: dict[str, Any] = Depends(verify_jwt),
) -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: yields a tenant-scoped session for authed routes."""
    async with tenant_session(claims) as session:
        yield session


@asynccontextmanager
async def service_session() -> AsyncIterator[AsyncSession]:
    """Yield a session that bypasses RLS.

    The connection uses the role configured in DATABASE_URL (postgres locally,
    service_role in production). Use ONLY for operations that must run before
    a workspace exists (onboarding) or for internal tasks (Celery workers,
    audit jobs). The caller is responsible for not leaking data across tenants.
    """
    if SessionLocal is None:
        raise RuntimeError("database is not configured (DATABASE_URL missing)")
    async with SessionLocal() as session, session.begin():
        yield session
