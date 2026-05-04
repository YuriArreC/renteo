"""Tests integration de encargados de tratamiento (skill 5)."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from typing import Any
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.jwt import verify_jwt
from src.main import app

_CONTADOR_ID = UUID("00000000-0000-0000-0000-00000000c001")


def _claims(user_id: UUID) -> dict[str, Any]:
    return {
        "sub": str(user_id),
        "aud": "authenticated",
        "role": "authenticated",
        "app_metadata": {"provider": "email"},
    }


def _override(claims: dict[str, Any]) -> Callable[[], dict[str, Any]]:
    def _dep() -> dict[str, Any]:
        return claims

    return _dep


@pytest_asyncio.fixture
async def http_client_enc() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        yield client
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def cleanup_test_encargados(
    admin_session: AsyncSession,
) -> AsyncIterator[None]:
    yield
    async with admin_session.begin():
        await admin_session.execute(
            text(
                "delete from privacy.encargados "
                "where nombre like 'TEST_%'"
            )
        )


@pytest.mark.integration
async def test_public_list_returns_seeded_encargados(
    http_client_enc: AsyncClient,
) -> None:
    response = await http_client_enc.get("/api/public/encargados")
    assert response.status_code == 200, response.text
    nombres = {e["nombre"] for e in response.json()["encargados"]}
    assert "Supabase Inc." in nombres
    assert "Amazon Web Services" in nombres


@pytest.mark.integration
async def test_admin_list_includes_dpa_metadata(
    http_client_enc: AsyncClient,
) -> None:
    app.dependency_overrides[verify_jwt] = _override(_claims(_CONTADOR_ID))

    response = await http_client_enc.get(
        "/api/admin/encargados",
        headers={"Authorization": "Bearer fake"},
    )
    assert response.status_code == 200, response.text
    items = response.json()["encargados"]
    assert any(e["activo"] is True for e in items)
    # Los encargados seedeados llevan dpa_firmado_at = None hasta que se firmen.
    sup = next(e for e in items if e["nombre"] == "Supabase Inc.")
    assert "contacto_dpo" in sup


@pytest.mark.integration
async def test_admin_list_blocked_for_non_admin(
    http_client_enc: AsyncClient,
) -> None:
    user_id = uuid4()
    app.dependency_overrides[verify_jwt] = _override(_claims(user_id))

    response = await http_client_enc.get(
        "/api/admin/encargados",
        headers={"Authorization": "Bearer fake"},
    )
    assert response.status_code == 403


@pytest.mark.integration
async def test_create_then_patch_then_soft_delete(
    http_client_enc: AsyncClient,
    cleanup_test_encargados: None,
) -> None:
    app.dependency_overrides[verify_jwt] = _override(_claims(_CONTADOR_ID))

    created = await http_client_enc.post(
        "/api/admin/encargados",
        json={
            "nombre": "TEST_Resend",
            "proposito": "Email transaccional",
            "pais_tratamiento": "US",
            "contacto_dpo": "privacy@resend.com",
        },
        headers={"Authorization": "Bearer fake"},
    )
    assert created.status_code == 201, created.text
    enc_id = created.json()["id"]

    patched = await http_client_enc.patch(
        f"/api/admin/encargados/{enc_id}",
        json={
            "dpa_firmado_at": "2026-01-15",
            "dpa_vigente_hasta": "2027-01-15",
            "dpa_url": "https://example.com/dpa.pdf",
        },
        headers={"Authorization": "Bearer fake"},
    )
    assert patched.status_code == 200, patched.text
    body = patched.json()
    assert body["dpa_firmado_at"] == "2026-01-15"
    assert body["dpa_vigente_hasta"] == "2027-01-15"

    deleted = await http_client_enc.delete(
        f"/api/admin/encargados/{enc_id}",
        headers={"Authorization": "Bearer fake"},
    )
    assert deleted.status_code == 204

    # Public list ya no lo muestra.
    public = await http_client_enc.get("/api/public/encargados")
    public_names = {e["nombre"] for e in public.json()["encargados"]}
    assert "TEST_Resend" not in public_names


@pytest.mark.integration
async def test_patch_invalid_dpa_dates_rejected(
    http_client_enc: AsyncClient,
    cleanup_test_encargados: None,
) -> None:
    """vigente_hasta < firmado_at viola el CHECK constraint → 500
    SQL error o 422 según mapping. La policy del schema es la de
    verdad; aquí solo verificamos que no pasa silenciosamente."""
    app.dependency_overrides[verify_jwt] = _override(_claims(_CONTADOR_ID))

    created = await http_client_enc.post(
        "/api/admin/encargados",
        json={
            "nombre": "TEST_BadDates",
            "proposito": "Test",
        },
        headers={"Authorization": "Bearer fake"},
    )
    enc_id = created.json()["id"]

    response = await http_client_enc.patch(
        f"/api/admin/encargados/{enc_id}",
        json={
            "dpa_firmado_at": "2026-06-01",
            "dpa_vigente_hasta": "2026-01-01",
        },
        headers={"Authorization": "Bearer fake"},
    )
    assert response.status_code >= 400
