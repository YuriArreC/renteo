"""Caso de estudio 01 — Ferretería PYME MVP.

Reproduce el comparador de `docs/casos-estudio/01-ferreteria-pyme-mvp.md`
llamando al **motor real del simulador**: `_load_topes`, `_apply_palancas`
y `_carga` de `src.routers.scenario` — exactamente los mismos que ejecuta
`POST /api/scenario/simulate` — más `build_snapshots` para el hash de
reproducibilidad. NO reimplementa aritmética tributaria: si cambia el
router, cambian estos números.

(Nota de arquitectura: idealmente la lógica pura del simulador viviría en
`src/domain/tax_engine/` (CLAUDE.md); hoy vive en el router y la
importamos desde ahí. La extracción a domain queda como refactor aparte;
lo importante es que este script llama al motor real, no una copia.)

🟡 INSPECCIÓN INTERNA — no es asesoría tributaria. Mientras los goldens
estén en xfail y los placeholders sin firma, los outputs son preliminares.

Uso:

    # 1. Supabase local levantado con migraciones aplicadas
    supabase start --workdir .

    # 2. Variable de entorno con DATABASE_URL local
    $env:DATABASE_URL = "postgresql+asyncpg://postgres:postgres@127.0.0.1:54322/postgres"

    # 3. Ejecutar
    python scripts/case_study_ferreteria.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Literal

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "apps" / "api"))

from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.domain.tax_engine.snapshot import build_snapshots  # noqa: E402
from src.routers.scenario import (  # noqa: E402
    Palancas,
    ScenarioRequest,
    ScenarioResultado,
    _apply_palancas,
    _carga,
    _load_topes,
    _validate_eligibility,
)

Regimen = Literal["14_a", "14_d_3", "14_d_8"]

# Hash del set de reglas/parámetros (build_snapshots) contra el que se
# validaron las cifras del doc del caso 01. `None` = sin fijar: la primera
# corrida imprime el hash actual. Fijar acá ese valor para que el script
# ABORTE si los placeholders/reglas cambian y las cifras del doc dejan de
# ser reproducibles (cierra finding 13: el safeguard existe de verdad).
EXPECTED_RULES_HASH: str | None = None


@dataclass(frozen=True)
class Perfil:
    nombre: str = "Ferretería barrio (caso 01)"
    tax_year: int = 2026
    rli_anual_clp: Decimal = Decimal("80000000")
    retiros_anuales_clp: Decimal = Decimal("48000000")
    planilla_anual_clp: Decimal = Decimal("72000000")
    # P1 — adquisición de activos fijos en año 1 (one-shot)
    dep_instantanea_anio_1: Decimal = Decimal("15000000")
    # P2 — gasto SENCE (= 1% planilla)
    sence_monto: Decimal = Decimal("720000")
    # P9 — intención de aporte APV del dueño. El motor lo capa al tope
    #      anual (600 UF × uf_valor_clp); el exceso dispara bandera P9.
    apv_monto_intencion: Decimal = Decimal("23568000")


# ---------------------------------------------------------------------------
# Motor real: un año = mismo path que POST /api/scenario/simulate
# ---------------------------------------------------------------------------


async def correr_anio(
    session: AsyncSession,
    *,
    regimen: Regimen,
    tax_year: int,
    rli: Decimal,
    retiros: Decimal,
    planilla: Decimal,
    palancas: Palancas,
) -> ScenarioResultado:
    """Corre un año por el motor real: _load_topes → _apply_palancas → _carga."""
    _validate_eligibility(regimen, palancas)
    topes = await _load_topes(session, tax_year)
    req = ScenarioRequest(
        regimen=regimen,
        tax_year=tax_year,
        rli_base=rli,
        retiros_base=retiros,
        planilla_anual_pesos=planilla,
        palancas=palancas,
    )
    aplicado = _apply_palancas(req, topes)
    regimen_efectivo = aplicado.regimen_override or regimen
    return await _carga(
        session,
        regimen=regimen_efectivo,
        tax_year=tax_year,
        rli=aplicado.rli_ajustada,
        retiros_total=aplicado.retiros_total,
        creditos_idpc=aplicado.creditos_idpc,
        deduccion_igc=aplicado.deduccion_igc,
    )


# ---------------------------------------------------------------------------
# Formato
# ---------------------------------------------------------------------------


def fmt_clp(v: Decimal) -> str:
    sign = "-" if v < 0 else " "
    abs_v = abs(v)
    return f"{sign}${abs_v:>16,.0f}".replace(",", ".")


def fmt_pct(v: Decimal) -> str:
    return f"{v * 100:>7.2f}%"


def imprimir_tabla(
    titulo: str, filas: list[tuple[int, Regimen, ScenarioResultado]]
) -> Decimal:
    total = sum((r.carga_total for _, _, r in filas), Decimal("0"))
    print()
    print(f"  {titulo}")
    print("  " + "─" * 78)
    print("  Año   Régimen      IDPC neto         IGC dueño      Carga año")
    for año, regimen, r in filas:
        print(
            f"  {año}  {regimen:<7}"
            f"  {fmt_clp(r.idpc)}"
            f"  {fmt_clp(r.igc_dueno)}"
            f"  {fmt_clp(r.carga_total)}"
        )
    print("  " + "─" * 78)
    print(f"  TOTAL 3 años                                              {fmt_clp(total)}")
    return total


# ---------------------------------------------------------------------------
# Escenarios (proyección a 3 años; el motor corre 1 año por request)
# ---------------------------------------------------------------------------


async def correr_status_quo(session: AsyncSession, perfil: Perfil) -> Decimal:
    filas = []
    for offset in range(3):
        año = perfil.tax_year + offset
        r = await correr_anio(
            session,
            regimen="14_a",
            tax_year=año,
            rli=perfil.rli_anual_clp,
            retiros=perfil.retiros_anuales_clp,
            planilla=perfil.planilla_anual_clp,
            palancas=Palancas(),
        )
        filas.append((año, "14_a", r))
    return imprimir_tabla("Status quo — 14 A sin palancas", filas)


async def correr_recomendacion_pura(
    session: AsyncSession, perfil: Perfil
) -> Decimal:
    filas = []
    for offset in range(3):
        año = perfil.tax_year + offset
        r = await correr_anio(
            session,
            regimen="14_d_3",
            tax_year=año,
            rli=perfil.rli_anual_clp,
            retiros=perfil.retiros_anuales_clp,
            planilla=perfil.planilla_anual_clp,
            palancas=Palancas(),
        )
        filas.append((año, "14_d_3", r))
    return imprimir_tabla(
        "Recomendación Renteo — 14 D N°3 puro (cambio régimen)", filas
    )


async def correr_con_palancas(
    session: AsyncSession, perfil: Perfil
) -> Decimal:
    """14 D N°3 + P1 (año 1) + P2 (todos los años) + P9 (todos los años).

    Se pasan los montos brutos de las palancas al motor; _apply_palancas
    aplica los topes (SENCE, APV) exactamente como en producción.
    """
    filas = []
    for offset in range(3):
        año = perfil.tax_year + offset
        palancas = Palancas(
            # P1 solo aplica en año 1 (one-shot por compra)
            dep_instantanea=(
                perfil.dep_instantanea_anio_1 if offset == 0 else None
            ),
            sence_monto=perfil.sence_monto,
            apv_monto=perfil.apv_monto_intencion,
        )
        r = await correr_anio(
            session,
            regimen="14_d_3",
            tax_year=año,
            rli=perfil.rli_anual_clp,
            retiros=perfil.retiros_anuales_clp,
            planilla=perfil.planilla_anual_clp,
            palancas=palancas,
        )
        filas.append((año, "14_d_3", r))

    # Detalle de topes aplicados en año base (informativo).
    topes = await _load_topes(session, perfil.tax_year)
    tope_sence = max(
        (perfil.planilla_anual_clp * topes.sence_pct_planilla).quantize(
            Decimal("0.01")
        ),
        topes.sence_tope_minimo_pesos,
    )
    print()
    print("  Palancas aplicadas (motor real, lista blanca)")
    print(
        f"    P1 dep_instantanea (año 1)      {fmt_clp(perfil.dep_instantanea_anio_1)}"
        "  · art. 31 N°5 bis LIR"
    )
    print(
        f"    P2 SENCE (tope {fmt_clp(tope_sence)})"
        f"  crédito: {fmt_clp(min(perfil.sence_monto, tope_sence))}"
        "  · Ley 19.518"
    )
    print(
        f"    P9 APV (tope {fmt_clp(topes.apv_tope_anual_pesos)})"
        f"  aporte: {fmt_clp(min(perfil.apv_monto_intencion, topes.apv_tope_anual_pesos))}"
        "  · art. 42 bis LIR"
    )
    return imprimir_tabla(
        "Recomendación Renteo — 14 D N°3 + P1·P2·P9", filas
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def main() -> None:
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise SystemExit(
            "DATABASE_URL no seteada. Ver docs/casos-estudio/README.md."
        )

    engine = create_async_engine(db_url, future=True)
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

    perfil = Perfil()

    print()
    print("=" * 80)
    print("  🟡 CASO DE ESTUDIO 01 — INSPECCIÓN INTERNA SANDBOX")
    print(f"  Perfil: {perfil.nombre}")
    print(f"  AT {perfil.tax_year} · RLI ${perfil.rli_anual_clp:,.0f}".replace(",", "."))
    print(f"  Retiros ${perfil.retiros_anuales_clp:,.0f}".replace(",", "."))
    print(f"  Planilla ${perfil.planilla_anual_clp:,.0f}".replace(",", "."))
    print("=" * 80)
    print()
    print(
        "  Cifras sobre seeds PLACEHOLDER firma contador socio "
        "pendiente."
    )
    print("  No es asesoría tributaria. Disclaimer: skill 2.")

    async with SessionLocal() as session:
        # Reproducibilidad: hash del set de reglas/parámetros vigente.
        _, _, rules_hash = await build_snapshots(
            session, tax_year=perfil.tax_year
        )
        print()
        print(f"  rules_snapshot_hash AT{perfil.tax_year} = {rules_hash}")
        if EXPECTED_RULES_HASH is None:
            print(
                "  ⚠️  EXPECTED_RULES_HASH sin fijar. Si estas cifras se "
                "publican en el doc, fijar este hash en el script."
            )
        elif rules_hash != EXPECTED_RULES_HASH:
            await engine.dispose()
            raise SystemExit(
                "Los placeholders/reglas cambiaron (hash distinto de "
                "EXPECTED_RULES_HASH). Las cifras del caso 01 dejaron de "
                "ser reproducibles: re-revisar "
                "docs/casos-estudio/01-ferreteria-pyme-mvp.md."
            )

        total_status_quo = await correr_status_quo(session, perfil)
        total_recomendacion = await correr_recomendacion_pura(session, perfil)
        total_palancas = await correr_con_palancas(session, perfil)

    await engine.dispose()

    ahorro_regimen = total_status_quo - total_recomendacion
    ahorro_palancas = total_recomendacion - total_palancas
    ahorro_total = total_status_quo - total_palancas
    pct_total = (ahorro_total / total_status_quo) if total_status_quo > 0 else Decimal("0")

    print()
    print("  Comparador final — beneficio Renteo")
    print("  " + "─" * 78)
    print(
        f"  Status quo (14 A)                                  {fmt_clp(total_status_quo)}"
    )
    print(
        f"  Renteo cambio régimen (14 D N°3)                   {fmt_clp(total_recomendacion)}"
        f"   Δ {fmt_clp(-ahorro_regimen)}"
    )
    print(
        f"  Renteo + palancas P1·P2·P9                         {fmt_clp(total_palancas)}"
        f"   Δ {fmt_clp(-ahorro_palancas)}"
    )
    print("  " + "─" * 78)
    print(
        f"  Ahorro total 3 años Renteo                         {fmt_clp(ahorro_total)}"
        f"   ({fmt_pct(pct_total)})"
    )
    print()
    print("  🟡 Sensibilidad: si se rompe la condicionalidad Ley 21.735 art. 4° t.,")
    print("     el IDPC 14 D N°3 revierte de 12,5% a 25% (feature flag")
    print("     idpc_14d3_revertida_rate) y el ahorro cae a ~$4,8M en 3 años.")
    print()


if __name__ == "__main__":
    asyncio.run(main())
