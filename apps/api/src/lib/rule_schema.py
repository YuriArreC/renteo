"""Carga y valida JSON Schemas de reglas declarativas (skill 11).

Mismos schemas que `tools/validate_rules.py` consume para verificar
las reglas publicadas en CI; este módulo los expone como helper para
el panel admin.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import jsonschema  # type: ignore[import-untyped]

_SCHEMAS_DIR = (
    Path(__file__).resolve().parents[1]
    / "domain"
    / "tax_engine"
    / "rule_schemas"
)


@dataclass(frozen=True)
class ValidationFailure:
    path: str
    message: str


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    errors: tuple[ValidationFailure, ...]


def load_schema(domain: str) -> dict[str, Any] | None:
    schema_file = _SCHEMAS_DIR / f"{domain}.schema.json"
    if not schema_file.exists():
        return None
    raw = schema_file.read_text(encoding="utf-8")
    parsed: dict[str, Any] = json.loads(raw)
    return parsed


def _format_path(parts: Any) -> str:
    out = "$"
    for p in parts:
        out += f".{p}" if isinstance(p, str) else f"[{p}]"
    return out


def validate_rule(domain: str, rules: dict[str, Any]) -> ValidationResult:
    """Valida `rules` contra el JSON Schema de `domain`.

    Si no existe schema para el dominio, lo trata como error: cualquier
    regla con dominio desconocido no debería poder publicarse.
    """
    schema = load_schema(domain)
    if schema is None:
        return ValidationResult(
            valid=False,
            errors=(
                ValidationFailure(
                    path="$",
                    message=(
                        f"no schema file for domain {domain!r} "
                        f"(expected {domain}.schema.json en "
                        "src/domain/tax_engine/rule_schemas/)"
                    ),
                ),
            ),
        )
    validator = jsonschema.Draft202012Validator(schema)
    failures: list[ValidationFailure] = []
    for err in validator.iter_errors(rules):
        path = _format_path(err.absolute_path)
        failures.append(
            ValidationFailure(path=path, message=err.message)
        )
    return ValidationResult(
        valid=not failures, errors=tuple(failures)
    )


def list_known_domains() -> list[str]:
    if not _SCHEMAS_DIR.exists():
        return []
    return sorted(
        f.stem.replace(".schema", "")
        for f in _SCHEMAS_DIR.glob("*.schema.json")
    )
