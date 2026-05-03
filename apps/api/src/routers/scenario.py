"""Simulador de escenario de cierre — Track 9.

Track 8 (MVP) entregó el motor what-if con 4 palancas (P1, P3, P4, P5).
Track 9 agrega:

- Persistencia en `core.escenarios_simulacion` por workspace.
- `GET /api/scenario/list` para consultar el historial.
- `POST /api/scenario/compare` para enfrentar hasta 4 escenarios lado a
  lado, con marca `es_recomendado` (menor carga total) y plan de
  acción consolidado por palanca aplicada.

Fase 3 oficial: P2 SENCE, P6 I+D, P7 IVA, P8 donaciones, P9 APV, P10
IPE, P11 timing, P12 cambio régimen; SAC/RAI/REX; rules_snapshot_hash
firmado por skill 11; validación de contador socio sobre rangos.

Auth: tenancy completa requerida (workspace activo).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.tenancy import Tenancy, current_tenancy
from src.db import get_db_session
from src.domain.tax_engine.beneficios import get_beneficio
from src.domain.tax_engine.guardrails import is_recomendacion_whitelisted
from src.domain.tax_engine.idpc import compute_idpc
from src.domain.tax_engine.igc import compute_igc
from src.domain.tax_engine.snapshot import build_snapshots
from src.lib.errors import RedFlagBlocked
from src.lib.legal_texts import get_legal_text

router = APIRouter(prefix="/api/scenario", tags=["scenario"])


# Disclaimer fallback en caso de que `disclaimer-simulacion` no esté
# publicado en privacy.legal_texts. La response real siempre proviene
# de get_legal_text en cada request.
PLACEHOLDER_DISCLAIMER = (
    "Disclaimer pendiente de carga desde privacy.legal_texts."
)

# Track 11b: los topes paramétricos del simulador viven en
# tax_params.beneficios_topes con vigencia anual. Las keys consultadas:
#   * `rebaja_14e_uf` — tope absoluto rebaja 14 E.
#   * `rebaja_14e_porcentaje` — fracción máxima de RLI.
#   * `sueldo_empresarial_tope_mensual_uf` — heurística rango razonable P5.
#   * `uf_valor_clp` — UF estimada para conversiones.
# El motor no asume valores: si la fila no existe para tax_year,
# `MissingTaxYearParams` interrumpe el cálculo.

# Identifica la versión del motor que produjo el escenario. En track 11
# pasa a derivarse del rules_snapshot_hash; por ahora viaja como string
# constante para soportar la columna NOT NULL de la tabla.
ENGINE_VERSION = "track-8b-mvp-001"

# Cantidad máxima de escenarios que el comparador acepta lado a lado.
_COMPARE_MAX = 4


@dataclass(frozen=True)
class PalancaTopes:
    """Topes paramétricos vigentes para `tax_year` (tracks 11b + 8b)."""

    # P3 — Rebaja 14 E
    pct_max_14e: Decimal
    tope_14e_uf: Decimal
    # P5 — Sueldo empresarial
    sueldo_emp_tope_mensual_uf: Decimal
    # P6 — Crédito I+D
    credito_id_pct_credito: Decimal
    credito_id_pct_gasto: Decimal
    credito_id_tope_utm: Decimal
    # P2 — SENCE
    sence_pct_planilla: Decimal
    sence_tope_minimo_utm: Decimal
    # P9 — APV
    apv_tope_anual_uf: Decimal
    # Conversiones
    uf_valor_clp: Decimal
    utm_valor_clp: Decimal

    @property
    def tope_14e_pesos(self) -> Decimal:
        return self.tope_14e_uf * self.uf_valor_clp

    @property
    def sueldo_emp_tope_mensual_pesos(self) -> Decimal:
        return self.sueldo_emp_tope_mensual_uf * self.uf_valor_clp

    @property
    def credito_id_tope_pesos(self) -> Decimal:
        return self.credito_id_tope_utm * self.utm_valor_clp

    @property
    def sence_tope_minimo_pesos(self) -> Decimal:
        return self.sence_tope_minimo_utm * self.utm_valor_clp

    @property
    def apv_tope_anual_pesos(self) -> Decimal:
        return self.apv_tope_anual_uf * self.uf_valor_clp


async def _load_topes(
    session: AsyncSession, tax_year: int
) -> PalancaTopes:
    keys = [
        "rebaja_14e_porcentaje",
        "rebaja_14e_uf",
        "sueldo_empresarial_tope_mensual_uf",
        "credito_id_porcentaje_credito",
        "credito_id_porcentaje_gasto",
        "credito_id_tope_utm",
        "sence_porcentaje_planilla",
        "sence_tope_minimo_utm",
        "apv_tope_anual_uf",
        "uf_valor_clp",
        "utm_valor_clp",
    ]
    values = {
        k: await get_beneficio(session, key=k, tax_year=tax_year)
        for k in keys
    }
    return PalancaTopes(
        pct_max_14e=values["rebaja_14e_porcentaje"],
        tope_14e_uf=values["rebaja_14e_uf"],
        sueldo_emp_tope_mensual_uf=values[
            "sueldo_empresarial_tope_mensual_uf"
        ],
        credito_id_pct_credito=values["credito_id_porcentaje_credito"],
        credito_id_pct_gasto=values["credito_id_porcentaje_gasto"],
        credito_id_tope_utm=values["credito_id_tope_utm"],
        sence_pct_planilla=values["sence_porcentaje_planilla"],
        sence_tope_minimo_utm=values["sence_tope_minimo_utm"],
        apv_tope_anual_uf=values["apv_tope_anual_uf"],
        uf_valor_clp=values["uf_valor_clp"],
        utm_valor_clp=values["utm_valor_clp"],
    )


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
    sence_monto: Decimal | None = Field(
        default=None,
        ge=0,
        description=(
            "P2 — Gasto en capacitación SENCE en CLP. Genera crédito "
            "directo contra IDPC dentro del tope max(1% planilla, 9 UTM)."
        ),
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
    credito_id_monto: Decimal | None = Field(
        default=None,
        ge=0,
        description=(
            "P6 — Desembolso I+D certificado por CORFO en CLP. 35% se "
            "imputa como crédito IDPC (tope 15.000 UTM); 65% se reconoce "
            "como gasto deducible RLI."
        ),
    )
    apv_monto: Decimal | None = Field(
        default=None,
        ge=0,
        description=(
            "P9 — Aporte APV anual del dueño en CLP. Reduce la base "
            "imponible del IGC dentro del tope anual."
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
    planilla_anual_pesos: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description=(
            "Planilla anual de remuneraciones imponibles en CLP. Sirve "
            "para calcular el tope SENCE (max 1% planilla, mínimo 9 UTM)."
        ),
    )
    palancas: Palancas = Field(default_factory=Palancas)
    nombre: str | None = Field(
        default=None,
        max_length=120,
        description=(
            "Nombre opcional del escenario (ej. 'Sin palancas', 'Plan A'). "
            "Si se omite, se autogenera con régimen + año + timestamp."
        ),
    )
    empresa_id: UUID | None = Field(
        default=None,
        description=(
            "Empresa del workspace activo a la que se asocia el escenario. "
            "Si se omite, queda como escenario workspace-level."
        ),
    )


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
    id: UUID
    nombre: str
    tax_year: int
    regimen: Regimen
    base: ScenarioResultado
    simulado: ScenarioResultado
    ahorro_total: Decimal
    palancas_aplicadas: list[PalancaImpacto]
    banderas: list[BanderaRoja]
    engine_version: str = ENGINE_VERSION
    disclaimer: str = PLACEHOLDER_DISCLAIMER


class ScenarioListItem(BaseModel):
    id: UUID
    nombre: str
    tax_year: int
    regimen: Regimen
    empresa_id: UUID | None
    carga_base: Decimal
    carga_simulada: Decimal
    ahorro_total: Decimal
    es_recomendado: bool
    created_at: str


class ScenarioListResponse(BaseModel):
    scenarios: list[ScenarioListItem]


class CompareRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ids: list[UUID] = Field(min_length=1, max_length=_COMPARE_MAX)


class CompareScenarioCard(BaseModel):
    id: UUID
    nombre: str
    tax_year: int
    regimen: Regimen
    base: ScenarioResultado
    simulado: ScenarioResultado
    ahorro_total: Decimal
    palancas_aplicadas: list[PalancaImpacto]
    banderas: list[BanderaRoja]
    es_recomendado: bool


class PlanAccionItem(BaseModel):
    palanca_id: str
    label: str
    accion: str
    fundamento_legal: str
    fecha_limite: str = "31-dic"


class CompareResponse(BaseModel):
    scenarios: list[CompareScenarioCard]
    plan_accion: list[PlanAccionItem]
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


@dataclass(frozen=True)
class PalancasResult:
    """Resultado consolidado de aplicar las palancas a un escenario."""

    rli_ajustada: Decimal
    retiros_total: Decimal
    creditos_idpc: Decimal
    deduccion_igc: Decimal
    impactos: list[PalancaImpacto]
    banderas: list[BanderaRoja]


def _apply_palancas(
    req: ScenarioRequest, topes: PalancaTopes
) -> PalancasResult:
    """Aplica las palancas activas y devuelve los efectos consolidados.

    Orden (skill 8 §"Cálculo de impacto"):
      1. Gastos directos que bajan RLI: P1 (depreciación), P5 (sueldo
         empresarial), P6 (65% del desembolso I+D).
      2. Rebajas RLI: P3 (rebaja 14 E).
      3. Créditos contra IDPC: P2 (SENCE), P6 (35% del desembolso I+D).
      4. Retiros: P4 (afecta IGC, no RLI).
      5. Deducción base IGC: P9 (APV).
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
        if sueldo_mensual > topes.sueldo_emp_tope_mensual_pesos:
            banderas.append(
                BanderaRoja(
                    severidad="warning",
                    palanca_id="sueldo_empresarial",
                    mensaje=(
                        "Sueldo mensual sobre el rango razonable PLACEHOLDER "
                        f"({topes.sueldo_emp_tope_mensual_uf} UF). Requiere "
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

    # --- P6 — Crédito I+D (gasto 65% baja RLI) -------------------------
    cid_monto = p.credito_id_monto or Decimal("0")
    cid_gasto = Decimal("0")
    cid_credito = Decimal("0")
    if cid_monto > 0:
        cid_gasto = (cid_monto * topes.credito_id_pct_gasto).quantize(
            Decimal("0.01")
        )
        rli = max(Decimal("0"), rli - cid_gasto)
        cid_credito_bruto = (
            cid_monto * topes.credito_id_pct_credito
        ).quantize(Decimal("0.01"))
        cid_credito = min(cid_credito_bruto, topes.credito_id_tope_pesos)

    # --- P3 — Rebaja 14 E ----------------------------------------------
    pct = p.rebaja_14e_pct or Decimal("0")
    rebaja_aplicada = Decimal("0")
    if pct > 0:
        pct_efectivo = min(pct, topes.pct_max_14e)
        bruto = rli * pct_efectivo
        rebaja_aplicada = min(bruto, topes.tope_14e_pesos)
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

    # --- P6 — Reportar I+D una vez la RLI quedó ajustada ---------------
    impactos.append(
        PalancaImpacto(
            palanca_id="credito_id",
            label="P6 — Crédito I+D + gasto 65%",
            aplicada=cid_monto > 0,
            monto_aplicado=cid_credito + cid_gasto,
            fuente_legal="Ley 20.241; extensión Ley 21.755",
            nota=(
                "35% del desembolso certificado por CORFO se imputa "
                "como crédito IDPC (tope 15.000 UTM); el 65% restante "
                "se reconoce como gasto deducible RLI."
            )
            if cid_monto > 0
            else None,
        )
    )

    # --- P2 — SENCE: crédito directo IDPC -------------------------------
    sence_monto = p.sence_monto or Decimal("0")
    sence_credito = Decimal("0")
    if sence_monto > 0:
        tope_sence = max(
            (req.planilla_anual_pesos * topes.sence_pct_planilla).quantize(
                Decimal("0.01")
            ),
            topes.sence_tope_minimo_pesos,
        )
        sence_credito = min(sence_monto, tope_sence)
        if sence_monto > tope_sence:
            banderas.append(
                BanderaRoja(
                    severidad="warning",
                    palanca_id="sence",
                    mensaje=(
                        "Gasto SENCE excede el tope max(1% planilla, "
                        f"{topes.sence_tope_minimo_utm} UTM). Solo se "
                        "imputa hasta el tope; el exceso no genera "
                        "crédito IDPC. Verifica con OTEC acreditada."
                    ),
                )
            )
    impactos.append(
        PalancaImpacto(
            palanca_id="sence",
            label="P2 — Franquicia SENCE",
            aplicada=sence_credito > 0,
            monto_aplicado=sence_credito,
            fuente_legal="Ley 19.518",
            nota=(
                "Crédito directo contra IDPC (no baja RLI). Requiere "
                "OTEC acreditada y asistencia efectiva del trabajador."
            )
            if sence_credito > 0
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

    # --- P9 — APV: deduce base IGC del dueño ---------------------------
    apv_monto = p.apv_monto or Decimal("0")
    apv_aplicado = Decimal("0")
    if apv_monto > 0:
        apv_aplicado = min(apv_monto, topes.apv_tope_anual_pesos)
        if apv_monto > topes.apv_tope_anual_pesos:
            banderas.append(
                BanderaRoja(
                    severidad="warning",
                    palanca_id="apv",
                    mensaje=(
                        "Aporte APV excede el tope anual "
                        f"{topes.apv_tope_anual_uf} UF (PLACEHOLDER). "
                        "Solo se deduce hasta el tope; el exceso queda "
                        "fuera del beneficio del art. 42 bis."
                    ),
                )
            )
    impactos.append(
        PalancaImpacto(
            palanca_id="apv",
            label="P9 — APV régimen A del dueño",
            aplicada=apv_aplicado > 0,
            monto_aplicado=apv_aplicado,
            fuente_legal="art. 42 bis LIR; DL 3.500",
            nota=(
                "Reduce la base imponible del IGC del dueño (no IDPC, "
                "no RLI). Monto se ajusta al tope anual placeholder."
            )
            if apv_aplicado > 0
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

    return PalancasResult(
        rli_ajustada=rli,
        retiros_total=retiros_total,
        creditos_idpc=cid_credito + sence_credito,
        deduccion_igc=apv_aplicado,
        impactos=impactos,
        banderas=banderas,
    )


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
    creditos_idpc: Decimal = Decimal("0"),
    deduccion_igc: Decimal = Decimal("0"),
) -> ScenarioResultado:
    """Calcula RLI, IDPC neto, IGC del dueño y carga total.

    `creditos_idpc` (P2 SENCE + P6 35% I+D) se imputa contra IDPC con
    piso 0. `deduccion_igc` (P9 APV) reduce la base IGC con piso 0.
    Para 14 D N°8 (transparente) IDPC=0, así que los créditos no
    cambian la carga: el dueño consume el beneficio en IGC sólo si la
    palanca lo modela explícitamente (P9). Trato simétrico aquí.
    """
    idpc_bruto = await compute_idpc(
        session, regimen=regimen, tax_year=tax_year, rli=rli
    )
    idpc = max(Decimal("0"), idpc_bruto - creditos_idpc)
    base_igc_full = rli if regimen == "14_d_8" else retiros_total
    base_igc = max(Decimal("0"), base_igc_full - deduccion_igc)
    igc = await compute_igc(session, tax_year=tax_year, base_pesos=base_igc)
    return ScenarioResultado(
        rli=rli,
        idpc=idpc,
        retiros_total=retiros_total,
        igc_dueno=igc,
        carga_total=idpc + igc,
    )


def _default_nombre(regimen: Regimen, tax_year: int) -> str:
    return f"Escenario {regimen.upper()} AT{tax_year}"


async def _assert_empresa_in_workspace(
    session: AsyncSession, empresa_id: UUID
) -> None:
    """Bajo RLS, ver una empresa implica pertenecer al workspace activo.

    Si el SELECT vuelve vacío la empresa no existe (en este workspace) o
    no se tiene acceso por rol — en ambos casos rechazamos con 422.
    """
    result = await session.execute(
        text("select 1 from core.empresas where id = :id and deleted_at is null"),
        {"id": str(empresa_id)},
    )
    if result.first() is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"empresa_id {empresa_id} no existe en el workspace o no "
                "tienes acceso bajo tu rol."
            ),
        )


def _plan_accion_for(
    impactos: list[PalancaImpacto],
) -> list[PlanAccionItem]:
    """Genera la checklist de acción para palancas aplicadas.

    Cada item ata la palanca a su acción concreta y a su fundamento
    legal. La fecha límite por defecto es 31-dic; en track 10 se
    refinará por palanca (ej. SENCE puede tener plazos antes).
    """
    plan_text: dict[str, str] = {
        "dep_instantanea": (
            "Adquirir y poner en uso el activo fijo dentro del ejercicio. "
            "Conservar factura de compra y evidencia de uso."
        ),
        "sence": (
            "Inscribir cursos con OTEC acreditada y obtener certificación "
            "de asistencia antes del 31-dic. Conservar comprobantes."
        ),
        "rebaja_14e": (
            "Reinvertir el monto en la empresa antes del cierre. No retirar "
            "el equivalente en los 12 meses siguientes."
        ),
        "retiros_adicionales": (
            "Documentar el retiro contra los registros SAC/RAI/REX y verificar "
            "imputación con contador antes de ejecutar."
        ),
        "sueldo_empresarial": (
            "Formalizar contrato y cotizaciones del socio activo, mantener "
            "evidencia de presencia efectiva y razonabilidad del monto."
        ),
        "credito_id": (
            "Coordinar certificación CORFO del proyecto I+D y mantener "
            "trazabilidad del desembolso (35% crédito + 65% gasto)."
        ),
        "apv": (
            "Realizar el aporte APV antes del cierre del ejercicio del "
            "dueño. Conservar comprobante de la AFP/AGF."
        ),
    }
    items: list[PlanAccionItem] = []
    for p in impactos:
        if not p.aplicada:
            continue
        items.append(
            PlanAccionItem(
                palanca_id=p.palanca_id,
                label=p.label,
                accion=plan_text.get(
                    p.palanca_id, "Coordinar ejecución con contador socio."
                ),
                fundamento_legal=p.fuente_legal,
            )
        )
    return items


# ---------------------------------------------------------------------------
# Persistencia
# ---------------------------------------------------------------------------


def _serialize_jsonb(value: Any) -> str:
    return json.dumps(value, default=str)


async def _persist(
    session: AsyncSession,
    *,
    workspace_id: UUID,
    user_id: UUID,
    empresa_id: UUID | None,
    nombre: str,
    regimen: Regimen,
    tax_year: int,
    request: ScenarioRequest,
    base: ScenarioResultado,
    simulado: ScenarioResultado,
    ahorro: Decimal,
    impactos: list[PalancaImpacto],
    banderas: list[BanderaRoja],
) -> UUID:
    """Inserta el escenario y devuelve el id generado por Postgres."""
    inputs_payload = {
        "regimen": regimen,
        "tax_year": tax_year,
        "rli_base": str(request.rli_base),
        "retiros_base": str(request.retiros_base),
        "palancas": json.loads(
            request.palancas.model_dump_json(exclude_none=True)
        ),
    }
    outputs_payload = {
        "base": json.loads(base.model_dump_json()),
        "simulado": json.loads(simulado.model_dump_json()),
        "ahorro_total": str(ahorro),
        "palancas_aplicadas": [
            json.loads(i.model_dump_json()) for i in impactos
        ],
        "banderas": [json.loads(b.model_dump_json()) for b in banderas],
    }

    # Track 11c: snapshots reales del rule_set + tax_year_params usados.
    rule_snap, params_snap, snap_hash = await build_snapshots(
        session, tax_year=tax_year
    )

    result = await session.execute(
        text(
            """
            insert into core.escenarios_simulacion
                (workspace_id, empresa_id, tax_year, nombre,
                 regimen, inputs, outputs,
                 engine_version, created_by,
                 rule_set_snapshot, tax_year_params_snapshot,
                 rules_snapshot_hash)
            values
                (:ws, :empresa, :year, :nombre,
                 :regimen, cast(:inputs as jsonb), cast(:outputs as jsonb),
                 :ver, :uid,
                 cast(:rule_snap as jsonb),
                 cast(:params_snap as jsonb),
                 :hash)
            returning id
            """
        ),
        {
            "ws": str(workspace_id),
            "empresa": str(empresa_id) if empresa_id is not None else None,
            "year": tax_year,
            "nombre": nombre,
            "regimen": regimen,
            "inputs": _serialize_jsonb(inputs_payload),
            "outputs": _serialize_jsonb(outputs_payload),
            "ver": ENGINE_VERSION,
            "uid": str(user_id),
            "rule_snap": _serialize_jsonb(rule_snap),
            "params_snap": _serialize_jsonb(params_snap),
            "hash": snap_hash,
        },
    )
    row = result.scalar_one()
    return UUID(str(row))


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/simulate", response_model=ScenarioResponse)
async def simulate(
    payload: ScenarioRequest,
    tenancy: Tenancy = Depends(current_tenancy),
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

    if payload.empresa_id is not None:
        await _assert_empresa_in_workspace(session, payload.empresa_id)

    topes = await _load_topes(session, payload.tax_year)
    result = _apply_palancas(payload, topes)

    # Skill 1: cada palanca aplicada debe estar en la lista blanca.
    for impacto in result.impactos:
        if impacto.aplicada and not await is_recomendacion_whitelisted(
            session, impacto.palanca_id, payload.tax_year
        ):
            raise RedFlagBlocked(
                f"palanca {impacto.palanca_id!r} fuera de la lista blanca "
                "de recomendaciones (skill 1, NGA arts. 4 bis/ter/quáter CT)"
            )

    simulado = await _carga(
        session,
        regimen=payload.regimen,
        tax_year=payload.tax_year,
        rli=result.rli_ajustada,
        retiros_total=result.retiros_total,
        creditos_idpc=result.creditos_idpc,
        deduccion_igc=result.deduccion_igc,
    )

    ahorro = base.carga_total - simulado.carga_total
    nombre = payload.nombre or _default_nombre(payload.regimen, payload.tax_year)

    scenario_id = await _persist(
        session,
        workspace_id=tenancy.workspace_id,
        user_id=tenancy.user_id,
        empresa_id=payload.empresa_id,
        nombre=nombre,
        regimen=payload.regimen,
        tax_year=payload.tax_year,
        request=payload,
        base=base,
        simulado=simulado,
        ahorro=ahorro,
        impactos=result.impactos,
        banderas=result.banderas,
    )

    legal = await get_legal_text(session, "disclaimer-simulacion")
    return ScenarioResponse(
        id=scenario_id,
        nombre=nombre,
        tax_year=payload.tax_year,
        regimen=payload.regimen,
        base=base,
        simulado=simulado,
        ahorro_total=ahorro,
        palancas_aplicadas=result.impactos,
        banderas=result.banderas,
        disclaimer=legal.body,
    )


@router.get("/list", response_model=ScenarioListResponse)
async def list_scenarios(
    tax_year: int | None = None,
    empresa_id: UUID | None = None,
    limit: int = 50,
    _tenancy: Tenancy = Depends(current_tenancy),
    session: AsyncSession = Depends(get_db_session),
) -> ScenarioListResponse:
    """Lista escenarios del workspace activo (RLS filtra automáticamente).

    `es_recomendado` se calcula en vivo: el escenario con menor carga
    total entre los listados queda marcado. Empate → desempata por
    menor cantidad de palancas activadas (preferencia por simplicidad).
    """
    if limit < 1 or limit > 200:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="limit debe estar entre 1 y 200",
        )

    params: dict[str, Any] = {
        "limit": limit,
        "year": tax_year,
        "empresa": str(empresa_id) if empresa_id is not None else None,
    }

    # `coalesce(:p, col)` actúa como "no filter when null", lo que
    # mantiene una query estática y deja al planner cachear un único plan.
    result = await session.execute(
        text(
            """
            select id, nombre, tax_year, regimen, empresa_id, outputs,
                   created_at
              from core.escenarios_simulacion
             where regimen is not null
               and tax_year = coalesce(:year, tax_year)
               and (
                    :empresa::uuid is null
                    or empresa_id = :empresa::uuid
               )
             order by created_at desc
             limit :limit
            """
        ),
        params,
    )
    rows = result.mappings().all()

    items: list[ScenarioListItem] = []
    for row in rows:
        outputs = row["outputs"] or {}
        carga_base = Decimal(str((outputs.get("base") or {}).get("carga_total", "0")))
        carga_sim = Decimal(
            str((outputs.get("simulado") or {}).get("carga_total", "0"))
        )
        ahorro = Decimal(str(outputs.get("ahorro_total", "0")))
        items.append(
            ScenarioListItem(
                id=UUID(str(row["id"])),
                nombre=row["nombre"],
                tax_year=row["tax_year"],
                regimen=row["regimen"],
                empresa_id=(
                    UUID(str(row["empresa_id"]))
                    if row["empresa_id"] is not None
                    else None
                ),
                carga_base=carga_base,
                carga_simulada=carga_sim,
                ahorro_total=ahorro,
                es_recomendado=False,
                created_at=row["created_at"].isoformat(),
            )
        )

    _mark_recomendado(items, lambda i: (i.carga_simulada, 0))

    return ScenarioListResponse(scenarios=items)


@router.post("/compare", response_model=CompareResponse)
async def compare(
    payload: CompareRequest,
    _tenancy: Tenancy = Depends(current_tenancy),
    session: AsyncSession = Depends(get_db_session),
) -> CompareResponse:
    """Compara hasta 4 escenarios lado a lado y consolida plan de acción.

    `es_recomendado` se asigna al escenario con menor carga total entre
    los provistos (lícitos por construcción, ya validados al simular).
    Empate → menos palancas activadas.
    """
    ids_str = [str(i) for i in payload.ids]
    result = await session.execute(
        text(
            """
            select id, nombre, tax_year, regimen, outputs
              from core.escenarios_simulacion
             where id = any(cast(:ids as uuid[]))
            """
        ),
        {"ids": ids_str},
    )
    rows = {str(row["id"]): row for row in result.mappings().all()}

    missing = [str(i) for i in payload.ids if str(i) not in rows]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"escenarios no encontrados: {', '.join(missing)}",
        )

    cards: list[CompareScenarioCard] = []
    for sid in payload.ids:
        row = rows[str(sid)]
        outputs = row["outputs"] or {}
        impactos = [
            PalancaImpacto.model_validate(p)
            for p in outputs.get("palancas_aplicadas", [])
        ]
        banderas = [
            BanderaRoja.model_validate(b)
            for b in outputs.get("banderas", [])
        ]
        cards.append(
            CompareScenarioCard(
                id=UUID(str(row["id"])),
                nombre=row["nombre"],
                tax_year=row["tax_year"],
                regimen=row["regimen"],
                base=ScenarioResultado.model_validate(outputs.get("base") or {}),
                simulado=ScenarioResultado.model_validate(
                    outputs.get("simulado") or {}
                ),
                ahorro_total=Decimal(str(outputs.get("ahorro_total", "0"))),
                palancas_aplicadas=impactos,
                banderas=banderas,
                es_recomendado=False,
            )
        )

    _mark_recomendado(
        cards,
        lambda c: (
            c.simulado.carga_total,
            sum(1 for p in c.palancas_aplicadas if p.aplicada),
        ),
    )

    # Plan de acción: dedupe por palanca_id de la unión de palancas del
    # escenario recomendado (si hay) o del primero pasado.
    pivot = next((c for c in cards if c.es_recomendado), cards[0])
    plan = _plan_accion_for(pivot.palancas_aplicadas)

    return CompareResponse(scenarios=cards, plan_accion=plan)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mark_recomendado(items: list[Any], key: Any) -> None:
    """Marca como `es_recomendado=True` al item con la menor key."""
    if not items:
        return
    winner = min(items, key=key)
    winner.es_recomendado = True
