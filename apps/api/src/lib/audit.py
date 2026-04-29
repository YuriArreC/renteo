"""Append-only audit log for tax data access.

Inserts go into security.audit_log. The table has a Postgres trigger that
blocks UPDATE/DELETE; never bypass it.
"""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def log_audit(
    session: AsyncSession,
    *,
    workspace_id: UUID,
    user_id: UUID,
    action: str,
    resource_type: str,
    resource_id: UUID | None = None,
    empresa_id: UUID | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    await session.execute(
        text(
            """
            INSERT INTO security.audit_log (
                workspace_id, empresa_id, user_id, action,
                resource_type, resource_id, metadata, at
            ) VALUES (
                :workspace_id, :empresa_id, :user_id, :action,
                :resource_type, :resource_id, :metadata, now()
            )
            """
        ),
        {
            "workspace_id": str(workspace_id),
            "empresa_id": str(empresa_id) if empresa_id else None,
            "user_id": str(user_id),
            "action": action,
            "resource_type": resource_type,
            "resource_id": str(resource_id) if resource_id else None,
            "metadata": json.dumps(metadata or {}),
        },
    )
