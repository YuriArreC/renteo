"""Tests integration del panel admin de reglas (skill 11 fase 6)."""

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

# IDs deterministas seedeados por la migración 20260506120000:
_CONTADOR_ID = UUID("00000000-0000-0000-0000-00000000c001")
_ADMIN_TECNICO_ID = UUID("00000000-0000-0000-0000-00000000a001")


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
async def http_client_admin() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        yield client
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def cleanup_drafts(
    admin_session: AsyncSession,
) -> AsyncIterator[None]:
    """Quita los drafts creados durante el test sin tocar las reglas
    publicadas existentes (que se usan en otros tests integration)."""
    yield
    async with admin_session.begin():
        await admin_session.execute(
            text(
                "delete from tax_rules.rule_sets "
                "where domain = 'test_admin' "
                "   or status in ('draft', 'pending_approval', "
                "                 'deprecated')"
            )
        )


@pytest.mark.integration
async def test_list_rules_blocked_for_non_admin(
    http_client_admin: AsyncClient,
) -> None:
    user_id = uuid4()
    app.dependency_overrides[verify_jwt] = _override(_claims(user_id))

    response = await http_client_admin.get(
        "/api/admin/rules",
        headers={"Authorization": "Bearer fake"},
    )
    assert response.status_code == 403


@pytest.mark.integration
async def test_list_rules_returns_seeded_rules_for_admin(
    http_client_admin: AsyncClient,
) -> None:
    app.dependency_overrides[verify_jwt] = _override(_claims(_CONTADOR_ID))

    response = await http_client_admin.get(
        "/api/admin/rules?status_filter=published",
        headers={"Authorization": "Bearer fake"},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    domains = {r["domain"] for r in data["rule_sets"]}
    # Las reglas seedeadas en track 11 deben aparecer.
    assert "regime_eligibility" in domains
    assert "recomendacion_whitelist" in domains


@pytest.mark.integration
async def test_create_draft_increments_version(
    http_client_admin: AsyncClient,
    cleanup_drafts: None,
) -> None:
    app.dependency_overrides[verify_jwt] = _override(_claims(_CONTADOR_ID))

    body = {
        "domain": "test_admin",
        "key": "ejemplo",
        "vigencia_desde": "2027-01-01",
        "rules": {
            "all_of": [{"field": "x", "op": "eq", "value": 1}]
        },
        "fuente_legal": [{"tipo": "ley", "id": "TEST"}],
    }

    first = await http_client_admin.post(
        "/api/admin/rules",
        json=body,
        headers={"Authorization": "Bearer fake"},
    )
    assert first.status_code == 201, first.text
    assert first.json()["version"] == 1
    assert first.json()["status"] == "draft"

    second = await http_client_admin.post(
        "/api/admin/rules",
        json=body,
        headers={"Authorization": "Bearer fake"},
    )
    assert second.json()["version"] == 2


@pytest.mark.integration
async def test_double_signature_workflow(
    http_client_admin: AsyncClient,
    cleanup_drafts: None,
) -> None:
    """draft → contador firma → admin firma → published."""
    # 1) Contador crea draft.
    app.dependency_overrides[verify_jwt] = _override(_claims(_CONTADOR_ID))
    created = await http_client_admin.post(
        "/api/admin/rules",
        json={
            "domain": "test_admin",
            "key": "doble_firma",
            "vigencia_desde": "2027-01-01",
            "rules": {
                "all_of": [{"field": "ok", "op": "eq", "value": True}]
            },
            "fuente_legal": [{"tipo": "ley", "id": "DF"}],
        },
        headers={"Authorization": "Bearer fake"},
    )
    rule_id = created.json()["id"]

    # 2) Contador firma (primera firma).
    sign_c = await http_client_admin.post(
        f"/api/admin/rules/{rule_id}/sign-contador",
        headers={"Authorization": "Bearer fake"},
    )
    assert sign_c.status_code == 200, sign_c.text
    assert sign_c.json()["status"] == "pending_approval"
    assert sign_c.json()["published_by_contador"] == str(_CONTADOR_ID)

    # 3) Mismo user intenta publicar → 409 (doble firma).
    same = await http_client_admin.post(
        f"/api/admin/rules/{rule_id}/publish",
        headers={"Authorization": "Bearer fake"},
    )
    assert same.status_code == 409

    # 4) Admin técnico publica → 200.
    app.dependency_overrides[verify_jwt] = _override(
        _claims(_ADMIN_TECNICO_ID)
    )
    published = await http_client_admin.post(
        f"/api/admin/rules/{rule_id}/publish",
        headers={"Authorization": "Bearer fake"},
    )
    assert published.status_code == 200, published.text
    body = published.json()
    assert body["status"] == "published"
    assert body["published_by_admin"] == str(_ADMIN_TECNICO_ID)
    assert body["published_at"] is not None


@pytest.mark.integration
async def test_publish_blocked_when_not_pending(
    http_client_admin: AsyncClient,
    cleanup_drafts: None,
) -> None:
    app.dependency_overrides[verify_jwt] = _override(
        _claims(_ADMIN_TECNICO_ID)
    )
    response = await http_client_admin.post(
        f"/api/admin/rules/{uuid4()}/publish",
        headers={"Authorization": "Bearer fake"},
    )
    assert response.status_code == 409


@pytest.mark.integration
async def test_validate_schema_accepts_well_formed_rule(
    http_client_admin: AsyncClient,
) -> None:
    app.dependency_overrides[verify_jwt] = _override(_claims(_CONTADOR_ID))

    response = await http_client_admin.post(
        "/api/admin/rules/validate-schema",
        json={
            "domain": "regime_eligibility",
            "rules": {
                "all_of": [
                    {"field": "ingresos_promedio_3a_uf",
                     "op": "lte", "value": 75000}
                ]
            },
        },
        headers={"Authorization": "Bearer fake"},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["valid"] is True
    assert data["errors"] == []
    assert "regime_eligibility" in data["domains_disponibles"]


@pytest.mark.integration
async def test_validate_schema_rejects_malformed_rule(
    http_client_admin: AsyncClient,
) -> None:
    app.dependency_overrides[verify_jwt] = _override(_claims(_CONTADOR_ID))

    response = await http_client_admin.post(
        "/api/admin/rules/validate-schema",
        json={
            "domain": "regime_eligibility",
            "rules": {
                "all_of": [
                    {"field": "x", "op": "operador_invalido", "value": 1}
                ]
            },
        },
        headers={"Authorization": "Bearer fake"},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["valid"] is False
    assert len(data["errors"]) >= 1


@pytest.mark.integration
async def test_validate_schema_unknown_domain(
    http_client_admin: AsyncClient,
) -> None:
    app.dependency_overrides[verify_jwt] = _override(_claims(_CONTADOR_ID))

    response = await http_client_admin.post(
        "/api/admin/rules/validate-schema",
        json={"domain": "no-existe", "rules": {}},
        headers={"Authorization": "Bearer fake"},
    )
    data = response.json()
    assert data["valid"] is False
    assert "no schema file" in data["errors"][0]["message"]


@pytest.mark.integration
async def test_dry_run_rejects_non_eligibility_domain(
    http_client_admin: AsyncClient,
) -> None:
    """Dry-run MVP solo soporta regime_eligibility."""
    app.dependency_overrides[verify_jwt] = _override(_claims(_CONTADOR_ID))

    # Buscar id de la regla recomendacion_whitelist seedeada.
    listing = await http_client_admin.get(
        "/api/admin/rules?domain=recomendacion_whitelist",
        headers={"Authorization": "Bearer fake"},
    )
    rule_id = listing.json()["rule_sets"][0]["id"]

    response = await http_client_admin.post(
        f"/api/admin/rules/{rule_id}/dry-run",
        headers={"Authorization": "Bearer fake"},
    )
    assert response.status_code == 422


@pytest.mark.integration
async def test_dry_run_evaluates_eligibility_rule(
    http_client_admin: AsyncClient,
) -> None:
    """Sobre la regla 14_d_3 publicada, dry-run no debe romper aunque
    no haya recomendaciones persistidas (cuenta 0 evaluadas)."""
    app.dependency_overrides[verify_jwt] = _override(_claims(_CONTADOR_ID))

    listing = await http_client_admin.get(
        "/api/admin/rules?domain=regime_eligibility&status_filter=published",
        headers={"Authorization": "Bearer fake"},
    )
    rules = listing.json()["rule_sets"]
    rule_14d3 = next(r for r in rules if r["key"] == "14_d_3")

    response = await http_client_admin.post(
        f"/api/admin/rules/{rule_14d3['id']}/dry-run",
        headers={"Authorization": "Bearer fake"},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["domain"] == "regime_eligibility"
    assert data["key"] == "14_d_3"
    assert data["evaluadas"] >= 0
    assert data["pasaban_antes"] >= 0
    assert data["pasan_ahora"] >= 0


@pytest.mark.integration
async def test_deprecate_rule(
    http_client_admin: AsyncClient,
    cleanup_drafts: None,
) -> None:
    app.dependency_overrides[verify_jwt] = _override(_claims(_CONTADOR_ID))
    created = await http_client_admin.post(
        "/api/admin/rules",
        json={
            "domain": "test_admin",
            "key": "deprecar",
            "vigencia_desde": "2027-01-01",
            "rules": {
                "all_of": [{"field": "x", "op": "eq", "value": 0}]
            },
            "fuente_legal": [{"tipo": "ley", "id": "DEP"}],
        },
        headers={"Authorization": "Bearer fake"},
    )
    rule_id = created.json()["id"]

    response = await http_client_admin.post(
        f"/api/admin/rules/{rule_id}/deprecate",
        headers={"Authorization": "Bearer fake"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "deprecated"
