"""Tests integration de GET /api/empresas/{id}/wizard-prefill (track 1
post skill 4): el endpoint deriva ventas / ingresos del RCV ya
sincronizado y devuelve warnings cuando falta data."""

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
async def http_client_pf() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        yield client
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def empresa_with_rcv(
    admin_session: AsyncSession,
) -> AsyncIterator[dict[str, UUID]]:
    """Empresa con líneas RCV de ventas para 2024 y 2025 (tax_year 2026)."""
    user_id = uuid4()
    workspace_id = uuid4()
    empresa_id = uuid4()

    # uf_valor_clp seed (track 11b) está en la BD; consultamos para conversión.
    async with admin_session.begin():
        await admin_session.execute(
            text("insert into auth.users (id, email) values (:id, :e)"),
            {"id": str(user_id), "e": f"pf-{user_id}@renteo.local"},
        )
        await admin_session.execute(
            text(
                "insert into core.workspaces (id, name, type) "
                "values (:id, 'Prefill test', 'pyme')"
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
        await admin_session.execute(
            text(
                """
                insert into core.empresas
                    (id, workspace_id, rut, razon_social,
                     regimen_actual, capital_inicial_uf)
                values (:e, :ws, '11111111-1', 'Prefill SpA',
                        '14_d_3', 5000)
                """
            ),
            {"e": str(empresa_id), "ws": str(workspace_id)},
        )
        # Plantamos ventas anuales: 2024 = 380M (10.000 UF), 2025 = 760M (20.000 UF).
        # uf_valor_clp seeded como 38000.
        for period, total in (
            ("2024-06", Decimal("190000000")),
            ("2024-12", Decimal("190000000")),
            ("2025-06", Decimal("380000000")),
            ("2025-12", Decimal("380000000")),
        ):
            await admin_session.execute(
                text(
                    """
                    insert into tax_data.rcv_lines
                        (workspace_id, empresa_id, period, tipo,
                         neto, iva, total)
                    values
                        (:ws, :emp, :p, 'venta', :n, :i, :t)
                    """
                ),
                {
                    "ws": str(workspace_id),
                    "emp": str(empresa_id),
                    "p": period,
                    "n": total / Decimal("1.19"),
                    "i": total - (total / Decimal("1.19")),
                    "t": total,
                },
            )
    yield {
        "user_id": user_id,
        "workspace_id": workspace_id,
        "empresa_id": empresa_id,
    }
    async with admin_session.begin():
        await admin_session.execute(
            text("set local session_replication_role = 'replica'")
        )
        await admin_session.execute(
            text(
                "delete from tax_data.rcv_lines where workspace_id = :w"
            ),
            {"w": str(workspace_id)},
        )
        await admin_session.execute(
            text("delete from core.empresas where workspace_id = :w"),
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


@pytest.mark.integration
async def test_prefill_computes_uf_from_rcv_ventas(
    http_client_pf: AsyncClient, empresa_with_rcv: dict[str, UUID]
) -> None:
    app.dependency_overrides[verify_jwt] = _override_jwt(
        _claims(empresa_with_rcv["user_id"], empresa_with_rcv["workspace_id"])
    )
    response = await http_client_pf.get(
        f"/api/empresas/{empresa_with_rcv['empresa_id']}"
        f"/wizard-prefill?tax_year=2026",
        headers={"Authorization": "Bearer fake"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    # ventas_anuales_uf = 760M / 38000 = 20000
    assert Decimal(body["ventas_anuales_uf"]) == Decimal("20000.00")
    # promedio (2024+2025)/2 = (10000+20000)/2 = 15000
    assert Decimal(body["ingresos_promedio_3a_uf"]) == Decimal("15000.00")
    # max
    assert Decimal(body["ingresos_max_anual_uf"]) == Decimal("20000.00")
    assert body["regimen_actual"] == "14_d_3"
    assert Decimal(body["capital_efectivo_inicial_uf"]) == Decimal("5000")
    assert sorted(body["anios_con_datos"]) == [2024, 2025]
    # Solo 2 años de los 3 esperados → warning informativo.
    assert any("menos de 3 años" in w for w in body["warnings"])


@pytest.mark.integration
async def test_prefill_warns_when_no_rcv(
    http_client_pf: AsyncClient,
    empresa_with_rcv: dict[str, UUID],
    admin_session: AsyncSession,
) -> None:
    """Borramos el RCV para reproducir el caso 'sin sync previa'."""
    app.dependency_overrides[verify_jwt] = _override_jwt(
        _claims(empresa_with_rcv["user_id"], empresa_with_rcv["workspace_id"])
    )
    async with admin_session.begin():
        await admin_session.execute(
            text(
                "delete from tax_data.rcv_lines where empresa_id = :e"
            ),
            {"e": str(empresa_with_rcv["empresa_id"])},
        )
    response = await http_client_pf.get(
        f"/api/empresas/{empresa_with_rcv['empresa_id']}"
        f"/wizard-prefill?tax_year=2026",
        headers={"Authorization": "Bearer fake"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["ventas_anuales_uf"] is None
    assert body["ingresos_promedio_3a_uf"] is None
    assert body["ingresos_max_anual_uf"] is None
    assert body["anios_con_datos"] == []
    assert any("Sincroniza con SII" in w for w in body["warnings"])


@pytest.mark.integration
async def test_prefill_404_for_unknown_empresa(
    http_client_pf: AsyncClient, empresa_with_rcv: dict[str, UUID]
) -> None:
    app.dependency_overrides[verify_jwt] = _override_jwt(
        _claims(empresa_with_rcv["user_id"], empresa_with_rcv["workspace_id"])
    )
    response = await http_client_pf.get(
        f"/api/empresas/{uuid4()}/wizard-prefill?tax_year=2026",
        headers={"Authorization": "Bearer fake"},
    )
    assert response.status_code == 404


@pytest.mark.integration
async def test_prefill_rejects_out_of_range_year(
    http_client_pf: AsyncClient, empresa_with_rcv: dict[str, UUID]
) -> None:
    app.dependency_overrides[verify_jwt] = _override_jwt(
        _claims(empresa_with_rcv["user_id"], empresa_with_rcv["workspace_id"])
    )
    response = await http_client_pf.get(
        f"/api/empresas/{empresa_with_rcv['empresa_id']}"
        f"/wizard-prefill?tax_year=2050",
        headers={"Authorization": "Bearer fake"},
    )
    assert response.status_code == 422
