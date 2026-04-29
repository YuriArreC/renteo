# ruff: noqa: I001
# TODO: ruff isort marca este bloque como un-sorted/un-formatted aunque el
# orden visual coincide con el de otros archivos del repo que sí pasan.
# Resolver al correr `ruff check --fix` localmente y ver el diff exacto.
"""Tests unitarios del evaluador declarativo (sin DB).

Cubren operadores, combinadores, paths anidados y rechazo de operadores no
soportados / shapes inválidas (skill 11 anti-patterns).
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from src.domain.tax_engine.rule_evaluator import (
    SUPPORTED_OPERATORS,
    EvaluationResult,
    evaluate,
)
from src.lib.errors import InvalidRuleError, UnsupportedOperatorError


# ---------------------------------------------------------------------------
# Operadores básicos
# ---------------------------------------------------------------------------


def test_eq_pass() -> None:
    rule = {"field": "regimen", "op": "eq", "value": "14_d_3"}
    result = evaluate(rule, {"regimen": "14_d_3"})
    assert result.passed
    assert result.failed_clauses == ()


def test_eq_fail_records_failure_with_fundamento() -> None:
    rule = {
        "field": "regimen",
        "op": "eq",
        "value": "14_d_3",
        "message": "régimen no coincide",
        "fundamento": "art. 14 D N°3 LIR",
    }
    result = evaluate(rule, {"regimen": "14_a"})
    assert not result.passed
    assert len(result.failed_clauses) == 1
    failure = result.failed_clauses[0]
    assert failure.field == "regimen"
    assert failure.op == "eq"
    assert failure.message == "régimen no coincide"
    assert failure.fundamento == "art. 14 D N°3 LIR"


@pytest.mark.parametrize(
    ("op", "lhs", "rhs", "expected"),
    [
        ("neq", 1, 2, True),
        ("neq", 1, 1, False),
        ("lt", 70_000, 75_000, True),
        ("lt", 80_000, 75_000, False),
        ("lte", 75_000, 75_000, True),
        ("gt", 100, 50, True),
        ("gte", 50, 50, True),
    ],
)
def test_numeric_operators(op: str, lhs: int, rhs: int, expected: bool) -> None:
    result = evaluate({"field": "x", "op": op, "value": rhs}, {"x": lhs})
    assert result.passed is expected


def test_lt_with_none_lhs_fails_safely() -> None:
    result = evaluate({"field": "x", "op": "lt", "value": 100}, {})
    assert not result.passed


def test_between_true_at_bounds() -> None:
    rule = {"field": "uf", "op": "between", "value": [0, 75_000]}
    assert evaluate(rule, {"uf": 0}).passed
    assert evaluate(rule, {"uf": 75_000}).passed
    assert evaluate(rule, {"uf": 75_001}).passed is False


def test_between_requires_two_element_list() -> None:
    rule = {"field": "uf", "op": "between", "value": [0]}
    with pytest.raises(InvalidRuleError):
        evaluate(rule, {"uf": 1})


def test_in_membership() -> None:
    rule = {"field": "regimen", "op": "in", "value": ["14_d_3", "14_d_8"]}
    assert evaluate(rule, {"regimen": "14_d_3"}).passed
    assert not evaluate(rule, {"regimen": "14_a"}).passed


def test_in_rejects_string_value() -> None:
    # Strings son iterables pero no es la semántica deseada; rechazar explícito.
    rule = {"field": "regimen", "op": "in", "value": "14_d_3"}
    with pytest.raises(InvalidRuleError):
        evaluate(rule, {"regimen": "14_d_3"})


def test_exists_and_not_exists() -> None:
    assert evaluate({"field": "x", "op": "exists"}, {"x": 0}).passed
    assert not evaluate({"field": "x", "op": "exists"}, {}).passed
    assert evaluate({"field": "x", "op": "not_exists"}, {}).passed
    assert not evaluate({"field": "x", "op": "not_exists"}, {"x": 0}).passed


def test_matches_regex() -> None:
    rule = {"field": "rut", "op": "matches_regex", "value": "^[0-9]{1,8}-[0-9Kk]$"}
    assert evaluate(rule, {"rut": "12345678-9"}).passed
    assert not evaluate(rule, {"rut": "no es rut"}).passed


def test_matches_regex_requires_string_value() -> None:
    rule = {"field": "rut", "op": "matches_regex", "value": 123}
    with pytest.raises(InvalidRuleError):
        evaluate(rule, {"rut": "12345678-9"})


# ---------------------------------------------------------------------------
# Combinadores
# ---------------------------------------------------------------------------


def test_all_of_pass() -> None:
    rule = {
        "all_of": [
            {"field": "ingresos_uf", "op": "lte", "value": 75_000},
            {"field": "regimen", "op": "in", "value": ["14_d_3", "14_d_8"]},
        ]
    }
    ctx = {"ingresos_uf": 50_000, "regimen": "14_d_3"}
    assert evaluate(rule, ctx).passed


def test_all_of_collects_all_failed_clauses() -> None:
    rule = {
        "all_of": [
            {
                "field": "ingresos_uf",
                "op": "lte",
                "value": 75_000,
                "message": "ingresos > 75.000 UF",
            },
            {
                "field": "pct_pasivos",
                "op": "lte",
                "value": 0.35,
                "message": "ingresos pasivos > 35%",
            },
        ]
    }
    ctx = {"ingresos_uf": 80_000, "pct_pasivos": 0.5}
    result = evaluate(rule, ctx)
    assert not result.passed
    messages = {f.message for f in result.failed_clauses}
    assert messages == {"ingresos > 75.000 UF", "ingresos pasivos > 35%"}


def test_any_of_short_circuits_on_first_pass() -> None:
    rule = {
        "any_of": [
            {"field": "regimen", "op": "eq", "value": "14_d_3"},
            {"field": "regimen", "op": "eq", "value": "14_d_8"},
        ]
    }
    ctx = {"regimen": "14_d_3"}
    result = evaluate(rule, ctx)
    assert result.passed
    assert result.failed_clauses == ()


def test_any_of_fail_collects_all_failures() -> None:
    rule = {
        "any_of": [
            {"field": "regimen", "op": "eq", "value": "14_d_3"},
            {"field": "regimen", "op": "eq", "value": "14_d_8"},
        ]
    }
    ctx = {"regimen": "14_a"}
    result = evaluate(rule, ctx)
    assert not result.passed
    assert len(result.failed_clauses) == 2


def test_not_inverts_result() -> None:
    rule = {"not": {"field": "regimen", "op": "eq", "value": "14_a"}}
    assert evaluate(rule, {"regimen": "14_d_3"}).passed
    assert not evaluate(rule, {"regimen": "14_a"}).passed


# ---------------------------------------------------------------------------
# Paths anidados
# ---------------------------------------------------------------------------


def test_nested_field_path() -> None:
    rule = {
        "field": "activo.proveedor_relacionado",
        "op": "eq",
        "value": True,
    }
    assert evaluate(rule, {"activo": {"proveedor_relacionado": True}}).passed
    assert not evaluate(rule, {"activo": {"proveedor_relacionado": False}}).passed


def test_nested_field_missing_resolves_to_none() -> None:
    rule = {"field": "a.b.c", "op": "exists"}
    assert not evaluate(rule, {"a": {"b": {}}}).passed
    assert not evaluate(rule, {}).passed


# ---------------------------------------------------------------------------
# Seguridad: rechazo de operadores no soportados / shapes inválidas
# ---------------------------------------------------------------------------


def test_unsupported_operator_raises() -> None:
    rule = {"field": "x", "op": "exec", "value": "rm -rf /"}
    with pytest.raises(UnsupportedOperatorError):
        evaluate(rule, {"x": 1})


def test_eval_keyword_is_not_an_operator() -> None:
    # Defensa explícita contra el patrón anti-skill: nada que evoque eval.
    assert "eval" not in SUPPORTED_OPERATORS
    assert "exec" not in SUPPORTED_OPERATORS
    assert "lambda" not in SUPPORTED_OPERATORS


def test_unrecognized_shape_raises() -> None:
    with pytest.raises(InvalidRuleError):
        evaluate({"foo": "bar"}, {})


def test_all_of_requires_non_empty_list() -> None:
    with pytest.raises(InvalidRuleError):
        evaluate({"all_of": []}, {})


def test_clause_must_be_dict() -> None:
    with pytest.raises(InvalidRuleError):
        evaluate({"all_of": ["not-a-dict"]}, {})  # type: ignore[list-item]


# ---------------------------------------------------------------------------
# EvaluationResult
# ---------------------------------------------------------------------------


def test_evaluation_result_is_frozen_dataclass() -> None:
    rule = {"field": "x", "op": "eq", "value": 1}
    result = evaluate(rule, {"x": 1})
    assert isinstance(result, EvaluationResult)
    with pytest.raises(FrozenInstanceError):
        result.passed = False  # type: ignore[misc]
