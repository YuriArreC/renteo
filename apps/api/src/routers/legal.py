"""GET /api/legal/{key} y /api/public/legal/{key} — texto legal versionado.

- `/api/legal/{key}` requiere auth (JWT). Sirve para mostrar disclaimers
  embebidos en flujos autenticados (simulador, wizard, etc.).
- `/api/public/legal/{key}` es público y sin auth. Lo consumen las pages
  públicas /legal/privacidad y /legal/terminos antes del login. Usa
  `service_session` (sin RLS) porque los textos son por definición
  públicos.

La respuesta incluye `version` para auditoría inversa ("¿qué versión vio
el usuario en este momento?").
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.tenancy import current_user
from src.db import get_db_session, service_session
from src.lib.legal_texts import LegalTextNotFound, get_legal_text

router = APIRouter(prefix="/api/legal", tags=["legal"])
public_router = APIRouter(prefix="/api/public/legal", tags=["legal"])


class LegalTextResponse(BaseModel):
    key: str
    version: str
    body: str
    effective_from: str


_ALLOWED_KEYS = frozenset(
    {
        "disclaimer-recomendacion",
        "disclaimer-simulacion",
        "consentimiento-tratamiento-datos",
        "consentimiento-certificado-digital",
        "consentimiento-mandato-digital",
        "terminos-servicio",
        "politica-privacidad",
        "ribbon-decisiones-automatizadas",
    }
)


async def _resolve_legal(
    session: AsyncSession, key: str
) -> LegalTextResponse:
    if key not in _ALLOWED_KEYS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"unknown legal text key: {key!r}",
        )
    try:
        legal = await get_legal_text(session, key)
    except LegalTextNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    return LegalTextResponse(
        key=legal.key,
        version=legal.version,
        body=legal.body,
        effective_from=legal.effective_from,
    )


@router.get("/{key}", response_model=LegalTextResponse)
async def get_legal(
    key: str,
    _user_id: UUID = Depends(current_user),
    session: AsyncSession = Depends(get_db_session),
) -> LegalTextResponse:
    return await _resolve_legal(session, key)


@public_router.get("/{key}", response_model=LegalTextResponse)
async def get_legal_public(key: str) -> LegalTextResponse:
    """Versión pública del lookup legal — sin auth.

    Los textos legales son por definición públicos (T&C, privacidad).
    Usamos `service_session` para no necesitar un JWT y respondemos
    el mismo shape que `/api/legal/{key}`.
    """
    async with service_session() as session:
        return await _resolve_legal(session, key)
