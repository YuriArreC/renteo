"""Test bloqueante: ningún número mágico tributario en `domain/tax_engine`.

Patrón anti-skill 11. Tasas, tramos y topes deben vivir en `tax_year_params`
o en reglas declarativas con vigencia, jamás como literal en código del motor.

Cubre también la sensibilidad del propio scanner: con un repo limpio pasa,
con un literal plantado falla.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

# Patrones prohibidos: cada tupla (regex, descripción del valor real).
# Si necesitas usar un valor literal por razones legítimas (ej. unidad
# constante, no tasa), agrega `# noqa: tax-magic-number  motivo` en la línea
# y ajusta este test con un per-line override.
FORBIDDEN: tuple[tuple[str, str], ...] = (
    (r"0\.27\b", "tasa IDPC 14 A"),
    (r"0\.125\b", "tasa transitoria 14 D N°3"),
    (r"0\.25\b", "tasa 14 D N°3 permanente"),
    (r"0\.19\b", "tasa IVA"),
    (r"0\.1525\b", "retención BHE 2026"),
    (r"\b75[._]?000\b", "tope ingresos 14 D"),
    (r"\b85[._]?000\b", "tope capital / año individual 14 D"),
    (r"\b5[._]?000\b", "tope rebaja 14 E"),
    (r"\b13[._]?5\b", "primer tramo IGC en UTA"),
)

EXEMPT_PATH_PARTS: tuple[str, ...] = (
    "tests/golden",
    "supabase/seeds",
    "rule_schemas",
)

NOQA_MARKER = "# noqa: tax-magic-number"

REPO_ROOT = Path(__file__).resolve().parents[2]
TAX_ENGINE = REPO_ROOT / "apps" / "api" / "src" / "domain" / "tax_engine"


def _scan_for_violations(root: Path) -> list[str]:
    if not root.exists():
        return [f"path does not exist: {root}"]

    violations: list[str] = []
    for path in root.rglob("*.py"):
        path_str = str(path).replace("\\", "/")
        if any(part in path_str for part in EXEMPT_PATH_PARTS):
            continue
        text = path.read_text(encoding="utf-8")
        lines = text.split("\n")

        for pattern, descripcion in FORBIDDEN:
            for match in re.finditer(pattern, text):
                line_no = text[: match.start()].count("\n") + 1
                line_text = lines[line_no - 1] if line_no <= len(lines) else ""
                if NOQA_MARKER in line_text:
                    continue
                violations.append(
                    f"{path}:{line_no}  {descripcion}  patrón={pattern}"
                )
    return violations


# ---------------------------------------------------------------------------
# Test bloqueante: el repo no debe tener literales prohibidos.
# ---------------------------------------------------------------------------


def test_no_hardcoded_tax_values_in_repo() -> None:
    violations = _scan_for_violations(TAX_ENGINE)
    assert not violations, (
        "Hardcoded tax values detected in domain/tax_engine. "
        "Mueve el valor a tax_year_params o a una regla declarativa "
        "(skill 11):\n  " + "\n  ".join(violations)
    )


# ---------------------------------------------------------------------------
# Tests del propio scanner — sensibilidad.
# ---------------------------------------------------------------------------


def test_scanner_passes_on_clean_directory(tmp_path: Path) -> None:
    (tmp_path / "clean.py").write_text(
        "import math\n"
        "PI = math.pi\n"
        "INVENTORY_TARGET = 42\n",
        encoding="utf-8",
    )
    assert _scan_for_violations(tmp_path) == []


@pytest.mark.parametrize(
    ("planted_line", "expected_pattern"),
    [
        ("rate = 0.125\n", "tasa transitoria 14 D N°3"),
        ("idpc = 0.27\n", "tasa IDPC 14 A"),
        ("iva = 0.19\n", "tasa IVA"),
        ("tope = 75000\n", "tope ingresos 14 D"),
        ("limite = 5_000\n", "tope rebaja 14 E"),
    ],
)
def test_scanner_detects_planted_violation(
    tmp_path: Path, planted_line: str, expected_pattern: str
) -> None:
    (tmp_path / "infected.py").write_text(planted_line, encoding="utf-8")
    violations = _scan_for_violations(tmp_path)
    assert violations, f"scanner failed to detect: {planted_line!r}"
    assert any(expected_pattern in v for v in violations), (
        f"scanner detected something but not the expected pattern "
        f"{expected_pattern!r}: {violations}"
    )


def test_scanner_respects_noqa_marker(tmp_path: Path) -> None:
    """Una línea con `# noqa: tax-magic-number` queda exenta."""
    (tmp_path / "exempt.py").write_text(
        "rate = 0.125  # noqa: tax-magic-number  unit, not a tax rate\n",
        encoding="utf-8",
    )
    assert _scan_for_violations(tmp_path) == []


def test_scanner_skips_exempt_paths(tmp_path: Path) -> None:
    (tmp_path / "supabase" / "seeds").mkdir(parents=True)
    (tmp_path / "supabase" / "seeds" / "data.py").write_text(
        "rate = 0.125\n", encoding="utf-8"
    )
    assert _scan_for_violations(tmp_path) == []
