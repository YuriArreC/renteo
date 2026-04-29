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
        await session.execute(
            text("set local request.jwt.claims = :claims"),
            {"claims": json.dumps(claims)},
        )
        yield session


async def get_db_session(
    claims: dict[str, Any] = Depends(verify_jwt),
) -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: yields a tenant-scoped session for authed routes."""
    async with tenant_session(claims) as session:
        yield session
