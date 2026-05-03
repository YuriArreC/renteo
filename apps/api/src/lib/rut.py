"""Validación de RUT chileno (Rol Único Tributario).

Formato canónico: `<cuerpo>-<dv>` con cuerpo numérico de 1-8 dígitos
y dígito verificador 0-9 o K. El cálculo del DV usa módulo 11 con
factores cíclicos 2-7 sobre el cuerpo de derecha a izquierda.

Esta función NO normaliza puntos. Si la entrada trae puntos los
removemos antes de validar y los reintroduce mantener forma canónica
sería un loss de información para el cliente — preferimos rechazar.
"""

from __future__ import annotations

import re

_RUT_PATTERN = re.compile(r"^([0-9]{1,8})-([0-9Kk])$")


class InvalidRutError(ValueError):
    """RUT con formato inválido o dígito verificador incorrecto."""


def validate_rut(rut: str) -> str:
    """Devuelve el RUT en formato canónico `<cuerpo>-<dv>` con DV
    en mayúscula. Lanza `InvalidRutError` si formato o DV no coinciden.
    """
    cleaned = rut.strip().replace(".", "").upper()
    match = _RUT_PATTERN.match(cleaned)
    if not match:
        raise InvalidRutError(
            f"RUT con formato inválido: {rut!r} (esperado <cuerpo>-<DV>)"
        )
    cuerpo, dv_input = match.group(1), match.group(2)
    expected_dv = _compute_dv(int(cuerpo))
    if dv_input != expected_dv:
        raise InvalidRutError(
            f"DV inválido para RUT {cleaned!r} (esperado {expected_dv})"
        )
    return f"{cuerpo}-{expected_dv}"


def _compute_dv(cuerpo: int) -> str:
    """Calcula el DV mod 11 con factores cíclicos 2..7."""
    suma = 0
    multiplicador = 2
    while cuerpo > 0:
        suma += (cuerpo % 10) * multiplicador
        cuerpo //= 10
        multiplicador = 2 if multiplicador == 7 else multiplicador + 1
    resto = suma % 11
    valor = 11 - resto
    if valor == 11:
        return "0"
    if valor == 10:
        return "K"
    return str(valor)
