"""GET /api/me — devuelve el user_id y, si aplica, el workspace activo.

El frontend usa esta respuesta para decidir el redirect post-login:
  - sin workspace → /onboarding/workspace
  - con workspace → /dashboard (cliente A) o /cartera (cliente B, fase 6+)
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.jwt import verify_jwt
from src.auth.tenancy import Role, WorkspaceType
from src.db import get_db_session

router = APIRouter(prefix="/api", tags=["me"])


class MeWorkspace(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    name: str
    type: WorkspaceType
    role: Role
    empresa_ids: tuple[UUID, ...]


class MeResponse(BaseModel):
    user_id: UUID
    workspace: MeWorkspace | None


@router.get("/me", response_model=MeResponse)
async def get_me(
    claims: dict[str, Any] = Depends(verify_jwt),
    session: AsyncSession = Depends(get_db_session),
) -> MeResponse:
    user_id = UUID(str(claims["sub"]))
    meta = claims.get("app_metadata") or {}
    workspace_id_claim = meta.get("workspace_id")

    if not workspace_id_claim:
        return MeResponse(user_id=user_id, workspace=None)

    result = await session.execute(
        text(
            """
            select id, name, type
              from core.workspaces
             where id = :id
               and deleted_at is null
            """
        ),
        {"id": workspace_id_claim},
    )
    row = result.mappings().one_or_none()
    if row is None:
        # JWT desactualizado (workspace borrado) o RLS lo oculta.
        return MeResponse(user_id=user_id, workspace=None)

    raw_empresa_ids = meta.get("empresa_ids") or []
    empresa_ids = tuple(UUID(str(e)) for e in raw_empresa_ids)

    return MeResponse(
        user_id=user_id,
        workspace=MeWorkspace(
            id=UUID(str(row["id"])),
            name=str(row["name"]),
            type=row["type"],
            role=meta["role"],
            empresa_ids=empresa_ids,
        ),
    )
