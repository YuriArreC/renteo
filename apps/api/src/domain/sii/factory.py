"""Factory de SiiClient.

Lee `tax_rules.feature_flags_by_year` para resolver el proveedor
vigente. Default = `mock` para que CI / dev local funcionen sin
DPA / tokens reales.

Track 4b agregará BaseAPI / ApiGateway con custodia KMS del
certificado digital.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.sii.adapter import SiiClient
from src.domain.sii.mock_client import MockSiiClient
from src.domain.sii.simpleapi_client import SimpleApiSiiClient
from src.lib.errors import SiiUnavailable

_FLAG_KEY = "sii_provider"
_DEFAULT_PROVIDER = "mock"
_KNOWN_PROVIDERS = {"mock", "simpleapi", "baseapi", "apigateway"}


async def resolve_sii_provider(
    session: AsyncSession, *, on_date: date | None = None
) -> str:
    """Devuelve el provider name vigente según el feature flag."""
    target = on_date or date.today()
    result = await session.execute(
        text(
            """
            select value
              from tax_rules.feature_flags_by_year
             where flag_key = :k
               and effective_from <= :t
             order by effective_from desc
             limit 1
            """
        ),
        {"k": _FLAG_KEY, "t": target},
    )
    row = result.first()
    if row is None:
        return _DEFAULT_PROVIDER
    value = str(row[0])
    if value not in _KNOWN_PROVIDERS:
        return _DEFAULT_PROVIDER
    return value


def make_sii_client(provider: str) -> SiiClient:
    """Instancia el cliente del proveedor pedido.

    `baseapi` / `apigateway` no están implementados aún; lanzan
    `SiiUnavailable` para que el endpoint degrade limpio en lugar
    de hacer fallback silencioso.
    """
    if provider == "mock":
        return MockSiiClient()
    if provider == "simpleapi":
        return SimpleApiSiiClient()
    if provider in ("baseapi", "apigateway"):
        raise SiiUnavailable(
            f"provider '{provider}' aún no implementado (track 4b)"
        )
    raise SiiUnavailable(f"unknown sii provider: {provider!r}")
