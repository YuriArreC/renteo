"""Evaluador de reglas declarativas — sin eval, sin lambdas, sin código arbitrario.

Solo se admite el set finito de operadores y combinadores de skill 11. Cualquier
operador desconocido lanza UnsupportedOperatorError; cualquier shape de cláusula
no reconocido lanza InvalidRuleError. Esto hace al evaluador seguro contra
inyección de reglas y testeable de forma exhaustiva.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from src.lib.errors import InvalidRuleError, UnsupportedOperatorError

SUPPORTED_OPERATORS: frozenset[str] = frozenset(
    {
        "eq",
        "neq",
        "lt",
        "lte",
        "gt",
        "gte",
        "between",
        "in",
        "not_in",
        "exists",
        "not_exists",
        "matches_regex",
    }
)

SUPPORTED_COMBINATORS: frozenset[str] = frozenset({"all_of", "any_of", "not"})


@dataclass(frozen=True)
class FailedClause:
    field: str | None
    op: str | None
    value: Any
    message: str | None
    fundamento: str | None


@dataclass(frozen=True)
class EvaluationResult:
    passed: bool
    failed_clauses: tuple[FailedClause, ...]


def evaluate(rule: dict[str, Any], ctx: dict[str, Any]) -> EvaluationResult:
    """Evalúa una cláusula raíz contra un contexto y reporta razones de fallo."""
    failed: list[FailedClause] = []
    passed = _eval_clause(rule, ctx, failed)
    return EvaluationResult(passed=passed, failed_clauses=tuple(failed))


def _eval_clause(
    clause: Any, ctx: dict[str, Any], failed: list[FailedClause]
) -> bool:
    if not isinstance(clause, dict):
        raise InvalidRuleError(f"clause must be an object, got {type(clause).__name__}")

    if "all_of" in clause:
        items = clause["all_of"]
        _require_list(items, "all_of")
        ok = True
        for sub in items:
            if not _eval_clause(sub, ctx, failed):
                ok = False
        return ok

    if "any_of" in clause:
        items = clause["any_of"]
        _require_list(items, "any_of")
        local: list[FailedClause] = []
        for sub in items:
            if _eval_clause(sub, ctx, local):
                return True
        failed.extend(local)
        return False

    if "not" in clause:
        # `not` invierte el resultado; los failures internos no se propagan.
        local: list[FailedClause] = []
        return not _eval_clause(clause["not"], ctx, local)

    if "field" in clause and "op" in clause:
        return _eval_predicate(clause, ctx, failed)

    raise InvalidRuleError(f"unrecognized clause shape: keys={sorted(clause)}")


def _require_list(value: Any, label: str) -> None:
    if not isinstance(value, list) or len(value) == 0:
        raise InvalidRuleError(f"{label} requires a non-empty list of clauses")


def _eval_predicate(
    clause: dict[str, Any], ctx: dict[str, Any], failed: list[FailedClause]
) -> bool:
    op = clause["op"]
    if op not in SUPPORTED_OPERATORS:
        raise UnsupportedOperatorError(op)

    field_value = _resolve_field(ctx, clause["field"])
    expected = clause.get("value")

    result = _apply_op(op, field_value, expected)
    if not result:
        failed.append(
            FailedClause(
                field=clause["field"],
                op=op,
                value=expected,
                message=clause.get("message"),
                fundamento=clause.get("fundamento"),
            )
        )
    return result


def _resolve_field(ctx: dict[str, Any], path: str) -> Any:
    parts = path.split(".")
    cur: Any = ctx
    for part in parts:
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def _apply_op(op: str, lhs: Any, rhs: Any) -> bool:
    if op == "eq":
        return lhs == rhs
    if op == "neq":
        return lhs != rhs
    if op == "lt":
        return lhs is not None and rhs is not None and lhs < rhs
    if op == "lte":
        return lhs is not None and rhs is not None and lhs <= rhs
    if op == "gt":
        return lhs is not None and rhs is not None and lhs > rhs
    if op == "gte":
        return lhs is not None and rhs is not None and lhs >= rhs
    if op == "between":
        if not isinstance(rhs, (list, tuple)) or len(rhs) != 2:
            raise InvalidRuleError("between requires value=[min, max]")
        lo, hi = rhs
        return lhs is not None and lo <= lhs <= hi
    if op == "in":
        if not isinstance(rhs, Iterable) or isinstance(rhs, (str, bytes)):
            raise InvalidRuleError("in requires value to be a list/tuple/set")
        return lhs in rhs
    if op == "not_in":
        if not isinstance(rhs, Iterable) or isinstance(rhs, (str, bytes)):
            raise InvalidRuleError("not_in requires value to be a list/tuple/set")
        return lhs not in rhs
    if op == "exists":
        return lhs is not None
    if op == "not_exists":
        return lhs is None
    if op == "matches_regex":
        if not isinstance(rhs, str):
            raise InvalidRuleError("matches_regex requires value=<regex string>")
        if not isinstance(lhs, str):
            return False
        return re.match(rhs, lhs) is not None
    raise UnsupportedOperatorError(op)
