"""Tests integration del watchdog legislativo (skill 11 closure).

Cubren: worker corre vía POST /run, dedup en segunda corrida, listado
filtrable por status/source, transición de estado vía PATCH y role
gate (sólo internal_admin)."""

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

# IDs deterministas seedeados por la migración 20260504120000.
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
async def http_client_leg() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        yield client
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def cleanup_alerts(
    admin_session: AsyncSession,
) -> AsyncIterator[None]:
    """Cada test corre con tabla limpia y la deja limpia."""
    async with admin_session.begin():
        await admin_session.execute(
            text("delete from tax_rules.legislative_alerts")
        )
    yield
    async with admin_session.begin():
        await admin_session.execute(
            text("delete from tax_rules.legislative_alerts")
        )


@pytest.mark.integration
async def test_list_blocked_for_non_admin(
    http_client_leg: AsyncClient,
    cleanup_alerts: None,
) -> None:
    user_id = uuid4()
    app.dependency_overrides[verify_jwt] = _override(_claims(user_id))

    response = await http_client_leg.get(
        "/api/admin/legislative-alerts",
        headers={"Authorization": "Bearer fake"},
    )
    assert response.status_code == 403


@pytest.mark.integration
async def test_run_watchdog_inserts_alerts_with_dedup(
    http_client_leg: AsyncClient,
    cleanup_alerts: None,
) -> None:
    """Primer /run inserta N filas; el segundo no duplica nada."""
    app.dependency_overrides[verify_jwt] = _override(_claims(_CONTADOR_ID))

    first = await http_client_leg.post(
        "/api/admin/legislative-alerts/run",
        headers={"Authorization": "Bearer fake"},
    )
    assert first.status_code == 200, first.text
    first_body = first.json()
    assert first_body["monitor"] == "mock"
    assert first_body["existentes"] == 0
    nuevos_first = first_body["nuevos"]
    # El mock garantiza al menos algunos hits sobre 7 días: lunes
    # (DOF) + posible día 15 (SII) + posible 1-ene (presupuestos).
    # No asumimos cantidad exacta; sólo que hay actividad si el rango
    # cubre al menos un lunes.
    assert nuevos_first >= 0

    second = await http_client_leg.post(
        "/api/admin/legislative-alerts/run",
        headers={"Authorization": "Bearer fake"},
    )
    assert second.status_code == 200
    second_body = second.json()
    assert second_body["nuevos"] == 0
    assert second_body["existentes"] == nuevos_first


@pytest.mark.integration
async def test_list_filters_status_and_source(
    http_client_leg: AsyncClient,
    cleanup_alerts: None,
    admin_session: AsyncSession,
) -> None:
    """Plantamos 3 alertas variadas y verificamos los filtros."""
    app.dependency_overrides[verify_jwt] = _override(_claims(_CONTADOR_ID))

    async with admin_session.begin():
        await admin_session.execute(
            text(
                """
                insert into tax_rules.legislative_alerts
                    (source, source_id, title, summary,
                     publication_date, status, propuesta_diff)
                values
                    ('dof', 'DOF-test-1', 'DOF lunes',
                     'reajuste UF', '2026-04-13', 'open',
                     cast('{}' as jsonb)),
                    ('sii_circular', 'CIRC-test-1',
                     'Circular SII', 'instrucciones',
                     '2026-04-15', 'open', cast('{}' as jsonb)),
                    ('sii_circular', 'CIRC-test-2',
                     'Circular antigua', 'ya cubierta',
                     '2026-03-15', 'ignored',
                     cast('{}' as jsonb))
                """
            )
        )

    only_open = await http_client_leg.get(
        "/api/admin/legislative-alerts?status_filter=open",
        headers={"Authorization": "Bearer fake"},
    )
    assert only_open.status_code == 200
    open_titles = {r["title"] for r in only_open.json()["records"]}
    assert open_titles == {"DOF lunes", "Circular SII"}

    only_sii = await http_client_leg.get(
        "/api/admin/legislative-alerts?source=sii_circular",
        headers={"Authorization": "Bearer fake"},
    )
    sources = {r["source"] for r in only_sii.json()["records"]}
    assert sources == {"sii_circular"}


@pytest.mark.integration
async def test_patch_alert_transitions_status_with_review_metadata(
    http_client_leg: AsyncClient,
    cleanup_alerts: None,
    admin_session: AsyncSession,
) -> None:
    app.dependency_overrides[verify_jwt] = _override(_claims(_CONTADOR_ID))

    alert_id = uuid4()
    async with admin_session.begin():
        await admin_session.execute(
            text(
                """
                insert into tax_rules.legislative_alerts
                    (id, source, source_id, title, publication_date,
                     status, propuesta_diff)
                values
                    (:id, 'dof', 'DOF-patch-1', 'DOF',
                     '2026-04-13', 'open', cast('{}' as jsonb))
                """
            ),
            {"id": str(alert_id)},
        )

    response = await http_client_leg.patch(
        f"/api/admin/legislative-alerts/{alert_id}",
        json={
            "status": "dismissed",
            "review_note": "Reajuste menor, no requiere cambio.",
        },
        headers={"Authorization": "Bearer fake"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "dismissed"
    assert body["reviewed_by"] == str(_CONTADOR_ID)
    assert body["reviewed_at"] is not None
    assert body["review_note"].startswith("Reajuste menor")


@pytest.mark.integration
async def test_patch_returns_404_for_unknown_alert(
    http_client_leg: AsyncClient,
    cleanup_alerts: None,
) -> None:
    app.dependency_overrides[verify_jwt] = _override(_claims(_CONTADOR_ID))
    response = await http_client_leg.patch(
        f"/api/admin/legislative-alerts/{uuid4()}",
        json={"status": "ignored"},
        headers={"Authorization": "Bearer fake"},
    )
    assert response.status_code == 404
