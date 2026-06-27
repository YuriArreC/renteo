"""Caso de estudio 01 — Ferretería PYME MVP.

Reproduce el comparador del documento
`docs/casos-estudio/01-ferreteria-pyme-mvp.md` llamando al motor
tributario real (`compute_idpc`, `compute_igc`, `get_beneficio`)
sobre las seeds placeholder cargadas en Supabase local.

🟡 INSPECCIÓN INTERNA — no es asesoría tributaria. Mientras los
goldens estén en xfail y los placeholders sin firma, los outputs
de este script son preliminares.

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

from src.domain.tax_engine.beneficios import get_beneficio  # noqa: E402
from src.domain.tax_engine.idpc import compute_idpc  # noqa: E402
from src.domain.tax_engine.igc import compute_igc  # noqa: E402

Regimen = Literal["14_a", "14_d_3", "14_d_8"]


@dataclass(frozen=True)
class Perfil:
    nombre: str = "Ferretería barrio (caso 01)"
    tax_year: int = 2026
    regimen_actual: Regimen = "14_a"
    rli_anual_clp: Decimal = Decimal("80000000")
    retiros_anuales_clp: Decimal = Decimal("48000000")
    planilla_anual_clp: Decimal = Decimal("72000000")
    # P1 — adquisición de activos fijos en año 1 (one-shot)
    dep_instantanea_anio_1: Decimal = Decimal("15000000")
    # P2 — gasto SENCE (= 1% planilla)
    sence_monto: Decimal = Decimal("720000")
    # P9 — APV anual (cap a tope 600 UF AT 2026 desde DB)
    apv_monto_intencion: Decimal = Decimal("23568000")


@dataclass(frozen=True)
class ResultadoAnual:
    año: int
    regimen: Regimen
    rli: Decimal
    idpc_bruto: Decimal
    creditos_idpc: Decimal
    idpc_neto: Decimal
    base_igc: Decimal
    igc: Decimal

    @property
    def carga_total(self) -> Decimal:
        return self.idpc_neto + self.igc


async def calcular_anual(
    session: AsyncSession,
    *,
    regimen: Regimen,
    tax_year: int,
    rli: Decimal,
    retiros: Decimal,
    creditos_idpc: Decimal = Decimal("0"),
    deduccion_igc: Decimal = Decimal("0"),
) -> ResultadoAnual:
    """Replica scenario._carga sin importar el privado del router."""
    idpc_bruto = await compute_idpc(
        session, regimen=regimen, tax_year=tax_year, rli=rli
    )
    idpc_neto = max(Decimal("0"), idpc_bruto - creditos_idpc)
    base_igc_full = rli if regimen == "14_d_8" else retiros
    base_igc = max(Decimal("0"), base_igc_full - deduccion_igc)
    igc = await compute_igc(session, tax_year=tax_year, base_pesos=base_igc)
    return ResultadoAnual(
        año=tax_year,
        regimen=regimen,
        rli=rli,
        idpc_bruto=idpc_bruto,
        creditos_idpc=creditos_idpc,
        idpc_neto=idpc_neto,
        base_igc=base_igc,
        igc=igc,
    )


async def tope_sence_clp(
    session: AsyncSession, *, tax_year: int, planilla: Decimal
) -> Decimal:
    """Tope SENCE = max(1% planilla, 9 UTM). Mismo cálculo que _apply_palancas."""
    pct_planilla = await get_beneficio(
        session, key="sence_porcentaje_planilla", tax_year=tax_year
    )
    tope_minimo_utm = await get_beneficio(
        session, key="sence_tope_minimo_utm", tax_year=tax_year
    )
    utm = await get_beneficio(
        session, key="utm_valor_clp", tax_year=tax_year
    )
    return max((pct_planilla * planilla).quantize(Decimal("0.01")), tope_minimo_utm * utm)


async def tope_apv_clp(
    session: AsyncSession, *, tax_year: int
) -> Decimal:
    uf = await get_beneficio(
        session, key="uf_valor_clp", tax_year=tax_year
    )
    apv_uf = await get_beneficio(
        session, key="apv_tope_anual_uf", tax_year=tax_year
    )
    return apv_uf * uf


def fmt_clp(v: Decimal) -> str:
    sign = "-" if v < 0 else " "
    abs_v = abs(v)
    return f"{sign}${abs_v:>16,.0f}".replace(",", ".")


def fmt_pct(v: Decimal) -> str:
    return f"{v * 100:>7.2f}%"


def imprimir_tabla(
    titulo: str, filas: list[ResultadoAnual]
) -> Decimal:
    total = sum((r.carga_total for r in filas), Decimal("0"))
    print()
    print(f"  {titulo}")
    print("  " + "─" * 78)
    print(
        "  Año   Régimen  "
        "    IDPC neto         IGC dueño      "
        "Carga año"
    )
    for r in filas:
        print(
            f"  {r.año}  {r.regimen:<7}"
            f"  {fmt_clp(r.idpc_neto)}"
            f"  {fmt_clp(r.igc)}"
            f"  {fmt_clp(r.carga_total)}"
        )
    print("  " + "─" * 78)
    print(f"  TOTAL 3 años                                              {fmt_clp(total)}")
    return total


async def correr_status_quo(
    session: AsyncSession, perfil: Perfil
) -> Decimal:
    filas: list[ResultadoAnual] = []
    for offset in range(3):
        año = perfil.tax_year + offset
        r = await calcular_anual(
            session,
            regimen="14_a",
            tax_year=año,
            rli=perfil.rli_anual_clp,
            retiros=perfil.retiros_anuales_clp,
        )
        filas.append(r)
    return imprimir_tabla("Status quo — 14 A sin palancas", filas)


async def correr_recomendacion_pura(
    session: AsyncSession, perfil: Perfil
) -> Decimal:
    filas: list[ResultadoAnual] = []
    for offset in range(3):
        año = perfil.tax_year + offset
        r = await calcular_anual(
            session,
            regimen="14_d_3",
            tax_year=año,
            rli=perfil.rli_anual_clp,
            retiros=perfil.retiros_anuales_clp,
        )
        filas.append(r)
    return imprimir_tabla(
        "Recomendación Renteo — 14 D N°3 puro (cambio régimen)", filas
    )


async def correr_con_palancas(
    session: AsyncSession, perfil: Perfil
) -> Decimal:
    """14 D N°3 + P1 (año 1) + P2 (todos los años) + P9 (todos los años)."""
    tope_sence = await tope_sence_clp(
        session,
        tax_year=perfil.tax_year,
        planilla=perfil.planilla_anual_clp,
    )
    sence_credito = min(perfil.sence_monto, tope_sence)

    tope_apv = await tope_apv_clp(session, tax_year=perfil.tax_year)
    apv_aplicado = min(perfil.apv_monto_intencion, tope_apv)

    filas: list[ResultadoAnual] = []
    for offset in range(3):
        año = perfil.tax_year + offset
        # P1 solo aplica en año 1 (one-shot por compra)
        dep = perfil.dep_instantanea_anio_1 if offset == 0 else Decimal("0")
        rli_ajustada = max(Decimal("0"), perfil.rli_anual_clp - dep)

        r = await calcular_anual(
            session,
            regimen="14_d_3",
            tax_year=año,
            rli=rli_ajustada,
            retiros=perfil.retiros_anuales_clp,
            creditos_idpc=sence_credito,
            deduccion_igc=apv_aplicado,
        )
        filas.append(r)

    print()
    print("  Palancas aplicadas (lista blanca v1)")
    print(
        f"    P1 dep_instantanea (año 1)      {fmt_clp(perfil.dep_instantanea_anio_1)}"
        "  · art. 31 N°5 bis LIR"
    )
    print(
        f"    P2 SENCE (tope {fmt_clp(tope_sence)})"
        f"  crédito: {fmt_clp(sence_credito)}"
        "  · Ley 19.518"
    )
    print(
        f"    P9 APV (tope {fmt_clp(tope_apv)})"
        f"  aporte: {fmt_clp(apv_aplicado)}"
        "  · art. 42 bis LIR"
    )
    return imprimir_tabla(
        "Recomendación Renteo — 14 D N°3 + P1·P2·P9", filas
    )


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
    print("  🟡 Bandera: tasa 12,5% queda condicionada a Ley 21.735 art. 4° t.")
    print("     Si se rompe condicionalidad, IDPC revierte a 25% y ahorro cae a ~$5M.")
    print()


if __name__ == "__main__":
    asyncio.run(main())
