"""Tests del middleware request_id (skill 10).

Verifica que cada response trae el header X-Request-Id; si la
request ya lo trae, lo respeta; si no, lo genera. El test no toca
Sentry: la inicialización es no-op cuando el DSN está vacío.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from src.main import app


@pytest.mark.asyncio
async def test_request_id_is_generated_when_missing() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        response = await client.get("/healthz")

    assert response.status_code == 200
    assert "x-request-id" in {k.lower() for k in response.headers}
    rid = response.headers["x-request-id"]
    # uuid4 hex tiene 32 chars, todos hex.
    assert len(rid) == 32
    assert all(c in "0123456789abcdef" for c in rid)


@pytest.mark.asyncio
async def test_request_id_is_propagated_when_provided() -> None:
    incoming = "fixed-correlation-id-123"
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        response = await client.get(
            "/healthz", headers={"X-Request-Id": incoming}
        )

    assert response.status_code == 200
    assert response.headers["x-request-id"] == incoming
