"""RLS a través del `tenant_session` REAL de la app (src.db), no del de tests.

POR QUÉ EXISTE ESTE ARCHIVO

`tests/integration/conftest.py` define su propio `tenant_session` que hace
`set_config('role', 'authenticated')` antes de inyectar los claims. Gracias a
eso, toda la suite de RLS (`test_rls_isolation`, `test_rls_exhaustivo`) pasaba
en verde… validando las POLICIES, pero no el wiring real de la aplicación.

El `tenant_session` de producción (`src/db.py`) NO bajaba el rol: solo seteaba
`request.jwt.claims`. Y los claims por sí solos no activan RLS — Postgres omite
las policies cuando el rol conectado es superusuario o tiene BYPASSRLS, que es
justo lo que es el rol de `DATABASE_URL` (`postgres` local, `service_role` en
Supabase). Resultado: en la app, RLS estaba de hecho APAGADA, y cualquier query
que confiara solo en RLS —como la de `/api/cartera`, que no filtra por
`workspace_id` en SQL— devolvía filas de TODOS los tenants.

Los tests de acá cierran ese hueco: usan `src.db.tenant_session`, el mismo
código que corre en producción. Si alguien vuelve a quitar el `SET LOCAL role`,
esto se pone rojo.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import tenant_session

pytestmark = pytest.mark.asyncio


def _claims(user_id: UUID, workspace_id: UUID) -> dict[str, object]:
    return {
        "sub": str(user_id),
        "role": "authenticated",
        "email": "tenant@renteo.local",
        "app_metadata": {
            "workspace_id": str(workspace_id),
            "workspace_type": "pyme",
            "role": "owner",
            "empresa_ids": [],
        },
    }


async def _seed_workspace(session: AsyncSession) -> tuple[UUID, UUID, UUID]:
    """Crea (user, workspace, empresa) aislados. Devuelve sus ids."""
    user_id, workspace_id, empresa_id = uuid4(), uuid4(), uuid4()
    await session.execute(
        text("insert into auth.users (id, email) values (:i, :e)"),
        {"i": str(user_id), "e": f"{user_id}@renteo.local"},
    )
    await session.execute(
        text(
            "insert into core.workspaces (id, name, type) "
            "values (:i, 'RLS probe', 'pyme')"
        ),
        {"i": str(workspace_id)},
    )
    await session.execute(
        text(
            "insert into core.workspace_members "
            "(workspace_id, user_id, role, accepted_at) "
            "values (:w, :u, 'owner', now())"
        ),
        {"w": str(workspace_id), "u": str(user_id)},
    )
    await session.execute(
        text(
            "insert into core.empresas "
            "(id, workspace_id, rut, razon_social, regimen_actual) "
            "values (:i, :w, :r, 'RLS probe SpA', '14_a')"
        ),
        {
            "i": str(empresa_id),
            "w": str(workspace_id),
            "r": f"{str(uuid4().int)[:8]}-1",
        },
    )
    return user_id, workspace_id, empresa_id


async def test_la_sesion_de_la_app_baja_el_rol_a_authenticated(
    admin_session: AsyncSession,
) -> None:
    """El `SET LOCAL role` es lo que hace que RLS exista. Sin él, nada aplica."""
    user_id, workspace_id, _ = await _seed_workspace(admin_session)
    await admin_session.commit()

    async with tenant_session(_claims(user_id, workspace_id)) as session:
        rol = (await session.execute(text("select current_user"))).scalar_one()

    assert rol == "authenticated", (
        f"la sesión de la app corre como {rol!r}. Si ese rol es superusuario o "
        f"tiene BYPASSRLS, TODAS las policies multi-tenant quedan inertes."
    )


async def test_un_tenant_no_ve_las_empresas_de_otro(
    admin_session: AsyncSession,
) -> None:
    """El caso que estaba roto: aislamiento por el camino real de la app.

    Se crean dos workspaces con una empresa cada uno. El tenant A consulta
    `core.empresas` SIN filtrar por workspace_id en el SQL — exactamente como
    hace `/api/cartera`. Solo RLS puede salvarlo.
    """
    user_a, ws_a, emp_a = await _seed_workspace(admin_session)
    _user_b, _ws_b, emp_b = await _seed_workspace(admin_session)
    await admin_session.commit()

    async with tenant_session(_claims(user_a, ws_a)) as session:
        result = await session.execute(
            text("select id from core.empresas where deleted_at is null")
        )
        visibles = {UUID(str(r[0])) for r in result}

    assert emp_a in visibles, "el tenant no ve su propia empresa"
    assert emp_b not in visibles, (
        "FUGA MULTI-TENANT: el tenant A ve la empresa del tenant B. Una query "
        "que confía solo en RLS (como la de /api/cartera) está exponiendo "
        "datos tributarios de otros contribuyentes."
    )


async def test_un_tenant_no_puede_escribir_en_el_workspace_de_otro(
    admin_session: AsyncSession,
) -> None:
    """RLS también debe frenar la ESCRITURA cruzada, no solo la lectura."""
    user_a, ws_a, _ = await _seed_workspace(admin_session)
    _user_b, ws_b, _ = await _seed_workspace(admin_session)
    await admin_session.commit()

    with pytest.raises(Exception) as exc:
        async with tenant_session(_claims(user_a, ws_a)) as session:
            await session.execute(
                text(
                    "insert into core.empresas "
                    "(workspace_id, rut, razon_social, regimen_actual) "
                    "values (:w, '11111111-1', 'Intrusa SpA', '14_a')"
                ),
                {"w": str(ws_b)},  # ← workspace ajeno
            )

    assert "row-level security" in str(exc.value).lower(), (
        f"se esperaba que RLS rechazara la escritura cruzada; en cambio: {exc.value}"
    )
