"""Fixtures comunes a integration y golden tests.

Cualquier suite que necesite DB real reusa estas fixtures por la
herencia automática de pytest (conftest.py se descubre hacia arriba en
el árbol de directorios).
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

DATABASE_URL = os.getenv("DATABASE_URL")


def _skip_if_no_db() -> None:
    if not DATABASE_URL:
        pytest.skip("DATABASE_URL not set; integration/golden tests skipped")


@pytest_asyncio.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    _skip_if_no_db()
    eng = create_async_engine(DATABASE_URL, future=True)
    try:
        yield eng
    finally:
        await eng.dispose()


@pytest_asyncio.fixture
async def admin_session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """Sesión sin RLS (postgres/service_role) para queries directas."""
    factory = async_sessionmaker(
        engine, expire_on_commit=False, class_=AsyncSession
    )
    async with factory() as session:
        yield session
