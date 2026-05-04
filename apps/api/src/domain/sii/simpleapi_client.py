"""SimpleAPI client — proveedor primario para acceso a SII.

Track 4 MVP: skeleton con httpx + reintentos exponenciales. La
custodia real del certificado digital y el mandato digital quedan
para track 4b (junto con KMS y la activación del feature flag
`sii_provider=simpleapi`).

Reglas:
- Lee el token de la env var `SII_SIMPLEAPI_TOKEN`. Si falta,
  lanza `SiiUnavailable` para que el endpoint degrade limpio.
- Timeouts cortos (10s) y máximo 3 intentos: 5xx / red → reintento
  con backoff; 401/403 → `SiiAuthError` sin reintento.
- NUNCA loguea el token ni los payloads completos del SII.
"""

from __future__ import annotations

import asyncio
import os
from datetime import date
from decimal import Decimal
from typing import Any

import httpx
import structlog

from src.domain.sii.adapter import (
    F22Anio,
    F29Periodo,
    RcvLine,
    SiiClient,
    TaxpayerInfo,
)
from src.lib.audit import mask_rut
from src.lib.errors import SiiAuthError, SiiTimeout, SiiUnavailable

logger = structlog.get_logger(__name__)

_DEFAULT_BASE_URL = "https://servicios.simpleapi.cl/api"
_TIMEOUT_SECONDS = 10.0
_MAX_ATTEMPTS = 3


class SimpleApiSiiClient(SiiClient):
    name = "simpleapi"

    def __init__(
        self,
        *,
        token: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self._token = token or os.getenv("SII_SIMPLEAPI_TOKEN", "")
        if not self._token:
            raise SiiUnavailable(
                "SII_SIMPLEAPI_TOKEN no configurado; "
                "no se puede invocar SimpleAPI"
            )
        resolved_url = base_url or os.getenv(
            "SII_SIMPLEAPI_BASE_URL"
        )
        self._base_url: str = resolved_url or _DEFAULT_BASE_URL

    async def _request(
        self, method: str, path: str, *, json: dict[str, Any] | None = None
    ) -> Any:
        url = f"{self._base_url.rstrip('/')}/{path.lstrip('/')}"
        last_exc: Exception | None = None
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
            for attempt in range(1, _MAX_ATTEMPTS + 1):
                try:
                    response = await client.request(
                        method,
                        url,
                        json=json,
                        headers={
                            "Authorization": f"Bearer {self._token}",
                            "Accept": "application/json",
                        },
                    )
                except httpx.TimeoutException as exc:
                    last_exc = exc
                    logger.warning(
                        "sii_simpleapi_timeout",
                        attempt=attempt,
                        path=path,
                    )
                except httpx.HTTPError as exc:
                    last_exc = exc
                    logger.warning(
                        "sii_simpleapi_network_error",
                        attempt=attempt,
                        path=path,
                        error_type=type(exc).__name__,
                    )
                else:
                    if response.status_code in (401, 403):
                        raise SiiAuthError(
                            "credenciales SimpleAPI rechazadas"
                        )
                    if 500 <= response.status_code < 600:
                        last_exc = SiiUnavailable(
                            f"SimpleAPI 5xx: {response.status_code}"
                        )
                        logger.warning(
                            "sii_simpleapi_5xx",
                            attempt=attempt,
                            status=response.status_code,
                        )
                    elif response.is_success:
                        return response.json()
                    else:
                        # 4xx no auth → falla rápido sin reintento.
                        raise SiiUnavailable(
                            f"SimpleAPI {response.status_code}"
                        )
                if attempt < _MAX_ATTEMPTS:
                    await asyncio.sleep(2 ** (attempt - 1))
        if isinstance(last_exc, httpx.TimeoutException):
            raise SiiTimeout(str(last_exc)) from last_exc
        raise SiiUnavailable(
            "SimpleAPI no respondió tras reintentos"
        ) from last_exc

    async def fetch_rcv(
        self, *, rut: str, period: str
    ) -> list[RcvLine]:
        logger.info(
            "sii_fetch_rcv",
            rut=mask_rut(rut),
            period=period,
        )
        payload = await self._request(
            "POST",
            "/rcv/consulta",
            json={"rut": rut, "periodo": period},
        )
        items = payload.get("items") or []
        result: list[RcvLine] = []
        for item in items:
            result.append(
                RcvLine(
                    period=period,
                    tipo=str(item["tipo"]),
                    folio=str(item["folio"]),
                    rut_contraparte=str(item["rut_contraparte"]),
                    neto=Decimal(str(item["neto"])),
                    iva=Decimal(str(item["iva"])),
                    total=Decimal(str(item["total"])),
                    fecha_emision=date.fromisoformat(
                        str(item["fecha_emision"])
                    ),
                )
            )
        return result

    async def fetch_f29(
        self, *, rut: str, period: str
    ) -> F29Periodo | None:
        logger.info(
            "sii_fetch_f29",
            rut=mask_rut(rut),
            period=period,
        )
        payload = await self._request(
            "POST",
            "/f29/consulta",
            json={"rut": rut, "periodo": period},
        )
        if not payload or payload.get("no_presentado"):
            return None
        return F29Periodo(
            period=period,
            iva_debito=Decimal(str(payload["iva_debito"])),
            iva_credito=Decimal(str(payload["iva_credito"])),
            ppm=Decimal(str(payload.get("ppm", "0"))),
            retenciones=Decimal(str(payload.get("retenciones", "0"))),
            postergacion_iva=bool(payload.get("postergacion_iva")),
        )

    async def fetch_f22(
        self, *, rut: str, tax_year: int
    ) -> F22Anio | None:
        logger.info(
            "sii_fetch_f22",
            rut=mask_rut(rut),
            tax_year=tax_year,
        )
        payload = await self._request(
            "POST",
            "/f22/consulta",
            json={"rut": rut, "tax_year": tax_year},
        )
        if not payload or payload.get("no_presentado"):
            return None
        return F22Anio(
            tax_year=tax_year,
            regimen_declarado=str(payload["regimen_declarado"]),
            rli_declarada=Decimal(str(payload["rli_declarada"])),
            idpc_pagado=Decimal(str(payload["idpc_pagado"])),
        )

    async def lookup_taxpayer(
        self, *, rut: str
    ) -> TaxpayerInfo | None:
        logger.info("sii_lookup_taxpayer", rut=mask_rut(rut))
        payload = await self._request(
            "POST",
            "/contribuyente/info",
            json={"rut": rut},
        )
        if not payload or payload.get("no_encontrado"):
            return None
        fecha_raw = payload.get("fecha_inicio_actividades")
        return TaxpayerInfo(
            rut=rut,
            razon_social=str(payload["razon_social"]),
            giro=(
                str(payload["giro"])
                if payload.get("giro") is not None
                else None
            ),
            fecha_inicio_actividades=(
                date.fromisoformat(str(fecha_raw)) if fecha_raw else None
            ),
            activo=bool(payload.get("activo", True)),
        )
