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
        return jwt.decode(
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
