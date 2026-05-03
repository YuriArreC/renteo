"""Motor de elegibilidad por régimen tributario (skill 7).

Cada función retorna `(elegible, requisitos)`:

- `elegible: bool`
- `requisitos: list[Requisito]` — texto humano + estado (`ok`) por
  cada condición evaluada. Permite mostrar una tabla "✓ / ✗" en la UI
  con el detalle de qué se cumplió y qué no.

Los umbrales en UF (ingresos promedio, ingresos pico anual, capital
inicial, % pasivos máximo, % participación, topes renta presunta)
viven en constantes locales porque son **cualitativos** del régimen
— no son tasas, tramos ni topes monetarios sujetos a cambio
paramétrico anual. Si la ley los modifica, se publica nueva versión
del módulo (track 11 los subirá a un rule_set declarativo). Este
módulo evalúa estructura, no calcula impuestos.

Fundamento legal:
- LIR arts. 14 A, 14 D N°3, 14 D N°8, 34.
- Ley 21.210 (estructura de regímenes).
- Ley 21.713 (modificaciones recientes).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

# Umbrales estructurales 14 D (art. 14 D LIR; track 11 los lleva a rule_set):
_UMBRAL_INGRESOS_PROMEDIO_UF = Decimal("75000")  # tax-magic-number-allow
_UMBRAL_INGRESOS_MAX_ANUAL_UF = Decimal("85000")  # tax-magic-number-allow
_UMBRAL_CAPITAL_INICIAL_UF = Decimal("85000")  # tax-magic-number-allow
_UMBRAL_PCT_PASIVOS_MAX = Decimal("0.35")

# Topes estructurales renta presunta (art. 34 LIR):
_TOPE_RP_AGRICOLA_UF = Decimal("9000")
_TOPE_RP_TRANSPORTE_UF = Decimal("5000")  # tax-magic-number-allow
_TOPE_RP_MINERIA_UF = Decimal("17000")


@dataclass(frozen=True)
class Requisito:
    texto: str
    ok: bool
    fundamento: str


@dataclass(frozen=True)
class EligibilityInputs:
    """Subset normalizado del wizard usado por la elegibilidad.

    Las entradas del wizard se traducen a este dataclass en el router;
    así las funciones de elegibilidad son testeables sin FastAPI.
    """

    ingresos_promedio_3a_uf: Decimal
    ingresos_max_anual_uf: Decimal
    capital_efectivo_inicial_uf: Decimal
    pct_ingresos_pasivos: Decimal
    todos_duenos_personas_naturales_chile: bool
    participacion_empresas_no_14d_sobre_10pct: bool
    sector: str  # comercio, servicios, agricola, transporte, mineria, otro
    ventas_anuales_uf: Decimal


def evaluar_14_a(_inputs: EligibilityInputs) -> tuple[bool, list[Requisito]]:
    """14 A es el régimen general supletorio: siempre elegible.

    Fundamento: art. 14 A LIR.
    """
    return True, [
        Requisito(
            texto="Régimen general supletorio: aplica por defecto.",
            ok=True,
            fundamento="art. 14 A LIR",
        )
    ]


def evaluar_14_d_3(
    inputs: EligibilityInputs,
) -> tuple[bool, list[Requisito]]:
    """Pro PyME General: cinco condiciones cumulativas (art. 14 D N°3 LIR).

    No incluye chequeo de 'sin observaciones SII' ni de fusión / división
    activa — eso se modela como bandera en el router para no mezclar
    elegibilidad estructural con estado operativo de la empresa.
    """
    fund = "art. 14 D N°3 LIR; Ley 21.210"

    requisitos = [
        Requisito(
            texto=(
                "Promedio de ingresos del giro últimos 3 años "
                f"≤ {_UMBRAL_INGRESOS_PROMEDIO_UF:.0f} UF"
            ),
            ok=inputs.ingresos_promedio_3a_uf
            <= _UMBRAL_INGRESOS_PROMEDIO_UF,
            fundamento=fund,
        ),
        Requisito(
            texto=(
                "Ningún año individual supera "
                f"{_UMBRAL_INGRESOS_MAX_ANUAL_UF:.0f} UF "
                "en los últimos 3 años"
            ),
            ok=inputs.ingresos_max_anual_uf
            <= _UMBRAL_INGRESOS_MAX_ANUAL_UF,
            fundamento=fund,
        ),
        Requisito(
            texto=(
                "Capital efectivo inicial ≤ "
                f"{_UMBRAL_CAPITAL_INICIAL_UF:.0f} UF "
                "(empresas en inicio de actividades)"
            ),
            ok=inputs.capital_efectivo_inicial_uf
            <= _UMBRAL_CAPITAL_INICIAL_UF,
            fundamento=fund,
        ),
        Requisito(
            texto=(
                "Ingresos pasivos no superan "
                f"{_UMBRAL_PCT_PASIVOS_MAX * 100:.0f}% del total"
            ),
            ok=inputs.pct_ingresos_pasivos <= _UMBRAL_PCT_PASIVOS_MAX,
            fundamento=fund,
        ),
        Requisito(
            texto=(
                "No participa por más del 10% en empresas no acogidas "
                "a 14 D"
            ),
            ok=not inputs.participacion_empresas_no_14d_sobre_10pct,
            fundamento=fund,
        ),
    ]
    return all(r.ok for r in requisitos), requisitos


def evaluar_14_d_8(
    inputs: EligibilityInputs,
) -> tuple[bool, list[Requisito]]:
    """Pro PyME Transparente: requisitos de 14 D N°3 + dueños chilenos.

    Fundamento: art. 14 D N°8 LIR.
    """
    base_ok, base_reqs = evaluar_14_d_3(inputs)

    extra = Requisito(
        texto=(
            "Todos los dueños son personas naturales con domicilio o "
            "residencia en Chile (o sin domicilio en Chile, sujetos a "
            "Adicional)"
        ),
        ok=inputs.todos_duenos_personas_naturales_chile,
        fundamento="art. 14 D N°8 LIR",
    )

    requisitos = [*base_reqs, extra]
    return base_ok and extra.ok, requisitos


def evaluar_renta_presunta(
    inputs: EligibilityInputs,
) -> tuple[bool, list[Requisito]]:
    """Renta presunta (art. 34 LIR) — orientativo, sin proyección.

    Solo se sugiere si la empresa opera en sector elegible y respeta
    el tope de ventas anuales correspondiente. La elección final
    requiere validación de contador (capital propio inicial,
    participación en otras sociedades, etc.).
    """
    sector = inputs.sector.lower()
    ventas = inputs.ventas_anuales_uf
    fund = "art. 34 LIR"

    if sector == "agricola":
        ok = ventas <= _TOPE_RP_AGRICOLA_UF
        return ok, [
            Requisito(
                texto=(
                    "Sector agrícola: ventas anuales ≤ "
                    f"{_TOPE_RP_AGRICOLA_UF:.0f} UF"
                ),
                ok=ok,
                fundamento=fund,
            )
        ]
    if sector == "transporte":
        ok = ventas <= _TOPE_RP_TRANSPORTE_UF
        return ok, [
            Requisito(
                texto=(
                    "Transporte terrestre de carga: ventas anuales ≤ "
                    f"{_TOPE_RP_TRANSPORTE_UF:.0f} UF"
                ),
                ok=ok,
                fundamento=fund,
            )
        ]
    if sector == "mineria":
        ok = ventas <= _TOPE_RP_MINERIA_UF
        return ok, [
            Requisito(
                texto=(
                    "Minería: ventas anuales ≤ "
                    f"{_TOPE_RP_MINERIA_UF:.0f} UF"
                ),
                ok=ok,
                fundamento=fund,
            )
        ]

    return False, [
        Requisito(
            texto=(
                "Renta presunta solo aplica a sectores agrícola, "
                "transporte terrestre de carga o minería."
            ),
            ok=False,
            fundamento=fund,
        )
    ]
