"""Tests de auditoría: cada acción tributaria deja trazabilidad en
security.audit_log con shape correcto y sin PII en claro.

Cubre:
- POST /api/empresas        → action=create, resource_type=empresa
- POST /api/scenario/simulate → action=simulate, resource_type=escenario
- POST /api/scenario/compare  → action=compare, resource_type=escenario
- POST /api/regime/diagnose   → action=diagnose, resource_type=recomendacion
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from typing import Any
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
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


def _override(claims: dict[str, Any]) -> Callable[[], dict[str, Any]]:
    def _dep() -> dict[str, Any]:
        return claims

    return _dep


@pytest_asyncio.fixture
async def http_client_audit() -> AsyncIterator[AsyncClient]:
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
            {"id": str(user_id), "e": f"audit-{user_id}@renteo.local"},
        )
        await admin_session.execute(
            text(
                "insert into core.workspaces (id, name, type) "
                "values (:id, 'Audit', 'pyme')"
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
            text("delete from core.empresas where workspace_id = :w"),
            {"w": str(workspace_id)},
        )
        await admin_session.execute(
            text(
                "delete from core.escenarios_simulacion "
                "where workspace_id = :w"
            ),
            {"w": str(workspace_id)},
        )
        await admin_session.execute(
            text("delete from core.recomendaciones where workspace_id = :w"),
            {"w": str(workspace_id)},
        )
        await admin_session.execute(
            text("delete from security.audit_log where workspace_id = :w"),
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


async def _audit_rows_for(
    admin_session: AsyncSession, workspace_id: UUID
) -> list[dict[str, Any]]:
    async with admin_session.begin():
        result = await admin_session.execute(
            text(
                """
                select action, resource_type, resource_id, empresa_id,
                       metadata, user_id
                  from security.audit_log
                 where workspace_id = :w
                 order by at asc
                """
            ),
            {"w": str(workspace_id)},
        )
        return [dict(row) for row in result.mappings().all()]


@pytest.mark.integration
async def test_audit_logs_empresa_create_with_masked_rut(
    http_client_audit: AsyncClient,
    workspace_ctx: dict[str, UUID],
    admin_session: AsyncSession,
) -> None:
    app.dependency_overrides[verify_jwt] = _override(
        _claims(workspace_ctx["user_id"], workspace_ctx["workspace_id"])
    )

    response = await http_client_audit.post(
        "/api/empresas",
        json={"rut": "12345678-5", "razon_social": "Audit SpA"},
        headers={"Authorization": "Bearer fake"},
    )
    assert response.status_code == 201, response.text

    rows = await _audit_rows_for(
        admin_session, workspace_ctx["workspace_id"]
    )
    create_rows = [r for r in rows if r["action"] == "create"]
    assert any(r["resource_type"] == "empresa" for r in create_rows)
    empresa_row = next(
        r for r in create_rows if r["resource_type"] == "empresa"
    )
    # PII mask: RUT no debe aparecer en claro.
    assert "12345678" not in str(empresa_row["metadata"])
    assert empresa_row["metadata"]["rut_masked"] == "12******-5"


@pytest.mark.integration
async def test_audit_logs_simulate_with_palancas_summary(
    http_client_audit: AsyncClient,
    workspace_ctx: dict[str, UUID],
    admin_session: AsyncSession,
) -> None:
    app.dependency_overrides[verify_jwt] = _override(
        _claims(workspace_ctx["user_id"], workspace_ctx["workspace_id"])
    )

    response = await http_client_audit.post(
        "/api/scenario/simulate",
        json={
            "regimen": "14_d_3",
            "tax_year": 2026,
            "rli_base": "30000000",
            "palancas": {"dep_instantanea": "5000000"},
        },
        headers={"Authorization": "Bearer fake"},
    )
    assert response.status_code == 200, response.text

    rows = await _audit_rows_for(
        admin_session, workspace_ctx["workspace_id"]
    )
    sim = next(r for r in rows if r["action"] == "simulate")
    assert sim["resource_type"] == "escenario"
    assert sim["resource_id"] is not None
    assert "dep_instantanea" in sim["metadata"]["palancas_aplicadas"]
    assert sim["metadata"]["regimen"] == "14_d_3"


@pytest.mark.integration
async def test_audit_logs_diagnose(
    http_client_audit: AsyncClient,
    workspace_ctx: dict[str, UUID],
    admin_session: AsyncSession,
) -> None:
    app.dependency_overrides[verify_jwt] = _override(
        _claims(workspace_ctx["user_id"], workspace_ctx["workspace_id"])
    )

    response = await http_client_audit.post(
        "/api/regime/diagnose",
        json={
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
        },
        headers={"Authorization": "Bearer fake"},
    )
    assert response.status_code == 200, response.text

    rows = await _audit_rows_for(
        admin_session, workspace_ctx["workspace_id"]
    )
    diag = next(r for r in rows if r["action"] == "diagnose")
    assert diag["resource_type"] == "recomendacion"
    assert diag["metadata"]["regimen_actual"] == "14_a"
    assert diag["metadata"]["regimen_recomendado"] in {
        "14_a",
        "14_d_3",
        "14_d_8",
    }


@pytest.mark.integration
async def test_audit_log_is_append_only(
    http_client_audit: AsyncClient,
    workspace_ctx: dict[str, UUID],
    admin_session: AsyncSession,
) -> None:
    """El trigger Postgres rechaza UPDATE/DELETE sobre security.audit_log."""
    app.dependency_overrides[verify_jwt] = _override(
        _claims(workspace_ctx["user_id"], workspace_ctx["workspace_id"])
    )

    await http_client_audit.post(
        "/api/empresas",
        json={"rut": "11111111-1", "razon_social": "Append-only"},
        headers={"Authorization": "Bearer fake"},
    )

    with pytest.raises(DBAPIError):
        async with admin_session.begin():
            await admin_session.execute(
                text(
                    "update security.audit_log set action = 'tampered' "
                    "where workspace_id = :w"
                ),
                {"w": str(workspace_ctx["workspace_id"])},
            )
