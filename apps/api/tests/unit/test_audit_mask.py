"""Tests del enmascaramiento de RUT para audit_log."""

from __future__ import annotations

import pytest

from src.lib.audit import mask_rut


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("12345678-5", "12******-5"),
        ("11111111-1", "11******-1"),
        ("123-6", "12*-6"),
        # Cuerpo ≤ 2 dígitos se enmascara completo (defensa en profundidad).
        ("12-K", "**-K"),
        ("1-9", "*-9"),
    ],
)
def test_mask_rut_preserves_dv(raw: str, expected: str) -> None:
    assert mask_rut(raw) == expected


def test_mask_rut_returns_stars_when_no_dash() -> None:
    assert mask_rut("12345678") == "***"
