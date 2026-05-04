"""Gate de administración interna (skill 11 fase 6).

Las reglas declarativas viven a nivel global (afectan a todos los
workspaces) y se publican con doble firma: contador socio + admin
técnico. Solo los emails listados en `settings.internal_admin_emails`
pueden invocar los endpoints `/api/admin/*`.

Default seguro: la lista trae los placeholder seedeados en track 11
(contador-socio@renteo.local + admin-tecnico@renteo.local). En prod
se reemplaza por los emails reales del staff Renteo via env var.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.tenancy import current_user
from src.config import settings
from src.db import service_session


async def require_internal_admin(
    user_id: UUID = Depends(current_user),
) -> UUID:
    """Bloquea con 403 si el user_id no está en la whitelist."""
    async with service_session() as session:
        return await _check_email(session, user_id)


async def _check_email(
    session: AsyncSession, user_id: UUID
) -> UUID:
    result = await session.execute(
        text("select email from auth.users where id = :id"),
        {"id": str(user_id)},
    )
    row = result.first()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="usuario no encontrado",
        )
    email = str(row[0]).lower()
    if email not in settings.internal_admin_emails_set:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Solo el staff de Renteo (contador socio o admin "
                "técnico) puede gestionar reglas tributarias."
            ),
        )
    return user_id
