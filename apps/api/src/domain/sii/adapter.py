"""Adapter SII — interface común a SimpleAPI / BaseAPI / ApiGateway / mock.

Track skill 4 MVP: solo el shape de los datos + un cliente mock que
retorna datos deterministas por RUT. La integración real con
SimpleAPI / BaseAPI vive en clients dedicados (track 4b agrega los
HTTP reales con retries, KMS para custodia de certificado y
clasificación de errores tipados).

Reglas no negociables (skill 4):
- NUNCA pedir Clave Tributaria del usuario en texto plano.
- Certificados solo en KMS; la DB guarda solo el ARN.
- Toda llamada loguea sin PII (RUT enmascarado, sin claves).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(frozen=True)
class RcvLine:
    period: str  # YYYY-MM
    tipo: str  # "compra" | "venta"
    folio: str
    rut_contraparte: str
    neto: Decimal
    iva: Decimal
    total: Decimal
    fecha_emision: date


@dataclass(frozen=True)
class F29Periodo:
    period: str
    iva_debito: Decimal
    iva_credito: Decimal
    ppm: Decimal
    retenciones: Decimal
    postergacion_iva: bool


@dataclass(frozen=True)
class F22Anio:
    tax_year: int
    regimen_declarado: str
    rli_declarada: Decimal
    idpc_pagado: Decimal


@dataclass(frozen=True)
class TaxpayerInfo:
    """Datos públicos de un contribuyente recuperados desde SII.

    No incluye PII sensible (no marca social, no domicilio fiscal
    tampoco): solo lo necesario para identificar la empresa y
    pre-llenar el alta.
    """

    rut: str
    razon_social: str
    giro: str | None
    fecha_inicio_actividades: date | None
    activo: bool


class SiiClient(ABC):
    """Contrato que cumplen todos los proveedores SII (mock + reales)."""

    name: str

    @abstractmethod
    async def fetch_rcv(
        self, *, rut: str, period: str
    ) -> list[RcvLine]:
        """RCV de un período YYYY-MM."""

    @abstractmethod
    async def fetch_f29(
        self, *, rut: str, period: str
    ) -> F29Periodo | None:
        """F29 de un período YYYY-MM, o None si aún no presentado."""

    @abstractmethod
    async def fetch_f22(
        self, *, rut: str, tax_year: int
    ) -> F22Anio | None:
        """F22 anual; None si aún no presentado."""

    @abstractmethod
    async def lookup_taxpayer(
        self, *, rut: str
    ) -> TaxpayerInfo | None:
        """Información pública del contribuyente (razón social, giro,
        fecha inicio actividades). None si el RUT no existe en SII."""
