"""Watchdog legislativo — adapter (skill 11 closure).

Define la interfaz `LegislativeMonitor` que cumplen el mock y el
fetcher real (track 11d). El monitor reporta `LegislativeAlert`
candidatos a partir de tres fuentes:

    - DOF (Diario Oficial)
    - SII (circulares, oficios, resoluciones)
    - Ley de Presupuestos

El worker invoca `check_all()` y persiste con dedup por (source,
source_id).

🟡 La implementación HTTP real (parser DOF + scraping SII +
notificaciones de presupuestos) es track 11d; aquí entregamos solo
el contrato + un mock determinístico para CI / dev.
"""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Literal

LegislativeSource = Literal[
    "dof",
    "sii_circular",
    "sii_oficio",
    "sii_resolucion",
    "presupuestos",
]


@dataclass(frozen=True)
class LegislativeAlert:
    source: LegislativeSource
    source_id: str
    title: str
    summary: str
    url: str | None
    publication_date: date
    target_domain: str | None
    target_key: str | None
    propuesta_diff: dict[str, Any]


class LegislativeMonitor(ABC):
    """Contrato que cumplen los monitors (mock + reales)."""

    name: str

    @abstractmethod
    async def check_dof(self, *, since: date) -> list[LegislativeAlert]:
        """Hits del Diario Oficial publicados desde `since` (inclusive)."""

    @abstractmethod
    async def check_sii(self, *, since: date) -> list[LegislativeAlert]:
        """Circulares, oficios y resoluciones SII desde `since`."""

    @abstractmethod
    async def check_presupuestos(
        self, *, since: date
    ) -> list[LegislativeAlert]:
        """Hits relevantes de Ley de Presupuestos desde `since`."""

    async def check_all(
        self, *, since: date
    ) -> list[LegislativeAlert]:
        """Helper que agrega los 3 sources en una lista única."""
        dof = await self.check_dof(since=since)
        sii = await self.check_sii(since=since)
        presupuestos = await self.check_presupuestos(since=since)
        return [*dof, *sii, *presupuestos]


def _hash(*parts: str) -> int:
    h = hashlib.sha256("|".join(parts).encode()).digest()
    return int.from_bytes(h[:4], "big")


class MockLegislativeMonitor(LegislativeMonitor):
    """Mock determinístico — devuelve hits estables por fecha.

    Convención: para una fecha dada, los hits son los mismos en cada
    invocación. Esto permite que el worker sea idempotente: la primera
    corrida inserta N filas; la segunda hace dedup y no inserta nada.
    """

    name = "mock"

    async def check_dof(
        self, *, since: date
    ) -> list[LegislativeAlert]:
        # Un hit por semana hábil (lunes) en la ventana.
        results: list[LegislativeAlert] = []
        cursor = since
        end = date.today()
        while cursor <= end:
            if cursor.weekday() == 0:  # lunes
                seed = _hash("dof", cursor.isoformat())
                results.append(
                    LegislativeAlert(
                        source="dof",
                        source_id=f"DOF-{cursor.isoformat()}-{seed}",
                        title=(
                            f"DOF {cursor.isoformat()}: ajuste IPC "
                            "anual a UF/UTM/UTA."
                        ),
                        summary=(
                            "Reajuste de UF/UTM/UTA conforme variación "
                            "IPC; afecta tax_year_params."
                        ),
                        url=(
                            f"https://www.diariooficial.cl/"
                            f"{cursor.isoformat()}"
                        ),
                        publication_date=cursor,
                        target_domain="tax_year_params",
                        target_key=str(cursor.year + 1),
                        propuesta_diff={
                            "uf_valor_clp": "TBD por DOF",
                            "utm_valor_clp": "TBD por DOF",
                        },
                    )
                )
            cursor += timedelta(days=1)
        return results

    async def check_sii(
        self, *, since: date
    ) -> list[LegislativeAlert]:
        # Una circular cada 15 días (días múltiplos de 15).
        results: list[LegislativeAlert] = []
        cursor = since
        end = date.today()
        while cursor <= end:
            if cursor.day == 15:
                seed = _hash("sii", cursor.isoformat())
                num = (seed % 90) + 1
                results.append(
                    LegislativeAlert(
                        source="sii_circular",
                        source_id=f"CIRC-{cursor.year}-{num}",
                        title=(
                            f"Circular SII {num}/{cursor.year}: "
                            "instrucciones art. 14 D N°3."
                        ),
                        summary=(
                            "Aclara cómputo de tasa transitoria 12,5% "
                            "para AT siguiente; revisar regla "
                            "regime_eligibility/14_d_3."
                        ),
                        url=(
                            f"https://www.sii.cl/normativa_legislacion/"
                            f"circulares/{cursor.year}/circu{num}.htm"
                        ),
                        publication_date=cursor,
                        target_domain="regime_eligibility",
                        target_key="14_d_3",
                        propuesta_diff={
                            "comentario": (
                                "Validar si la circular cambia los "
                                "topes ingresos / capital efectivo."
                            )
                        },
                    )
                )
            cursor += timedelta(days=1)
        return results

    async def check_presupuestos(
        self, *, since: date
    ) -> list[LegislativeAlert]:
        # Un hit por año en el primer día del año cubierto por la
        # ventana — la Ley de Presupuestos llega cada 12 meses.
        results: list[LegislativeAlert] = []
        years_seen: set[int] = set()
        cursor = since
        end = date.today()
        while cursor <= end:
            if (
                cursor.month == 1
                and cursor.day == 1
                and cursor.year not in years_seen
            ):
                years_seen.add(cursor.year)
                seed = _hash("presup", str(cursor.year))
                results.append(
                    LegislativeAlert(
                        source="presupuestos",
                        source_id=f"LEY-PRESUP-{cursor.year}",
                        title=(
                            f"Ley de Presupuestos {cursor.year}: "
                            "cambios tributarios."
                        ),
                        summary=(
                            "Revisar topes y franquicias afectadas por "
                            "el presupuesto; impacto en SENCE / I+D / "
                            "depreciación instantánea."
                        ),
                        url=(
                            f"https://www.bcn.cl/leychile/"
                            f"presupuestos-{cursor.year}"
                        ),
                        publication_date=cursor,
                        target_domain="beneficios_topes",
                        target_key=f"presupuestos_{cursor.year}",
                        propuesta_diff={
                            "review_seed": seed,
                            "comentario": (
                                "Verificar SENCE, I+D, dep. instantánea "
                                "y APV contra texto publicado."
                            ),
                        },
                    )
                )
            cursor += timedelta(days=1)
        return results
