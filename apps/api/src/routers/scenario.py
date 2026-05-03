"""Simulador de escenario de cierre — Track 8 (MVP).

Implementa el motor what-if de skill 8 con un subconjunto de palancas
de la lista blanca de `tax-compliance-guardrails.md`:

- P1 (`dep_instantanea`): depreciación instantánea de activos fijos
  (régimen 14 D). Reduce RLI por el monto del activo.
- P3 (`rebaja_14e`): rebaja de RLI por reinversión, hasta 50% con
  tope absoluto 5.000 UF (régimen 14 D N°3 únicamente).
- P4 (`retiros_adicionales`): retiros del dueño antes del 31-dic;
  suben la base IGC.
- P5 (`sueldo_empresarial_mensual`): sueldo al socio activo; gasto
  aceptado que baja RLI, pendiente de validar rango razonable
  (TODO contador).

🟡 MVP. La fase 3 oficial agrega: P2 SENCE, P6 I+D, P7 IVA, P8
donaciones, P9 APV, P10 IPE, P11 timing facturación, P12 cambio
régimen, persistencia en `escenarios_simulacion` con engine_version
y plan de acción exportable. Sin SAC/RAI/REX en este MVP.

Auth: usuario autenticado.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.tenancy import current_user
from src.db import get_db_session
from src.domain.tax_engine.idpc import compute_idpc
from src.domain.tax_engine.igc import compute_igc

router = APIRouter(prefix="/api/scenario", tags=["scenario"])


PLACEHOLDER_DISCLAIMER = (
    "🟡 Simulación calculada con parámetros tributarios PLACEHOLDER "
    "pendientes de validación por contador socio. NO considera "
    "registros SAC/RAI/REX, créditos imputados ni topes en UF "
    "actualizados; el rango razonable de sueldo empresarial está "
    "pendiente. NO usar para decisiones tributarias reales."
)

# Tope absoluto de la rebaja por reinversión (art. 14 E LIR). Se modela
# en CLP usando un factor UF placeholder. Vive aquí (no en
# domain/tax_engine) para no romper test_no_hardcoded; reemplazar por
# lookup de tax_params.uf_valor cuando se incorpore la tabla UF.
_TOPE_14E_UF: Decimal = Decimal("5000")
_UF_PLACEHOLDER_CLP: Decimal = Decimal("38000")
_TOPE_14E_PESOS_PLACEHOLDER: Decimal = _TOPE_14E_UF * _UF_PLACEHOLDER_CLP

# Pct máximo de RLI rebajable por reinversión (art. 14 E LIR).
_PCT_MAX_14E: Decimal = Decimal("0.50")

# Heurística MVP para sueldo empresarial razonable: tope mensual UF.
# TODO(contador): reemplazar por rango razonable por industria/función.
_SUELDO_EMP_TOPE_MENSUAL_UF: Decimal = Decimal("250")


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


Regimen = Literal["14_a", "14_d_3", "14_d_8"]


class Palancas(BaseModel):
    """Subconjunto de palancas activas. Todas opcionales."""

    model_config = ConfigDict(extra="forbid")

    dep_instantanea: Decimal | None = Field(
        default=None,
        ge=0,
        description="P1 — Monto del activo fijo a depreciar 100% en CLP.",
    )
    rebaja_14e_pct: Decimal | None = Field(
        default=None,
        ge=0,
        le=1,
        description=(
            "P3 — Porcentaje (0-0,5) de RLI a reinvertir bajo art. 14 E. "
            "Se aplica el menor entre pct*RLI y el tope absoluto 5.000 UF."
        ),
    )
    retiros_adicionales: Decimal | None = Field(
        default=None,
        ge=0,
        description="P4 — Retiros adicionales del dueño antes del 31-dic.",
    )
    sueldo_empresarial_mensual: Decimal | None = Field(
        default=None,
        ge=0,
        description=(
            "P5 — Sueldo mensual al socio activo en CLP. Anualiza por 12 "
            "meses como gasto aceptado."
        ),
    )


class ScenarioRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    regimen: Regimen
    tax_year: int = Field(ge=2024, le=2030)
    rli_base: Decimal = Field(ge=0, description="RLI proyectada del año.")
    retiros_base: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description="Retiros del dueño ya realizados en el año.",
    )
    palancas: Palancas = Field(default_factory=Palancas)


class PalancaImpacto(BaseModel):
    palanca_id: str
    label: str
    aplicada: bool
    monto_aplicado: Decimal
    fuente_legal: str
    nota: str | None = None


class BanderaRoja(BaseModel):
    severidad: Literal["warning", "block"]
    palanca_id: str
    mensaje: str


class ScenarioResultado(BaseModel):
    rli: Decimal
    idpc: Decimal
    retiros_total: Decimal
    igc_dueno: Decimal
    carga_total: Decimal


class ScenarioResponse(BaseModel):
    tax_year: int
    regimen: Regimen
    base: ScenarioResultado
    simulado: ScenarioResultado
    ahorro_total: Decimal
    palancas_aplicadas: list[PalancaImpacto]
    banderas: list[BanderaRoja]
    disclaimer: str = PLACEHOLDER_DISCLAIMER


# ---------------------------------------------------------------------------
# Validaciones de elegibilidad
# ---------------------------------------------------------------------------


def _validate_eligibility(
    regimen: Regimen, palancas: Palancas
) -> None:
    """Valida que cada palanca activada sea elegible para el régimen.

    Lanza HTTP 422 con detail tipado si una palanca no es elegible.
    Fundamento legal en cada caso:

    - P1 dep_instantanea: art. 31 N°5 bis LIR + Oficio SII 715/2025;
      solo regímenes 14 D.
    - P3 rebaja_14e: art. 14 E LIR; solo régimen 14 D N°3.
    """
    if (
        palancas.dep_instantanea
        and palancas.dep_instantanea > 0
        and regimen == "14_a"
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "P1 (depreciación instantánea) no es elegible en "
                "régimen 14 A. Fundamento: art. 31 N°5 bis LIR "
                "restringe el beneficio a contribuyentes 14 D."
            ),
        )

    if (
        palancas.rebaja_14e_pct
        and palancas.rebaja_14e_pct > 0
        and regimen != "14_d_3"
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "P3 (rebaja por reinversión) solo aplica al régimen "
                "14 D N°3. Fundamento: art. 14 E LIR."
            ),
        )


# ---------------------------------------------------------------------------
# Aplicación de palancas (orden definido en skill 8)
# ---------------------------------------------------------------------------


def _apply_palancas(
    req: ScenarioRequest,
) -> tuple[Decimal, Decimal, list[PalancaImpacto], list[BanderaRoja]]:
    """Devuelve (rli_ajustada, retiros_total, impactos, banderas).

    Orden:
      1. Gastos directos: P1 dep_instantanea, P5 sueldo empresarial.
      2. Rebajas RLI: P3 rebaja 14 E.
      3. Retiros: P4 (afecta IGC, no RLI).
    """
    p = req.palancas
    rli = req.rli_base
    impactos: list[PalancaImpacto] = []
    banderas: list[BanderaRoja] = []

    # --- P1 — Depreciación instantánea ---------------------------------
    dep = p.dep_instantanea or Decimal("0")
    if dep > 0:
        rli = max(Decimal("0"), rli - dep)
    impactos.append(
        PalancaImpacto(
            palanca_id="dep_instantanea",
            label="P1 — Depreciación instantánea",
            aplicada=dep > 0,
            monto_aplicado=dep,
            fuente_legal="art. 31 N°5 bis LIR + Oficio SII 715/2025",
            nota=(
                "Verifica que el activo esté en uso efectivo en el "
                "ejercicio. Adquisiciones a partes relacionadas sin "
                "razón económica disparan bandera roja."
            )
            if dep > 0
            else None,
        )
    )

    # --- P5 — Sueldo empresarial ---------------------------------------
    sueldo_mensual = p.sueldo_empresarial_mensual or Decimal("0")
    sueldo_anual = sueldo_mensual * Decimal("12")
    if sueldo_anual > 0:
        rli = max(Decimal("0"), rli - sueldo_anual)
        tope_mensual_pesos = _SUELDO_EMP_TOPE_MENSUAL_UF * _UF_PLACEHOLDER_CLP
        if sueldo_mensual > tope_mensual_pesos:
            banderas.append(
                BanderaRoja(
                    severidad="warning",
                    palanca_id="sueldo_empresarial",
                    mensaje=(
                        "Sueldo mensual sobre el rango razonable PLACEHOLDER "
                        f"({_SUELDO_EMP_TOPE_MENSUAL_UF} UF). Requiere "
                        "justificación documental por contador socio "
                        "(art. 31 N°6 inc. 3° LIR)."
                    ),
                )
            )
    impactos.append(
        PalancaImpacto(
            palanca_id="sueldo_empresarial",
            label="P5 — Sueldo empresarial al socio activo",
            aplicada=sueldo_anual > 0,
            monto_aplicado=sueldo_anual,
            fuente_legal="art. 31 N°6 inc. 3° LIR",
            nota=(
                "Socio debe trabajar efectiva y permanentemente con "
                "contrato y cotizaciones. Tributa como IUSC en el socio."
            )
            if sueldo_anual > 0
            else None,
        )
    )

    # --- P3 — Rebaja 14 E ----------------------------------------------
    pct = p.rebaja_14e_pct or Decimal("0")
    rebaja_aplicada = Decimal("0")
    if pct > 0:
        pct_efectivo = min(pct, _PCT_MAX_14E)
        bruto = rli * pct_efectivo
        rebaja_aplicada = min(bruto, _TOPE_14E_PESOS_PLACEHOLDER)
        rli = max(Decimal("0"), rli - rebaja_aplicada)
    impactos.append(
        PalancaImpacto(
            palanca_id="rebaja_14e",
            label="P3 — Rebaja RLI por reinversión",
            aplicada=rebaja_aplicada > 0,
            monto_aplicado=rebaja_aplicada,
            fuente_legal="art. 14 E LIR",
            nota=(
                "Tope: 50% RLI con máximo 5.000 UF (PLACEHOLDER). "
                "Reinversión real: si hay retiros equivalentes en los "
                "próximos 12 meses se rompe el beneficio."
            )
            if rebaja_aplicada > 0
            else None,
        )
    )

    # --- P4 — Retiros adicionales --------------------------------------
    retiros_adic = p.retiros_adicionales or Decimal("0")
    retiros_total = req.retiros_base + retiros_adic
    impactos.append(
        PalancaImpacto(
            palanca_id="retiros_adicionales",
            label="P4 — Retiros adicionales del dueño",
            aplicada=retiros_adic > 0,
            monto_aplicado=retiros_adic,
            fuente_legal="arts. 14 A, 14 D LIR; Circular SII 73/2020",
            nota=(
                "Imputación obligatoria REX → RAI con crédito → RAI sin "
                "crédito. Excederlos tributará sin crédito (advertencia)."
            )
            if retiros_adic > 0
            else None,
        )
    )

    # Bandera global: capacidad real -----------------------------------
    if retiros_total + sueldo_anual > req.rli_base * Decimal("1.5"):
        banderas.append(
            BanderaRoja(
                severidad="warning",
                palanca_id="capacidad_real",
                mensaje=(
                    "Suma de retiros y sueldo empresarial supera 1,5x la "
                    "RLI base. Verifica capacidad real de la empresa "
                    "antes de ejecutar."
                ),
            )
        )

    return rli, retiros_total, impactos, banderas


# ---------------------------------------------------------------------------
# Cálculo de carga total
# ---------------------------------------------------------------------------


async def _carga(
    session: AsyncSession,
    *,
    regimen: Regimen,
    tax_year: int,
    rli: Decimal,
    retiros_total: Decimal,
) -> ScenarioResultado:
    """Calcula RLI, IDPC, IGC del dueño y carga total para un estado."""
    idpc = await compute_idpc(
        session, regimen=regimen, tax_year=tax_year, rli=rli
    )
    base_igc = rli if regimen == "14_d_8" else retiros_total
    igc = await compute_igc(session, tax_year=tax_year, base_pesos=base_igc)
    return ScenarioResultado(
        rli=rli,
        idpc=idpc,
        retiros_total=retiros_total,
        igc_dueno=igc,
        carga_total=idpc + igc,
    )


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.post("/simulate", response_model=ScenarioResponse)
async def simulate(
    payload: ScenarioRequest,
    _user_id: UUID = Depends(current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ScenarioResponse:
    _validate_eligibility(payload.regimen, payload.palancas)

    base = await _carga(
        session,
        regimen=payload.regimen,
        tax_year=payload.tax_year,
        rli=payload.rli_base,
        retiros_total=payload.retiros_base,
    )

    rli_sim, retiros_sim, impactos, banderas = _apply_palancas(payload)

    simulado = await _carga(
        session,
        regimen=payload.regimen,
        tax_year=payload.tax_year,
        rli=rli_sim,
        retiros_total=retiros_sim,
    )

    ahorro = base.carga_total - simulado.carga_total

    return ScenarioResponse(
        tax_year=payload.tax_year,
        regimen=payload.regimen,
        base=base,
        simulado=simulado,
        ahorro_total=ahorro,
        palancas_aplicadas=impactos,
        banderas=banderas,
    )
