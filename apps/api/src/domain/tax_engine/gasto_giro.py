"""Banderas del optimizador de gasto del giro (skill 1 + skill 11).

Este módulo implementa **solo la mitad bloqueante** del optimizador de gasto
asociado al giro (art. 31 LIR): evalúa un gasto candidato y devuelve las
banderas que le aplican. **No sugiere gastos, no aplica palancas y no calcula
impuestos.** La mitad que sugiere (catálogo por rubro + agente) espera la firma
del CONTADOR_SOCIO — ver `docs/optimizadores/01-gasto-del-giro.md` §6.

Se construyó primero lo que dice "no" y después lo que dice "sí" por una razón
concreta: el **art. 100 bis CT** (texto vigente tras las Leyes 21.713 y 21.755)
sanciona a **quien diseña o planifica** con **100 a 250 UTA**, y la exención del
art. 14 letra D **ampara al contribuyente, no al asesor**. Renteo es,
funcionalmente, un diseñador. Estas banderas son la mitigación de un riesgo
propio, no higiene de producto.

Contrato de evaluación (ojo — se invierte respecto de `eligibility.py`):

    eligibility:  evaluate(...).passed == True  →  el requisito SE CUMPLE  ✅
    red_flag:     evaluate(...).passed == True  →  la condición SE CUMPLE  🚩
                                                   ⇒ la bandera SE LEVANTA

Es decir: en una bandera roja, `passed=True` es la **mala** noticia. Cualquier
refactor que "normalice" ambos dominios al mismo signo invierte los guardrails
en silencio. Los tests de `tests/unit/test_gasto_giro_guardrails.py` fijan esta
semántica.

Las condiciones NO viven acá: viven como reglas declarativas versionadas en
`tax_rules.rule_sets` bajo el dominio `red_flag`, una key por bandera. Publicar
una bandera nueva es un INSERT con doble firma, no un release de código
(skill 11). Este módulo solo sabe evaluarlas.

Fundamento legal de las banderas (detalle por bandera en la migración
`20260713120000_red_flags_gasto_giro.sql`):
- art. 31 inc. 1° LIR — automóviles, station wagons y similares (la prohibición
  **incluye el leasing**, Circular SII N°53 de 2020).
- art. 31 incs. 2° y 3°, N°4 y N°12 LIR — gastos en el extranjero y partes
  relacionadas.
- art. 31 inciso final LIR — transacciones y cláusulas penales entre
  relacionados **no son gasto**.
- art. 14 D N°3 LIR; Circular SII N°62 de 2020 — base caja: el egreso se
  reconoce al **pagarse**.
- art. 21 LIR — gasto rechazado.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict, dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.tax_engine.rule_evaluator import evaluate
from src.domain.tax_engine.rule_resolver import RuleSet, resolve_domain_rules
from src.lib.errors import InvalidRuleError, RedFlagBlocked

RED_FLAG_DOMAIN = "red_flag"

SEVERIDAD_BLOCK = "block"
SEVERIDAD_WARN = "warn"
SEVERIDADES = frozenset({SEVERIDAD_BLOCK, SEVERIDAD_WARN})


@dataclass(frozen=True)
class Bandera:
    """Una bandera levantada sobre un gasto concreto."""

    id: str
    severidad: str
    mensaje: str
    fundamento: str

    @property
    def bloquea(self) -> bool:
        return self.severidad == SEVERIDAD_BLOCK


@dataclass(frozen=True)
class GastoGiroInputs:
    """Contexto de UN gasto candidato.

    Todos los campos son obligatorios **a propósito**. El evaluador resuelve
    un campo ausente como `None`, y `None == False` es `False`: una bandera de
    bloqueo cuya condición mira un campo que el contexto no trae **no se
    levantaría nunca**. Un default silencioso sería, literalmente, un guardrail
    apagado. Si el llamador no sabe el valor, debe decidirlo explícitamente —
    no omitirlo.

    El test `test_toda_field_de_las_banderas_existe_en_el_contexto` fija esta
    invariante contra las banderas realmente seedeadas.
    """

    # Nexo con el giro (art. 31 inc. 1°)
    categoria: str
    nexo_giro_declarado: bool
    es_personal: bool

    # Vehículos (art. 31 inc. 1°)
    es_vehiculo_automovil: bool
    giro_habitual_vehiculos: bool
    via_leasing: bool
    tiene_resolucion_director: bool

    # Documentación (art. 31 inc. 1°; art. 23 DL 825)
    tiene_documento_tributario: bool

    # Partes relacionadas (art. 31 incs. 3° y final, N°4 y N°12)
    tipo_desembolso: str
    contraparte_relacionada: bool
    ia_declarado_y_pagado: bool
    exento_o_no_gravado_ia: bool

    # Gastos en el extranjero (art. 31 inc. 2°)
    es_gasto_extranjero: bool
    doc_extranjero_datos_completos: bool

    # Régimen y timing (art. 14 D N°3; Circular SII N°62/2020)
    regimen: str
    pagado: bool

    # Conducta (lista negra, skill 1)
    fraccionado_para_umbral: bool


def _to_ctx(gasto: GastoGiroInputs) -> dict[str, Any]:
    """Normaliza el dataclass a dict plano para el evaluador."""
    return asdict(gasto)


def _parse_bandera(rule_set: RuleSet) -> tuple[Bandera, dict[str, Any]]:
    """Extrae (bandera, condición) de un rule_set del dominio `red_flag`.

    Valida el shape acá y no en el evaluador porque una bandera mal formada es
    un problema de *publicación* (regla inválida), no de *evaluación*. Falla
    ruidosamente: una bandera que no se puede parsear no se puede ignorar — si
    era de bloqueo, ignorarla es exactamente el fallo que no podemos permitir.
    """
    rules = rule_set.rules
    faltantes = [
        campo
        for campo in ("id", "severidad", "condicion", "mensaje", "fundamento")
        if campo not in rules
    ]
    if faltantes:
        raise InvalidRuleError(
            f"red_flag {rule_set.key!r} incompleta: faltan {sorted(faltantes)}"
        )

    severidad = str(rules["severidad"])
    if severidad not in SEVERIDADES:
        raise InvalidRuleError(
            f"red_flag {rule_set.key!r}: severidad {severidad!r} no soportada "
            f"(esperada una de {sorted(SEVERIDADES)})"
        )

    condicion = rules["condicion"]
    if not isinstance(condicion, dict):
        raise InvalidRuleError(
            f"red_flag {rule_set.key!r}: `condicion` debe ser un objeto"
        )

    bandera = Bandera(
        id=str(rules["id"]),
        severidad=severidad,
        mensaje=str(rules["mensaje"]),
        fundamento=str(rules["fundamento"]),
    )
    return bandera, condicion


def evaluar_banderas(
    rule_sets: Sequence[RuleSet], gasto: GastoGiroInputs
) -> list[Bandera]:
    """Evalúa las banderas publicadas contra un gasto. Función pura.

    Una bandera se levanta cuando su `condicion` **se cumple** (ver el contrato
    invertido en el docstring del módulo).

    Orden de salida: primero los bloqueos, luego los avisos; dentro de cada
    grupo, el orden de publicación. La UI muestra lo que detiene el gasto antes
    que lo que solo lo condiciona.
    """
    ctx = _to_ctx(gasto)
    levantadas: list[Bandera] = []
    for rule_set in rule_sets:
        bandera, condicion = _parse_bandera(rule_set)
        if evaluate(condicion, ctx).passed:
            levantadas.append(bandera)

    return sorted(levantadas, key=lambda b: not b.bloquea)


def bloqueado(banderas: Sequence[Bandera]) -> bool:
    return any(b.bloquea for b in banderas)


def assert_sin_bloqueo(banderas: Sequence[Bandera]) -> None:
    """Lanza `RedFlagBlocked` si alguna bandera bloquea.

    `RedFlagBlocked` ya está mapeada a HTTP 422 en el handler global
    (`main.py`), con code `red_flag_blocked`.
    """
    bloqueos = [b for b in banderas if b.bloquea]
    if not bloqueos:
        return
    detalle = "; ".join(f"{b.id}: {b.mensaje} ({b.fundamento})" for b in bloqueos)
    raise RedFlagBlocked(detalle)


async def evaluar_gasto_giro(
    session: AsyncSession,
    gasto: GastoGiroInputs,
    tax_year: int,
) -> list[Bandera]:
    """Resuelve las banderas vigentes para `tax_year` y las evalúa.

    Un dominio `red_flag` vacío devuelve `[]` (nada que bloquear) en vez de
    lanzar: cero banderas publicadas es un estado legítimo del sandbox. El
    llamador que exija banderas activas debe verificarlo — hoy no hay ninguno,
    porque la palanca `optimizacion_gastos_giro` **todavía no está en la lista
    blanca** y por tanto nada consume esto en producción.
    """
    rule_sets = await resolve_domain_rules(session, RED_FLAG_DOMAIN, tax_year)
    return evaluar_banderas(rule_sets, gasto)
