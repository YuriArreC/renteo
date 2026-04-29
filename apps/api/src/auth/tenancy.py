"""Tenancy extracted from the Supabase JWT (`app_metadata`).

Workspace and empresa context NEVER come from the request body or query —
they are derived exclusively from the verified JWT, then enforced again at
the database layer via Row-Level Security (skill 6, skill 10).
"""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from fastapi import Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from src.auth.jwt import verify_jwt

WorkspaceType = Literal["pyme", "accounting_firm"]
Role = Literal[
    "owner",
    "cfo",
    "accountant_lead",
    "accountant_staff",
    "viewer",
]


class Tenancy(BaseModel):
    model_config = ConfigDict(frozen=True)

    user_id: UUID
    workspace_id: UUID
    workspace_type: WorkspaceType
    role: Role
    empresa_ids: tuple[UUID, ...] = Field(default_factory=tuple)


def current_user(
    claims: dict[str, Any] = Depends(verify_jwt),
) -> UUID:
    """Devuelve solo el user_id del JWT.

    Útil durante onboarding (cuando aún no hay workspace, así que
    `current_tenancy` rechazaría con 403). Una vez creado el workspace,
    el frontend refresca la sesión y el flujo normal vuelve a usar
    `current_tenancy`.
    """
    sub = claims.get("sub")
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="missing sub claim",
        )
    try:
        return UUID(str(sub))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="malformed sub claim",
        ) from exc


def current_tenancy(
    claims: dict[str, Any] = Depends(verify_jwt),
) -> Tenancy:
    meta = claims.get("app_metadata") or {}
    workspace_id = meta.get("workspace_id")
    workspace_type = meta.get("workspace_type")
    role = meta.get("role")
    sub = claims.get("sub")

    if not workspace_id or not workspace_type or not role or not sub:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="missing tenancy claims",
        )

    raw_empresa_ids = meta.get("empresa_ids") or []
    try:
        empresa_ids = tuple(UUID(str(e)) for e in raw_empresa_ids)
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="malformed empresa_ids claim",
        ) from exc

    try:
        return Tenancy(
            user_id=UUID(str(sub)),
            workspace_id=UUID(str(workspace_id)),
            workspace_type=workspace_type,
            role=role,
            empresa_ids=empresa_ids,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="malformed tenancy claims",
        ) from exc
