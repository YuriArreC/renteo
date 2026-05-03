"""Motor de elegibilidad por régimen tributario (skill 7 + skill 11).

Cada función `evaluar_<regimen>` consulta la regla declarativa
publicada en `tax_rules.rule_sets` para el `tax_year` dado, evalúa
el contexto del contribuyente con el `rule_evaluator` (sin eval, sin
lambdas, set finito de operadores) y mapea el resultado a una lista
de `Requisito` con texto humano + estado + fundamento legal — el
mismo shape que consume el router del wizard.

Track 7 introdujo umbrales como constantes locales (P1); track 11 los
saca a `tax_rules` con vigencia temporal y doble firma.

Si la regla no está publicada para el año pedido, `resolve_rule` lanza
`MissingRuleError` y el endpoint la traduce a 503: el motor jamás
calcula sin regla vigente.

Fundamento legal por dominio:
- LIR arts. 14 A, 14 D N°3, 14 D N°8, 34.
- Ley 21.210, Ley 21.713 (estructura y modificaciones recientes).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.tax_engine.rule_evaluator import EvaluationResult, evaluate
from src.domain.tax_engine.rule_resolver import resolve_rule


@dataclass(frozen=True)
class Requisito:
    texto: str
    ok: bool
    fundamento: str


@dataclass(frozen=True)
class EligibilityInputs:
    """Contexto del contribuyente que el evaluador consume."""

    ingresos_promedio_3a_uf: Decimal
    ingresos_max_anual_uf: Decimal
    capital_efectivo_inicial_uf: Decimal
    pct_ingresos_pasivos: Decimal
    todos_duenos_personas_naturales_chile: bool
    participacion_empresas_no_14d_sobre_10pct: bool
    sector: str
    ventas_anuales_uf: Decimal


def _to_ctx(inputs: EligibilityInputs) -> dict[str, object]:
    """Normaliza el dataclass a dict para el evaluador.

    Decimal se convierte a float porque el evaluador compara con
    literales JSON (que llegan como int/float). La conversión es
    determinista para los rangos en juego (≤ 100.000 UF).
    """
    return {
        "ingresos_promedio_3a_uf": float(inputs.ingresos_promedio_3a_uf),
        "ingresos_max_anual_uf": float(inputs.ingresos_max_anual_uf),
        "capital_efectivo_inicial_uf": float(
            inputs.capital_efectivo_inicial_uf
        ),
        "pct_ingresos_pasivos": float(inputs.pct_ingresos_pasivos),
        "todos_duenos_personas_naturales_chile": (
            inputs.todos_duenos_personas_naturales_chile
        ),
        "participacion_empresas_no_14d_sobre_10pct": (
            inputs.participacion_empresas_no_14d_sobre_10pct
        ),
        "sector": inputs.sector,
        "ventas_anuales_uf": float(inputs.ventas_anuales_uf),
        # 14 A es supletorio: el contexto siempre viaja con `supletorio=True`.
        "supletorio": True,
    }


def _result_to_requisitos(
    rule: dict[str, object], result: EvaluationResult
) -> list[Requisito]:
    """Convierte cláusulas declarativas en `Requisito` para la UI.

    Recorremos las cláusulas raíz (`all_of` / `any_of`) y emitimos un
    `Requisito` por cada predicado simple. Si el predicado falló según
    `result.failed_clauses`, marcamos `ok=False` y mostramos el
    `message` declarado; si pasó, mostramos un texto positivo derivado
    del `fundamento`.
    """
    failed_keys = {
        (fc.field, fc.op) for fc in result.failed_clauses
    }
    requisitos: list[Requisito] = []
    for clause in _flatten_predicates(rule):
        field = clause.get("field")
        op = clause.get("op")
        ok = (field, op) not in failed_keys
        message = str(clause.get("message") or "Requisito cumplido.")
        fundamento = str(clause.get("fundamento") or "")
        texto = (
            message
            if not ok
            else _positive_text_for(field, op, clause.get("value"))
        )
        requisitos.append(
            Requisito(texto=texto, ok=ok, fundamento=fundamento)
        )
    return requisitos


def _flatten_predicates(clause: object) -> list[dict[str, object]]:
    """Devuelve la lista de predicados simples bajo una cláusula raíz.

    Un `all_of` se aplana en sus hijos directos; un `any_of` también
    (cada rama es un predicado o un `all_of` interno cuyas cláusulas
    se aplanan recursivamente). El `not` no se utiliza por ahora en
    `regime_eligibility`, pero se respeta si aparece.
    """
    if not isinstance(clause, dict):
        return []
    if "all_of" in clause:
        items: list[dict[str, object]] = []
        for sub in clause["all_of"]:
            items.extend(_flatten_predicates(sub))
        return items
    if "any_of" in clause:
        items = []
        for sub in clause["any_of"]:
            items.extend(_flatten_predicates(sub))
        return items
    if "not" in clause:
        return _flatten_predicates(clause["not"])
    if "field" in clause and "op" in clause:
        return [clause]
    return []


_OP_HUMAN: dict[str, str] = {
    "lte": "≤",
    "lt": "<",
    "gte": "≥",
    "gt": ">",
    "eq": "=",
    "neq": "≠",
}


def _positive_text_for(
    field: object, op: object, value: object
) -> str:
    """Texto cuando el requisito se cumple — derivado del predicado."""
    if not isinstance(field, str) or not isinstance(op, str):
        return "Requisito cumplido."
    symbol = _OP_HUMAN.get(op, op)
    return f"{field} {symbol} {value} ✓"


async def _evaluate_rule(
    session: AsyncSession,
    *,
    key: str,
    tax_year: int,
    ctx: dict[str, object],
) -> tuple[bool, list[Requisito]]:
    rule_set = await resolve_rule(
        session, "regime_eligibility", key, tax_year
    )
    result = evaluate(rule_set.rules, ctx)
    return result.passed, _result_to_requisitos(rule_set.rules, result)


async def evaluar_14_a(
    session: AsyncSession, inputs: EligibilityInputs, tax_year: int
) -> tuple[bool, list[Requisito]]:
    return await _evaluate_rule(
        session, key="14_a", tax_year=tax_year, ctx=_to_ctx(inputs)
    )


async def evaluar_14_d_3(
    session: AsyncSession, inputs: EligibilityInputs, tax_year: int
) -> tuple[bool, list[Requisito]]:
    return await _evaluate_rule(
        session, key="14_d_3", tax_year=tax_year, ctx=_to_ctx(inputs)
    )


async def evaluar_14_d_8(
    session: AsyncSession, inputs: EligibilityInputs, tax_year: int
) -> tuple[bool, list[Requisito]]:
    return await _evaluate_rule(
        session, key="14_d_8", tax_year=tax_year, ctx=_to_ctx(inputs)
    )


async def evaluar_renta_presunta(
    session: AsyncSession, inputs: EligibilityInputs, tax_year: int
) -> tuple[bool, list[Requisito]]:
    return await _evaluate_rule(
        session,
        key="renta_presunta",
        tax_year=tax_year,
        ctx=_to_ctx(inputs),
    )
