"""Tests del validador de RUT chileno (módulo 11)."""

from __future__ import annotations

import pytest

from src.lib.rut import InvalidRutError, validate_rut


@pytest.mark.parametrize(
    "raw,expected",
    [
        # DV numérico clásico
        ("11111111-1", "11111111-1"),
        # DV K
        ("10000013-K", "10000013-K"),
        # DV minúscula → mayúscula
        ("10000013-k", "10000013-K"),
        # Con puntos (los limpia internamente)
        ("11.111.111-1", "11111111-1"),
        # Cuerpo corto
        ("123-6", "123-6"),
    ],
)
def test_validate_rut_canonicalizes(raw: str, expected: str) -> None:
    assert validate_rut(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "no-es-rut",
        "11111111",
        "11111111-",
        "1111111-A",
        "-1",
        "",
    ],
)
def test_validate_rut_rejects_format(raw: str) -> None:
    with pytest.raises(InvalidRutError, match="formato inválido"):
        validate_rut(raw)


def test_validate_rut_rejects_bad_dv() -> None:
    with pytest.raises(InvalidRutError, match="DV inválido"):
        validate_rut("11111111-9")
