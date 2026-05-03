"""Comparador multi-régimen.

🟡 Versión placeholder de Track 7. La fase 3 oficial (skill 7) agrega
elegibilidad por requisitos objetivos, proyección 3 años, registros
SAC/RAI/REX, créditos imputados contra IDPC y workflow firmado.

Track 7 toma:
  tax_year, rli (proyectada), retiros_pesos (del dueño en el año)

y devuelve, para cada régimen:
  - 14 A (régimen general semi-integrado)
  - 14 D N°3 — escenario base (tasa transitoria 12,5% AT 2026 si aplica)
  - 14 D N°3 — escenario revertido (tasa permanente 25% si se rompe
    condicionalidad Ley 21.735 art. 4° transitorio)
  - 14 D N°8 (Pro PyME Transparente: IDPC = 0, IGC del dueño sobre RLI
    completa atribuida)

Cálculos:
  IDPC = tasa_regimen * rli  (tasa de tax_params.idpc_rates o forzada)
  IGC del dueño = compute_igc(tax_year, base)
    base = retiros_pesos para 14 A y 14 D N°3
    base = rli (atribuida) para 14 D N°8
  carga_total = IDPC + IGC del dueño

Auth: usuario autenticado. Sin tenancy required (lectura tax_params).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.tenancy import current_user
from src.db import get_db_session
from src.domain.tax_engine.idpc import compute_idpc
from src.domain.tax_engine.igc import compute_igc

router = APIRouter(prefix="/api/calc", tags=["calc"])


PLACEHOLDER_DISCLAIMER = (
    "🟡 Comparativa calculada con parámetros tributarios PLACEHOLDER "
    "pendientes de validación por contador socio. Esta versión NO "
    "considera registros SAC/RAI/REX, créditos imputados ni proyección "
    "multi-año (eso entra en fase 3 oficial). NO usar para decisiones "
    "tributarias reales."
)

_FLAG_14D3_REVERTIDA = "idpc_14d3_revertida_rate"


async def _get_revertida_rate(
    session: AsyncSession, tax_year: int
) -> Decimal:
    """Lee la tasa revertida del feature flag publicado (skill 11)."""
    from datetime import date

    target_date = date(tax_year, 12, 31)
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
        {"k": _FLAG_14D3_REVERTIDA, "t": target_date},
    )
    row = result.first()
    return Decimal(str(row[0])) if row else Decimal("0")


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class ComparadorRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tax_year: int = Field(ge=2024, le=2030)
    rli: Decimal = Field(ge=0, description="RLI proyectada en CLP")
    retiros_pesos: Decimal = Field(
        ge=0, description="Retiros del dueño en el año, CLP"
    )


class RegimenScenario(BaseModel):
    model_config = ConfigDict(frozen=True)

    regimen: Literal["14_a", "14_d_3", "14_d_3_revertido", "14_d_8"]
    label: str
    idpc: Decimal
    igc_dueno: Decimal
    carga_total: Decimal
    ahorro_vs_14a: Decimal
    es_recomendado: bool
    es_transitoria: bool
    nota: str | None
    fuente_legal: str


class ComparadorResponse(BaseModel):
    tax_year: int
    rli: Decimal
    retiros_pesos: Decimal
    scenarios: list[RegimenScenario]
    disclaimer: str = PLACEHOLDER_DISCLAIMER


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.post("/comparador-regimen", response_model=ComparadorResponse)
async def comparador_regimen(
    payload: ComparadorRequest,
    _user_id: UUID = Depends(current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ComparadorResponse:
    year = payload.tax_year
    rli = payload.rli
    retiros = payload.retiros_pesos

    # IGC sobre retiros (común a 14 A y 14 D N°3).
    igc_sobre_retiros = await compute_igc(
        session, tax_year=year, base_pesos=retiros
    )
    # IGC sobre RLI atribuida (14 D N°8 transparente).
    igc_sobre_rli = await compute_igc(
        session, tax_year=year, base_pesos=rli
    )

    # 14 A
    idpc_14a = await compute_idpc(
        session, regimen="14_a", tax_year=year, rli=rli
    )
    carga_14a = idpc_14a + igc_sobre_retiros

    # 14 D N°3 — base (tasa de seeds)
    idpc_14d3_base = await compute_idpc(
        session, regimen="14_d_3", tax_year=year, rli=rli
    )
    carga_14d3_base = idpc_14d3_base + igc_sobre_retiros

    # 14 D N°3 — revertido (tasa del feature flag, skill 11)
    revertida_rate = await _get_revertida_rate(session, year)
    idpc_14d3_rev = (revertida_rate * rli).quantize(Decimal("0.01"))
    carga_14d3_rev = idpc_14d3_rev + igc_sobre_retiros

    # 14 D N°8 — transparente
    idpc_14d8 = await compute_idpc(
        session, regimen="14_d_8", tax_year=year, rli=rli
    )
    carga_14d8 = idpc_14d8 + igc_sobre_rli

    raw_scenarios: list[dict[str, Any]] = [
        {
            "regimen": "14_a",
            "label": "14 A — Régimen general (semi-integrado)",
            "idpc": idpc_14a,
            "igc_dueno": igc_sobre_retiros,
            "carga_total": carga_14a,
            "es_transitoria": False,
            "nota": None,
            "fuente_legal": "art. 14 A LIR",
        },
        {
            "regimen": "14_d_3",
            "label": "14 D N°3 — Pro PyME General (tasa actual)",
            "idpc": idpc_14d3_base,
            "igc_dueno": igc_sobre_retiros,
            "carga_total": carga_14d3_base,
            "es_transitoria": True,
            "nota": (
                "Asume tasa transitoria de tax_params.idpc_rates para el año. "
                "Si se rompe condicionalidad Ley 21.735, ver escenario revertido."
            ),
            "fuente_legal": "art. 14 D N°3 LIR; Ley 21.755; Circular SII 53/2025",
        },
        {
            "regimen": "14_d_3_revertido",
            "label": "14 D N°3 — Escenario revertido (25%)",
            "idpc": idpc_14d3_rev,
            "igc_dueno": igc_sobre_retiros,
            "carga_total": carga_14d3_rev,
            "es_transitoria": False,
            "nota": (
                "Hipotético: si se rompe la condicionalidad por cotización "
                "empleador del art. 4° transitorio Ley 21.735, la tasa vuelve "
                "a 25% permanente."
            ),
            "fuente_legal": "art. 14 D N°3 LIR; Ley 21.735 art. 4° transitorio",
        },
        {
            "regimen": "14_d_8",
            "label": "14 D N°8 — Pro PyME Transparente",
            "idpc": idpc_14d8,
            "igc_dueno": igc_sobre_rli,
            "carga_total": carga_14d8,
            "es_transitoria": False,
            "nota": (
                "Régimen transparente: IDPC a nivel empresa = 0; el dueño "
                "tributa IGC sobre la RLI completa atribuida (independiente "
                "del monto de retiros)."
            ),
            "fuente_legal": "art. 14 D N°8 LIR",
        },
    ]

    # ahorro_vs_14a
    for s in raw_scenarios:
        s["ahorro_vs_14a"] = (carga_14a - s["carga_total"]).quantize(
            Decimal("0.01")
        )

    # es_recomendado: el de menor carga_total. En empate, prefiere
    # los no-transitorios (más seguro).
    def _key(s: dict[str, Any]) -> tuple[Decimal, bool]:
        return (s["carga_total"], s["es_transitoria"])

    best = min(raw_scenarios, key=_key)
    for s in raw_scenarios:
        s["es_recomendado"] = s is best

    scenarios = [RegimenScenario(**s) for s in raw_scenarios]

    return ComparadorResponse(
        tax_year=year,
        rli=rli,
        retiros_pesos=retiros,
        scenarios=scenarios,
    )
