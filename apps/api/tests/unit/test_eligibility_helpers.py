"""Tests unitarios para helpers puros de eligibility y guardrails.

Cubren ramas que no se ejercitan en integration porque dependen de
shapes específicas de la rule (clause no-dict, item sin id, etc.).
"""

from __future__ import annotations

from src.domain.tax_engine.eligibility import (
    _flatten_predicates,
    _positive_text_for,
)


def test_flatten_returns_empty_for_non_dict() -> None:
    assert _flatten_predicates("not a dict") == []
    assert _flatten_predicates(None) == []
    assert _flatten_predicates(42) == []


def test_flatten_unwraps_all_of_nested_in_any_of() -> None:
    clause = {
        "any_of": [
            {
                "all_of": [
                    {"field": "ingresos_uf", "op": "lte", "value": 75_000},
                    {"field": "regimen", "op": "in", "value": ["14_d_3"]},
                ]
            },
            {"field": "regimen", "op": "eq", "value": "14_d_8"},
        ]
    }
    flat = _flatten_predicates(clause)
    fields = {p["field"] for p in flat}
    assert fields == {"ingresos_uf", "regimen"}


def test_flatten_unwraps_not_branch() -> None:
    clause = {"not": {"field": "regimen", "op": "eq", "value": "14_a"}}
    flat = _flatten_predicates(clause)
    assert len(flat) == 1
    assert flat[0]["field"] == "regimen"


def test_flatten_returns_empty_for_unknown_shape() -> None:
    assert _flatten_predicates({"foo": "bar"}) == []


def test_positive_text_falls_back_when_field_or_op_invalid() -> None:
    assert (
        _positive_text_for(None, "lte", 100) == "Requisito cumplido."
    )
    assert (
        _positive_text_for("ingresos", 42, 100) == "Requisito cumplido."
    )


def test_positive_text_uses_human_symbol() -> None:
    assert "≤" in _positive_text_for("ingresos_uf", "lte", 75000)
    assert "≥" in _positive_text_for("capital_uf", "gte", 5000)
    # Unknown op falls back to op string itself.
    assert "matches_regex" in _positive_text_for("rut", "matches_regex", "^.*$")
