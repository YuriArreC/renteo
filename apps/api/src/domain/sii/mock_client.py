"""Mock SiiClient — datos determinísticos por RUT + período.

Útil para CI / dev local sin DPA firmados con proveedores reales,
y para tests integration que validan el flujo de sincronización
sin depender del estado real del SII.
"""

from __future__ import annotations

import hashlib
from datetime import date
from decimal import Decimal

from src.domain.sii.adapter import (
    F22Anio,
    F29Periodo,
    RcvLine,
    SiiClient,
    TaxpayerInfo,
)

_GIROS = (
    "Comercio al por menor",
    "Servicios profesionales",
    "Transporte de carga",
    "Construcción",
    "Tecnología y software",
    "Consultoría",
    "Restaurante",
    "Educación",
)
_RAZONES_SUFFIXES = ("SpA", "Ltda.", "S.A.")
_RAZONES_NUCLEO = (
    "Andes",
    "Patagonia",
    "Cordillera",
    "Maipo",
    "Bio Bio",
    "Atacama",
    "Pacífico",
    "Austral",
)


def _seed(rut: str, period: str) -> int:
    """Hash estable RUT+period para que dos calls idénticas devuelvan
    la misma cantidad de líneas y montos."""
    h = hashlib.sha256(f"{rut}|{period}".encode()).digest()
    return int.from_bytes(h[:4], "big")


class MockSiiClient(SiiClient):
    name = "mock"

    async def fetch_rcv(
        self, *, rut: str, period: str
    ) -> list[RcvLine]:
        seed = _seed(rut, period)
        n_compras = 3 + (seed % 5)
        n_ventas = 4 + ((seed >> 4) % 6)
        year, month = (int(p) for p in period.split("-"))
        lines: list[RcvLine] = []
        for i in range(n_compras):
            base = Decimal(50000 + (seed >> i) % 200000)
            iva = (base * Decimal("0.19")).quantize(Decimal("0.01"))
            lines.append(
                RcvLine(
                    period=period,
                    tipo="compra",
                    folio=f"C{seed}-{i}",
                    rut_contraparte=f"7777777{i}-K",
                    neto=base,
                    iva=iva,
                    total=base + iva,
                    fecha_emision=date(year, month, min(i + 1, 28)),
                )
            )
        for i in range(n_ventas):
            base = Decimal(80000 + (seed >> (i + 8)) % 300000)
            iva = (base * Decimal("0.19")).quantize(Decimal("0.01"))
            lines.append(
                RcvLine(
                    period=period,
                    tipo="venta",
                    folio=f"V{seed}-{i}",
                    rut_contraparte=f"8888888{i}-K",
                    neto=base,
                    iva=iva,
                    total=base + iva,
                    fecha_emision=date(year, month, min(i + 1, 28)),
                )
            )
        return lines

    async def fetch_f29(
        self, *, rut: str, period: str
    ) -> F29Periodo | None:
        seed = _seed(rut, period)
        if seed % 17 == 0:
            # Simula período aún no presentado.
            return None
        debito = Decimal(seed % 10_000_000)
        credito = Decimal((seed >> 4) % 8_000_000)
        return F29Periodo(
            period=period,
            iva_debito=debito,
            iva_credito=credito,
            ppm=Decimal((seed >> 8) % 500_000),
            retenciones=Decimal(0),
            postergacion_iva=(seed % 7 == 0),
        )

    async def fetch_f22(
        self, *, rut: str, tax_year: int
    ) -> F22Anio | None:
        seed = _seed(rut, f"f22-{tax_year}")
        regimen_options = ("14_a", "14_d_3", "14_d_8")
        regimen = regimen_options[seed % 3]
        rli = Decimal(seed % 100_000_000)
        return F22Anio(
            tax_year=tax_year,
            regimen_declarado=regimen,
            rli_declarada=rli,
            idpc_pagado=(rli * Decimal("0.27")).quantize(Decimal("0.01")),
        )

    async def lookup_taxpayer(
        self, *, rut: str
    ) -> TaxpayerInfo | None:
        """Mock lookup: deriva razón social y giro determinísticamente
        del RUT. Si los últimos 3 chars del cuerpo son '000' simula un
        RUT inexistente para que los tests cubran ese caso."""
        cuerpo = rut.replace("-", "").replace(".", "")[:-1]
        if cuerpo.endswith("000"):
            return None
        seed = _seed(rut, "lookup")
        nucleo = _RAZONES_NUCLEO[seed % len(_RAZONES_NUCLEO)]
        suffix = _RAZONES_SUFFIXES[(seed >> 4) % len(_RAZONES_SUFFIXES)]
        giro = _GIROS[(seed >> 8) % len(_GIROS)]
        # Año fundacional entre 2010 y 2024 derivado del RUT.
        year = 2010 + (seed % 14)
        month = 1 + ((seed >> 12) % 12)
        day = 1 + ((seed >> 16) % 27)
        return TaxpayerInfo(
            rut=rut,
            razon_social=f"{nucleo} {suffix}",
            giro=giro,
            fecha_inicio_actividades=date(year, month, day),
            activo=(seed % 11) != 0,
        )
