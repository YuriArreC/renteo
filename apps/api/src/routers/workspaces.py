"""Onboarding endpoints: alta de workspace + miembro inicial.

Es el único punto del backend donde el cliente provee información sobre el
workspace que va a crear (porque aún no existe). Después de este POST, el
flujo canónico vuelve: workspace_id se deriva del JWT y la RLS protege.
"""

from __future__ import annotations

import json
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

from src.auth.tenancy import Role, WorkspaceType, current_user
from src.db import service_session
from src.lib.audit import log_audit

router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])


CONSENT_TRATAMIENTO_DATOS = "consentimiento-tratamiento-datos-v1"


class CreateWorkspaceReq(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    type: WorkspaceType
    consent_tratamiento_datos: Literal[True] = Field(
        ...,
        description=(
            "Consentimiento explícito al tratamiento de datos personales y "
            "tributarios bajo Ley 19.628 + Ley 21.719. Versión "
            f"{CONSENT_TRATAMIENTO_DATOS}."
        ),
    )


class CreateWorkspaceResp(BaseModel):
    id: UUID
    name: str
    type: WorkspaceType
    role: Role


def _initial_role(workspace_type: WorkspaceType) -> Role:
    return "owner" if workspace_type == "pyme" else "accountant_lead"


@router.post(
    "",
    response_model=CreateWorkspaceResp,
    status_code=status.HTTP_201_CREATED,
)
async def create_workspace(
    payload: CreateWorkspaceReq,
    user_id: UUID = Depends(current_user),
) -> CreateWorkspaceResp:
    """Crea workspace + miembro inicial + consentimiento + audit log.

    Atómico: si cualquier paso falla, todo se revierte. El usuario debe
    refrescar su sesión Supabase tras este POST para que el Auth Hook
    re-ejecute y inyecte la tenancy en el JWT.
    """
    role: Role = _initial_role(payload.type)

    async with service_session() as session:
        # Validar que el usuario aún no tiene membership aceptada — un user
        # = un workspace en MVP (multi-workspace selector llega en fase 6+).
        existing = await session.execute(
            text(
                """
                select 1
                  from core.workspace_members
                 where user_id = :uid
                   and accepted_at is not null
                 limit 1
                """
            ),
            {"uid": str(user_id)},
        )
        if existing.scalar() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="user already belongs to a workspace",
            )

        workspace_id = uuid4()
        await session.execute(
            text(
                """
                insert into core.workspaces (id, name, type)
                values (:id, :name, :type)
                """
            ),
            {
                "id": str(workspace_id),
                "name": payload.name,
                "type": payload.type,
            },
        )
        await session.execute(
            text(
                """
                insert into core.workspace_members
                    (workspace_id, user_id, role, accepted_at)
                values (:ws, :uid, :role, now())
                """
            ),
            {"ws": str(workspace_id), "uid": str(user_id), "role": role},
        )
        await session.execute(
            text(
                """
                insert into privacy.consentimientos
                    (user_id, workspace_id, tipo_consentimiento,
                     version_texto)
                values (:uid, :ws, 'tratamiento_datos', :ver)
                """
            ),
            {
                "uid": str(user_id),
                "ws": str(workspace_id),
                "ver": CONSENT_TRATAMIENTO_DATOS,
            },
        )
        await log_audit(
            session,
            workspace_id=workspace_id,
            user_id=user_id,
            action="create",
            resource_type="workspace",
            resource_id=workspace_id,
            metadata={"workspace_type": payload.type, "role": role},
        )

    return CreateWorkspaceResp(
        id=workspace_id,
        name=payload.name,
        type=payload.type,
        role=role,
    )
