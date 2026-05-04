"""Sentry + request_id middleware (skill 10).

Reglas del CLAUDE.md sobre logging:
- Logs JSON sin PII (cubierto por `filter_sensitive` en lib/logging).
- request_id correlacionable: cada request entra con un id (header
  `X-Request-Id` o generado) y todas las entradas de structlog en
  ese ciclo lo llevan como contexto.
- Sentry captura excepciones no controladas. El SDK lee el DSN de
  config; si está vacío, no se inicializa (CI / dev local).
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

import sentry_sdk
import structlog
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

_REQUEST_ID_HEADER = "X-Request-Id"


def init_sentry(*, dsn: str, environment: str, release: str) -> None:
    """Inicializa Sentry si hay DSN. Sin DSN no hace nada (silencio
    explícito = bueno para CI / dev local). El sample rate se queda
    en 1.0 hasta tener volumen real; baja en producción cuando haga
    falta."""
    if not dsn:
        return
    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        release=release,
        integrations=[
            StarletteIntegration(),
            FastApiIntegration(),
        ],
        # Las requests con stack traces ya pasan por filter_sensitive de
        # structlog, pero Sentry tiene su propia copia: deshabilitamos
        # el body para no enviar JWTs / claims / payloads SII.
        send_default_pii=False,
        max_breadcrumbs=50,
    )


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Genera o propaga request_id y lo inyecta como contextvar de
    structlog. Cualquier `get_logger().info(...)` en el handler queda
    correlacionado automáticamente.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        incoming = request.headers.get(_REQUEST_ID_HEADER)
        request_id = incoming or uuid.uuid4().hex

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )
        sentry_sdk.set_tag("request_id", request_id)

        try:
            response = await call_next(request)
        finally:
            structlog.contextvars.clear_contextvars()

        response.headers[_REQUEST_ID_HEADER] = request_id
        return response
