"""Tests integration de POST /api/regime/diagnose (skill 7)."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.jwt import verify_jwt
from src.main import app


def _claims(user_id: UUID, workspace_id: UUID) -> dict[str, Any]:
    return {
        "sub": str(user_id),
        "aud": "authenticated",
        "role": "authenticated",
        "app_metadata": {
            "provider": "email",
            "workspace_id": str(workspace_id),
            "workspace_type": "pyme",
            "role": "owner",
            "empresa_ids": [],
        },
    }


def _override_jwt(claims: dict[str, Any]) -> Callable[[], dict[str, Any]]:
    def _dep() -> dict[str, Any]:
        return claims

    return _dep


@pytest_asyncio.fixture
async def http_client_reg() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        yield client
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def workspace_ctx(
    admin_session: AsyncSession,
) -> AsyncIterator[dict[str, UUID]]:
    user_id = uuid4()
    workspace_id = uuid4()
    async with admin_session.begin():
        await admin_session.execute(
            text("insert into auth.users (id, email) values (:id, :e)"),
            {"id": str(user_id), "e": f"reg-{user_id}@renteo.local"},
        )
        await admin_session.execute(
            text(
                "insert into core.workspaces (id, name, type) "
                "values (:id, 'Reg test', 'pyme')"
            ),
            {"id": str(workspace_id)},
        )
        await admin_session.execute(
            text(
                "insert into core.workspace_members "
                "(workspace_id, user_id, role, accepted_at) "
                "values (:ws, :u, 'owner', now())"
            ),
            {"ws": str(workspace_id), "u": str(user_id)},
        )
    yield {"user_id": user_id, "workspace_id": workspace_id}
    async with admin_session.begin():
        await admin_session.execute(
            text("set local session_replication_role = 'replica'")
        )
        # `replica` desactiva regular triggers — incluidas las FK
        # cascade. Limpiamos las recomendaciones explícitamente para
        # no dejar filas huérfanas que contaminen tests posteriores.
        await admin_session.execute(
            text(
                "delete from core.recomendaciones where workspace_id = :id"
            ),
            {"id": str(workspace_id)},
        )
        await admin_session.execute(
            text("delete from core.workspaces where id = :id"),
            {"id": str(workspace_id)},
        )
        await admin_session.execute(
            text("delete from auth.users where id = :id"),
            {"id": str(user_id)},
        )


_DEFAULT_BODY: dict[str, Any] = {
    "tax_year": 2026,
    "regimen_actual": "14_a",
    "ingresos_promedio_3a_uf": "30000",
    "ingresos_max_anual_uf": "40000",
    "capital_efectivo_inicial_uf": "5000",
    "pct_ingresos_pasivos": "0.10",
    "todos_duenos_personas_naturales_chile": True,
    "participacion_empresas_no_14d_sobre_10pct": False,
    "sector": "comercio",
    "ventas_anuales_uf": "30000",
    "rli_proyectada_anual_uf": "1000",
    "plan_retiros_pct": "0.30",
}


@pytest.mark.integration
async def test_diagnose_pyme_chilena_recommends_14d(
    http_client_reg: AsyncClient, workspace_ctx: dict[str, UUID]
) -> None:
    app.dependency_overrides[verify_jwt] = _override_jwt(
        _claims(workspace_ctx["user_id"], workspace_ctx["workspace_id"])
    )

    response = await http_client_reg.post(
        "/api/regime/diagnose",
        json=_DEFAULT_BODY,
        headers={"Authorization": "Bearer fake"},
    )

    assert response.status_code == 200, response.text
    data = response.json()

    elegibles = {e["regimen"] for e in data["elegibilidad"] if e["elegible"]}
    assert {"14_a", "14_d_3", "14_d_8"}.issubset(elegibles)
    assert data["veredicto"]["regimen_recomendado"] in {
        "14_d_3",
        "14_d_8",
    }
    assert Decimal(data["veredicto"]["ahorro_3a_clp"]) >= Decimal("0")
    assert data["proyeccion_dual_14d3"] is not None
    assert data["proyeccion_dual_14d3"]["base"]["es_transitoria"] is True
    # Track 7b: el diagnóstico se persiste y la response trae id +
    # disclaimer_version + engine_version.
    from uuid import UUID as _UUID

    assert _UUID(data["id"])
    assert data["disclaimer_version"] == "v1"
    assert data["engine_version"].startswith("track-7b")


@pytest.mark.integration
async def test_diagnose_high_passive_excludes_14d(
    http_client_reg: AsyncClient, workspace_ctx: dict[str, UUID]
) -> None:
    """50% pasivos descalifica 14 D N°3 y 14 D N°8."""
    app.dependency_overrides[verify_jwt] = _override_jwt(
        _claims(workspace_ctx["user_id"], workspace_ctx["workspace_id"])
    )
    body = {**_DEFAULT_BODY, "pct_ingresos_pasivos": "0.50"}

    response = await http_client_reg.post(
        "/api/regime/diagnose",
        json=body,
        headers={"Authorization": "Bearer fake"},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    by_regimen = {e["regimen"]: e for e in data["elegibilidad"]}
    assert by_regimen["14_d_3"]["elegible"] is False
    assert by_regimen["14_d_8"]["elegible"] is False
    assert data["veredicto"]["regimen_recomendado"] == "14_a"


@pytest.mark.integration
async def test_diagnose_foreign_owner_excludes_14d8(
    http_client_reg: AsyncClient, workspace_ctx: dict[str, UUID]
) -> None:
    app.dependency_overrides[verify_jwt] = _override_jwt(
        _claims(workspace_ctx["user_id"], workspace_ctx["workspace_id"])
    )
    body = {
        **_DEFAULT_BODY,
        "todos_duenos_personas_naturales_chile": False,
    }

    response = await http_client_reg.post(
        "/api/regime/diagnose",
        json=body,
        headers={"Authorization": "Bearer fake"},
    )
    data = response.json()
    by_regimen = {e["regimen"]: e for e in data["elegibilidad"]}
    assert by_regimen["14_d_3"]["elegible"] is True
    assert by_regimen["14_d_8"]["elegible"] is False


@pytest.mark.integration
async def test_diagnose_agricola_exposes_renta_presunta(
    http_client_reg: AsyncClient, workspace_ctx: dict[str, UUID]
) -> None:
    """Sector agrícola con ventas bajo 9.000 UF → renta presunta elegible."""
    app.dependency_overrides[verify_jwt] = _override_jwt(
        _claims(workspace_ctx["user_id"], workspace_ctx["workspace_id"])
    )
    body = {
        **_DEFAULT_BODY,
        "sector": "agricola",
        "ventas_anuales_uf": "5000",
        "ingresos_promedio_3a_uf": "5000",
        "ingresos_max_anual_uf": "6000",
    }

    response = await http_client_reg.post(
        "/api/regime/diagnose",
        json=body,
        headers={"Authorization": "Bearer fake"},
    )
    data = response.json()
    by_regimen = {e["regimen"]: e for e in data["elegibilidad"]}
    assert by_regimen["renta_presunta"]["elegible"] is True


@pytest.mark.integration
async def test_diagnose_requires_tenancy(
    http_client_reg: AsyncClient,
) -> None:
    user_id = uuid4()
    app.dependency_overrides[verify_jwt] = _override_jwt(
        {
            "sub": str(user_id),
            "aud": "authenticated",
            "role": "authenticated",
            "app_metadata": {"provider": "email"},
        }
    )

    response = await http_client_reg.post(
        "/api/regime/diagnose",
        json=_DEFAULT_BODY,
        headers={"Authorization": "Bearer fake"},
    )
    assert response.status_code == 403


@pytest.mark.integration
async def test_diagnose_rejects_invalid_pct(
    http_client_reg: AsyncClient, workspace_ctx: dict[str, UUID]
) -> None:
    app.dependency_overrides[verify_jwt] = _override_jwt(
        _claims(workspace_ctx["user_id"], workspace_ctx["workspace_id"])
    )
    body = {**_DEFAULT_BODY, "pct_ingresos_pasivos": "1.5"}

    response = await http_client_reg.post(
        "/api/regime/diagnose",
        json=body,
        headers={"Authorization": "Bearer fake"},
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Track 7b — persistencia y listado
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_recomendaciones_listed_after_diagnose(
    http_client_reg: AsyncClient, workspace_ctx: dict[str, UUID]
) -> None:
    app.dependency_overrides[verify_jwt] = _override_jwt(
        _claims(workspace_ctx["user_id"], workspace_ctx["workspace_id"])
    )

    # Baseline: el listado puede traer filas residuales de otros tests
    # si el cleanup falla; solo verificamos que el diagnóstico nuevo
    # quede listado y sume exactamente 1.
    initial = await http_client_reg.get(
        "/api/regime/recomendaciones",
        headers={"Authorization": "Bearer fake"},
    )
    assert initial.status_code == 200
    initial_count = len(initial.json()["recomendaciones"])

    diagnose = await http_client_reg.post(
        "/api/regime/diagnose",
        json=_DEFAULT_BODY,
        headers={"Authorization": "Bearer fake"},
    )
    assert diagnose.status_code == 200, diagnose.text
    rec_id = diagnose.json()["id"]

    listed = await http_client_reg.get(
        "/api/regime/recomendaciones",
        headers={"Authorization": "Bearer fake"},
    )
    assert listed.status_code == 200
    items = listed.json()["recomendaciones"]
    assert len(items) == initial_count + 1
    nuevo = next(i for i in items if i["id"] == rec_id)
    assert nuevo["tipo"] == "cambio_regimen"
    assert nuevo["regimen_actual"] == "14_a"
    assert nuevo["disclaimer_version"] == "v1"


@pytest.mark.integration
async def test_recomendaciones_filter_by_year(
    http_client_reg: AsyncClient, workspace_ctx: dict[str, UUID]
) -> None:
    app.dependency_overrides[verify_jwt] = _override_jwt(
        _claims(workspace_ctx["user_id"], workspace_ctx["workspace_id"])
    )
    for year in (2025, 2026):
        body = {**_DEFAULT_BODY, "tax_year": year}
        r = await http_client_reg.post(
            "/api/regime/diagnose",
            json=body,
            headers={"Authorization": "Bearer fake"},
        )
        assert r.status_code == 200, r.text

    response = await http_client_reg.get(
        "/api/regime/recomendaciones?tax_year=2025",
        headers={"Authorization": "Bearer fake"},
    )
    # El filtro server-side debe excluir 2026, sin asumir cardinalidad
    # exacta (otros tests pueden dejar filas residuales con tax_year=2025).
    years = {r["tax_year"] for r in response.json()["recomendaciones"]}
    assert years.issubset({2025})
    assert 2025 in years
