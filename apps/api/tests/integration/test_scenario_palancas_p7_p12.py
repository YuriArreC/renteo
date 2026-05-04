"""Tests integration de las 5 palancas restantes del simulador
(P7-P12, cierre skill 8). Verifican: aplicación + monto, eligibilidad
por régimen, banderas amarillas y efectos sobre RLI / créditos /
régimen objetivo."""

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


def _claims(
    user_id: UUID,
    workspace_id: UUID,
    *,
    role: str = "owner",
    workspace_type: str = "pyme",
) -> dict[str, Any]:
    return {
        "sub": str(user_id),
        "aud": "authenticated",
        "role": "authenticated",
        "app_metadata": {
            "provider": "email",
            "workspace_id": str(workspace_id),
            "workspace_type": workspace_type,
            "role": role,
            "empresa_ids": [],
        },
    }


def _override_jwt(claims: dict[str, Any]) -> Callable[[], dict[str, Any]]:
    def _dep() -> dict[str, Any]:
        return claims

    return _dep


@pytest_asyncio.fixture
async def http_client_p7_12() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        yield client
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def workspace_p7_12(
    admin_session: AsyncSession,
) -> AsyncIterator[dict[str, UUID]]:
    user_id = uuid4()
    workspace_id = uuid4()
    async with admin_session.begin():
        await admin_session.execute(
            text("insert into auth.users (id, email) values (:id, :e)"),
            {"id": str(user_id), "e": f"p7p12-{user_id}@renteo.local"},
        )
        await admin_session.execute(
            text(
                "insert into core.workspaces (id, name, type) "
                "values (:id, 'P7-P12 test', 'pyme')"
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
        await admin_session.execute(
            text(
                "delete from core.escenarios_simulacion where workspace_id = :w"
            ),
            {"w": str(workspace_id)},
        )
        await admin_session.execute(
            text("delete from core.workspaces where id = :w"),
            {"w": str(workspace_id)},
        )
        await admin_session.execute(
            text("delete from auth.users where id = :u"),
            {"u": str(user_id)},
        )


def _impacto(data: dict[str, Any], palanca_id: str) -> dict[str, Any]:
    return next(
        p
        for p in data["palancas_aplicadas"]
        if p["palanca_id"] == palanca_id
    )


@pytest.mark.integration
async def test_p7_ppm_extraordinario_no_reduce_carga(
    http_client_p7_12: AsyncClient, workspace_p7_12: dict[str, UUID]
) -> None:
    """P7 mejora flujo, no carga total. ahorro_total debe ser 0."""
    app.dependency_overrides[verify_jwt] = _override_jwt(
        _claims(workspace_p7_12["user_id"], workspace_p7_12["workspace_id"])
    )
    response = await http_client_p7_12.post(
        "/api/scenario/simulate",
        json={
            "regimen": "14_d_3",
            "tax_year": 2026,
            "rli_base": "100000000",
            "palancas": {"ppm_extraordinario_monto": "500000"},
        },
        headers={"Authorization": "Bearer fake"},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    ppm = _impacto(data, "ppm_extraordinario")
    assert ppm["aplicada"] is True
    assert Decimal(ppm["monto_aplicado"]) == Decimal("500000")
    assert Decimal(data["ahorro_total"]) == Decimal("0")


@pytest.mark.integration
async def test_p8_iva_postergacion_blocked_for_14a(
    http_client_p7_12: AsyncClient, workspace_p7_12: dict[str, UUID]
) -> None:
    app.dependency_overrides[verify_jwt] = _override_jwt(
        _claims(workspace_p7_12["user_id"], workspace_p7_12["workspace_id"])
    )
    response = await http_client_p7_12.post(
        "/api/scenario/simulate",
        json={
            "regimen": "14_a",
            "tax_year": 2026,
            "rli_base": "30000000",
            "palancas": {"iva_postergacion_aplicada": True},
        },
        headers={"Authorization": "Bearer fake"},
    )
    assert response.status_code == 422
    assert "art. 64 N°9 CT" in response.json()["detail"]


@pytest.mark.integration
async def test_p10_credito_reinversion_blocked_for_14d8(
    http_client_p7_12: AsyncClient, workspace_p7_12: dict[str, UUID]
) -> None:
    app.dependency_overrides[verify_jwt] = _override_jwt(
        _claims(workspace_p7_12["user_id"], workspace_p7_12["workspace_id"])
    )
    response = await http_client_p7_12.post(
        "/api/scenario/simulate",
        json={
            "regimen": "14_d_8",
            "tax_year": 2026,
            "rli_base": "30000000",
            "palancas": {"credito_reinversion_monto": "5000000"},
        },
        headers={"Authorization": "Bearer fake"},
    )
    assert response.status_code == 422
    assert "33 bis" in response.json()["detail"]


@pytest.mark.integration
async def test_p10_credito_reinversion_credit_capped_by_topen(
    http_client_p7_12: AsyncClient, workspace_p7_12: dict[str, UUID]
) -> None:
    """Inversión enorme dispara bandera amarilla y queda capped en el tope."""
    app.dependency_overrides[verify_jwt] = _override_jwt(
        _claims(workspace_p7_12["user_id"], workspace_p7_12["workspace_id"])
    )
    response = await http_client_p7_12.post(
        "/api/scenario/simulate",
        json={
            "regimen": "14_d_3",
            "tax_year": 2026,
            "rli_base": "100000000",
            "palancas": {"credito_reinversion_monto": "10000000000"},
        },
        headers={"Authorization": "Bearer fake"},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    cred = _impacto(data, "credito_reinversion")
    assert cred["aplicada"] is True
    # tope = 500 UTM * 70.000 CLP = 35.000.000
    assert Decimal(cred["monto_aplicado"]) <= Decimal("35000000")
    banderas = {b["palanca_id"] for b in data["banderas"]}
    assert "credito_reinversion" in banderas


@pytest.mark.integration
async def test_p11_depreciacion_acelerada_reduces_rli(
    http_client_p7_12: AsyncClient, workspace_p7_12: dict[str, UUID]
) -> None:
    app.dependency_overrides[verify_jwt] = _override_jwt(
        _claims(workspace_p7_12["user_id"], workspace_p7_12["workspace_id"])
    )
    response = await http_client_p7_12.post(
        "/api/scenario/simulate",
        json={
            "regimen": "14_d_3",
            "tax_year": 2026,
            "rli_base": "30000000",
            "palancas": {"depreciacion_acelerada_monto": "8000000"},
        },
        headers={"Authorization": "Bearer fake"},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert Decimal(data["simulado"]["rli"]) == Decimal("22000000")
    assert Decimal(data["ahorro_total"]) > Decimal("0")


@pytest.mark.integration
async def test_p12_cambio_regimen_recomputes_simulado_under_target(
    http_client_p7_12: AsyncClient, workspace_p7_12: dict[str, UUID]
) -> None:
    """P12 cambia el régimen del simulado. El base sigue siendo el actual."""
    app.dependency_overrides[verify_jwt] = _override_jwt(
        _claims(workspace_p7_12["user_id"], workspace_p7_12["workspace_id"])
    )
    response = await http_client_p7_12.post(
        "/api/scenario/simulate",
        json={
            "regimen": "14_a",
            "tax_year": 2026,
            "rli_base": "100000000",
            "retiros_base": "30000000",
            "palancas": {"cambio_regimen_objetivo": "14_d_3"},
        },
        headers={"Authorization": "Bearer fake"},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    cambio = _impacto(data, "cambio_regimen")
    assert cambio["aplicada"] is True
    # 14 D N°3 con tasa transitoria <= 14 A → simulado IDPC < base IDPC.
    assert Decimal(data["simulado"]["idpc"]) < Decimal(data["base"]["idpc"])


@pytest.mark.integration
async def test_p12_rejects_same_regimen(
    http_client_p7_12: AsyncClient, workspace_p7_12: dict[str, UUID]
) -> None:
    app.dependency_overrides[verify_jwt] = _override_jwt(
        _claims(workspace_p7_12["user_id"], workspace_p7_12["workspace_id"])
    )
    response = await http_client_p7_12.post(
        "/api/scenario/simulate",
        json={
            "regimen": "14_d_3",
            "tax_year": 2026,
            "rli_base": "30000000",
            "palancas": {"cambio_regimen_objetivo": "14_d_3"},
        },
        headers={"Authorization": "Bearer fake"},
    )
    assert response.status_code == 422
    assert "distinto del actual" in response.json()["detail"]
