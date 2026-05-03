"""GET /api/legal/{key} — texto legal versionado vigente (skill 2).

Permite que el front renderice los textos sin duplicarlos como
constantes. La respuesta incluye `version` para auditoría inversa
("¿qué versión vio el usuario en este momento?").
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.tenancy import current_user
from src.db import get_db_session
from src.lib.legal_texts import LegalTextNotFound, get_legal_text

router = APIRouter(prefix="/api/legal", tags=["legal"])


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


@router.get("/{key}", response_model=LegalTextResponse)
async def get_legal(
    key: str,
    _user_id: UUID = Depends(current_user),
    session: AsyncSession = Depends(get_db_session),
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
