"""Tests integration del Custom Access Token Hook (Track 2).

Verifican que la función `public.custom_access_token_hook(event)` puebla
correctamente el JWT con `app_metadata.{workspace_id, workspace_type, role,
empresa_ids}` según las reglas de skill 6 + skill 9.
"""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def _build_event(
    user_id: UUID, base_app_metadata: dict[str, Any] | None = None
) -> dict[str, Any]:
    return {
        "user_id": str(user_id),
        "claims": {
            "sub": str(user_id),
            "aud": "authenticated",
            "role": "authenticated",
            "app_metadata": base_app_metadata or {"provider": "email"},
        },
    }


async def _call_hook(
    session: AsyncSession, event: dict[str, Any]
) -> dict[str, Any]:
    result = await session.execute(
        text("select public.custom_access_token_hook(cast(:e as jsonb))"),
        {"e": json.dumps(event)},
    )
    raw = result.scalar_one()
    if isinstance(raw, str):
        return json.loads(raw)  # type: ignore[no-any-return]
    return raw  # type: ignore[no-any-return]


# ---------------------------------------------------------------------------
# Caminos felices
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_hook_returns_pyme_owner_claims(
    admin_session: AsyncSession, two_workspaces: dict[str, UUID]
) -> None:
    ctx = two_workspaces
    async with admin_session.begin():
        await admin_session.execute(
            text(
                """
                insert into core.workspace_members
                    (workspace_id, user_id, role, accepted_at)
                values (:ws, :uid, 'owner', now())
                on conflict do nothing
                """
            ),
            {"ws": str(ctx["ws_a"]), "uid": str(ctx["user_a"])},
        )

    async with admin_session.begin():
        result = await _call_hook(admin_session, _build_event(ctx["user_a"]))

    app_md = result["claims"]["app_metadata"]
    assert app_md["workspace_id"] == str(ctx["ws_a"])
    assert app_md["workspace_type"] == "pyme"
    assert app_md["role"] == "owner"
    assert app_md["empresa_ids"] == []
    # Claims base preservados.
    assert app_md["provider"] == "email"


@pytest.mark.integration
async def test_hook_accountant_staff_with_assigned_empresas(
    admin_session: AsyncSession, two_workspaces: dict[str, UUID]
) -> None:
    ctx = two_workspaces
    async with admin_session.begin():
        await admin_session.execute(
            text(
                """
                insert into core.workspace_members
                    (workspace_id, user_id, role, accepted_at)
                values (:ws, :uid, 'accountant_staff', now())
                on conflict do nothing
                """
            ),
            {"ws": str(ctx["ws_b"]), "uid": str(ctx["user_b"])},
        )
        await admin_session.execute(
            text(
                """
                insert into core.accountant_assignments
                    (workspace_id, empresa_id, user_id, permission_level)
                values (:ws, :emp, :uid, 'read_write')
                """
            ),
            {
                "ws": str(ctx["ws_b"]),
                "emp": str(ctx["emp_b"]),
                "uid": str(ctx["user_b"]),
            },
        )

    async with admin_session.begin():
        result = await _call_hook(admin_session, _build_event(ctx["user_b"]))

    app_md = result["claims"]["app_metadata"]
    assert app_md["role"] == "accountant_staff"
    assert app_md["workspace_type"] == "accounting_firm"
    assert str(ctx["emp_b"]) in app_md["empresa_ids"]


@pytest.mark.integration
async def test_hook_accountant_staff_empty_when_no_assignments(
    admin_session: AsyncSession, two_workspaces: dict[str, UUID]
) -> None:
    ctx = two_workspaces
    async with admin_session.begin():
        await admin_session.execute(
            text(
                """
                insert into core.workspace_members
                    (workspace_id, user_id, role, accepted_at)
                values (:ws, :uid, 'accountant_staff', now())
                on conflict do nothing
                """
            ),
            {"ws": str(ctx["ws_b"]), "uid": str(ctx["user_b"])},
        )

    async with admin_session.begin():
        result = await _call_hook(admin_session, _build_event(ctx["user_b"]))

    assert result["claims"]["app_metadata"]["empresa_ids"] == []


# ---------------------------------------------------------------------------
# Casos en los que NO se inyecta workspace
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_hook_skips_when_no_membership(
    admin_session: AsyncSession,
) -> None:
    user_id = uuid4()
    async with admin_session.begin():
        await admin_session.execute(
            text(
                "insert into auth.users (id, email) values (:id, :email)"
            ),
            {"id": str(user_id), "email": f"hook-{user_id}@renteo.local"},
        )

    try:
        async with admin_session.begin():
            result = await _call_hook(admin_session, _build_event(user_id))

        app_md = result["claims"]["app_metadata"]
        assert "workspace_id" not in app_md
        assert "role" not in app_md
        # Lo que vino se respeta.
        assert app_md["provider"] == "email"
    finally:
        async with admin_session.begin():
            await admin_session.execute(
                text("delete from auth.users where id = :id"),
                {"id": str(user_id)},
            )


@pytest.mark.integration
async def test_hook_ignores_unaccepted_membership(
    admin_session: AsyncSession, two_workspaces: dict[str, UUID]
) -> None:
    """accepted_at IS NULL → la membership no califica."""
    ctx = two_workspaces
    async with admin_session.begin():
        await admin_session.execute(
            text(
                """
                insert into core.workspace_members
                    (workspace_id, user_id, role, accepted_at)
                values (:ws, :uid, 'owner', null)
                on conflict do nothing
                """
            ),
            {"ws": str(ctx["ws_a"]), "uid": str(ctx["user_a"])},
        )

    async with admin_session.begin():
        result = await _call_hook(admin_session, _build_event(ctx["user_a"]))

    assert "workspace_id" not in result["claims"]["app_metadata"]


@pytest.mark.integration
async def test_hook_ignores_soft_deleted_workspace(
    admin_session: AsyncSession, two_workspaces: dict[str, UUID]
) -> None:
    ctx = two_workspaces
    async with admin_session.begin():
        await admin_session.execute(
            text(
                """
                insert into core.workspace_members
                    (workspace_id, user_id, role, accepted_at)
                values (:ws, :uid, 'owner', now())
                on conflict do nothing
                """
            ),
            {"ws": str(ctx["ws_a"]), "uid": str(ctx["user_a"])},
        )
        await admin_session.execute(
            text(
                "update core.workspaces set deleted_at = now() where id = :id"
            ),
            {"id": str(ctx["ws_a"])},
        )

    try:
        async with admin_session.begin():
            result = await _call_hook(admin_session, _build_event(ctx["user_a"]))

        assert "workspace_id" not in result["claims"]["app_metadata"]
    finally:
        async with admin_session.begin():
            await admin_session.execute(
                text(
                    "update core.workspaces set deleted_at = null where id = :id"
                ),
                {"id": str(ctx["ws_a"])},
            )


# ---------------------------------------------------------------------------
# Multi-workspace
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_hook_picks_most_recent_membership(
    admin_session: AsyncSession, two_workspaces: dict[str, UUID]
) -> None:
    """Con dos memberships aceptadas gana invited_at más reciente."""
    ctx = two_workspaces
    async with admin_session.begin():
        await admin_session.execute(
            text(
                """
                insert into core.workspace_members
                    (workspace_id, user_id, role, invited_at, accepted_at)
                values (
                    :ws, :uid, 'owner',
                    now() - interval '7 days',
                    now() - interval '6 days'
                )
                on conflict do nothing
                """
            ),
            {"ws": str(ctx["ws_a"]), "uid": str(ctx["user_a"])},
        )
        await admin_session.execute(
            text(
                """
                insert into core.workspace_members
                    (workspace_id, user_id, role, invited_at, accepted_at)
                values (:ws, :uid, 'accountant_lead', now(), now())
                on conflict do nothing
                """
            ),
            {"ws": str(ctx["ws_b"]), "uid": str(ctx["user_a"])},
        )

    async with admin_session.begin():
        result = await _call_hook(admin_session, _build_event(ctx["user_a"]))

    app_md = result["claims"]["app_metadata"]
    assert app_md["workspace_id"] == str(ctx["ws_b"])
    assert app_md["role"] == "accountant_lead"
    assert app_md["workspace_type"] == "accounting_firm"
