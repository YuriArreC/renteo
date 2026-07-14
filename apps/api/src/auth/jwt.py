"""JWT verification against the Supabase JWKS endpoint.

Supabase Auth signs JWTs with RS256 and exposes the public keys at
`<project>.supabase.co/auth/v1/jwks`. We cache the JWKS for 1 h (the default
lifespan of `PyJWKClient`) and re-fetch on key rotation.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

from src.config import settings

_bearer = HTTPBearer(auto_error=True)


@lru_cache(maxsize=1)
def _jwks_client() -> PyJWKClient:
    if not settings.supabase_jwks_url:
        raise RuntimeError("SUPABASE_JWKS_URL is not configured")
    return PyJWKClient(
        settings.supabase_jwks_url,
        cache_keys=True,
        lifespan=3600,
    )


def verify_jwt(
    creds: HTTPAuthorizationCredentials = Depends(_bearer),
) -> dict[str, Any]:
    token = creds.credentials
    try:
        signing_key = _jwks_client().get_signing_key_from_jwt(token).key
        # Supabase Auth firma con ES256 en proyectos nuevos y RS256 en
        # proyectos legacy. Aceptamos ambos para cubrir las dos cohortes.
        claims = jwt.decode(
            token,
            signing_key,
            algorithms=["RS256", "ES256"],
            audience=settings.supabase_jwt_audience,
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid token",
        ) from exc

    _enforce_allowlist(claims)
    return claims


def _enforce_allowlist(claims: dict[str, Any]) -> None:
    """Demo cerrado: solo los emails de `ALLOWED_USER_EMAILS` entran.

    Se aplica acá, en el verificador del token, y no en cada router, porque
    `verify_jwt` es el único camino de entrada de TODO endpoint autenticado
    (`current_user`, `current_tenancy` y `require_internal_admin` dependen de
    él). Un guard por router se olvidaría en el próximo router que se agregue.

    Motivo: el motor tributario todavía NO está validado por el CONTADOR_SOCIO
    (firma diferida). Emitir recomendaciones a una persona real sobre reglas sin
    validar expone a Renteo al art. 100 bis CT como diseñador/planificador
    (100-250 UTA), y la exención del art. 14 letra D ampara al contribuyente, no
    al asesor. Mientras eso siga así, la app solo la usan usuarios de prueba.

    Falla CERRADA: si la allowlist está activa y el token no trae `email`, se
    rechaza. Un token sin email no es prueba de estar en la lista.

    Con la allowlist vacía no se hace nada — ver `settings.allowlist_enabled`.
    """
    if not settings.allowlist_enabled:
        return

    email = claims.get("email")
    if not isinstance(email, str) or not email.strip():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="acceso restringido (demo cerrado)",
        )

    if email.strip().lower() not in settings.allowed_user_emails_set:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="acceso restringido (demo cerrado)",
        )
