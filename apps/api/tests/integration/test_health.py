"""Tests integration de /healthz y /readyz (track despliegue prep).

/healthz es liveness — siempre 200 si el proceso responde.
/readyz es readiness — 200 sólo si DB responde a SELECT 1; 503 si la
DB se cae. Render usa /readyz como healthCheckPath para hacer
rollback automático cuando el deploy nuevo no puede servir tráfico.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from src.main import app


@pytest_asyncio.fixture
async def http_client_health() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        yield client


@pytest.mark.integration
async def test_healthz_returns_ok(
    http_client_health: AsyncClient,
) -> None:
    response = await http_client_health.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.integration
async def test_readyz_returns_ok_with_db_up(
    http_client_health: AsyncClient,
) -> None:
    """En CI con Supabase corriendo, /readyz debe pasar el SELECT 1
    y reportar `database: ok`. Redis no está configurado en CI →
    aparece como `not_configured`, sin afectar el status."""
    response = await http_client_health.get("/readyz")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "ok"
    assert body["dependencies"]["database"] == "ok"
    # Redis: not_configured en CI (no rompe), ok en stack completo.
    assert body["dependencies"]["redis"] in ("ok", "not_configured")


@pytest.mark.integration
async def test_readyz_503_when_db_unreachable(
    monkeypatch: pytest.MonkeyPatch,
    http_client_health: AsyncClient,
) -> None:
    """Simulamos DB caída: parchamos SessionLocal a None para que el
    endpoint reporte `database: not_configured` y devuelva 503."""
    monkeypatch.setattr("src.db.SessionLocal", None)
    response = await http_client_health.get("/readyz")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["dependencies"]["database"] == "not_configured"
