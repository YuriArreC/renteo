"""El seed de red_flags y el fixture de tests no pueden divergir.

`20260713120000_red_flags_gasto_giro.sql` es la FUENTE DE VERDAD (es el
artefacto versionado y firmable, skill 11). `tests/fixtures/red_flags_gasto_giro.json`
es un espejo que permite a los tests unitarios evaluar las banderas reales sin
DB.

Dos fuentes = riesgo de deriva. Este test la convierte en un fallo de CI: si
alguien afloja una condición en la migración y no toca el fixture (o al revés),
los tests unitarios seguirían pasando contra banderas que ya no son las que el
motor usa. Eso es exactamente el fallo que no podemos permitirnos en un
guardrail.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.tax_engine.gasto_giro import (
    GastoGiroInputs,
    bloqueado,
    evaluar_gasto_giro,
)
from src.domain.tax_engine.rule_resolver import resolve_domain_rules

pytestmark = pytest.mark.asyncio

FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "red_flags_gasto_giro.json"
)


def _fixture() -> dict[str, Any]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


async def _seeded(session: AsyncSession) -> dict[str, dict[str, Any]]:
    result = await session.execute(
        text(
            """
            select key, rules
              from tax_rules.rule_sets
             where domain = 'red_flag'
               and status = 'published'
            """
        )
    )
    return {row.key: row.rules for row in result}


async def test_seed_coincide_con_fixture(admin_session: AsyncSession) -> None:
    esperadas = {b["key"]: b["rules"] for b in _fixture()["banderas"]}
    seedeadas = await _seeded(admin_session)

    assert set(seedeadas) == set(esperadas), (
        "El set de banderas seedeadas difiere del fixture. "
        f"Solo en DB: {sorted(set(seedeadas) - set(esperadas))}. "
        f"Solo en fixture: {sorted(set(esperadas) - set(seedeadas))}."
    )

    for key, rules_esperadas in esperadas.items():
        assert seedeadas[key] == rules_esperadas, (
            f"La bandera {key!r} seedeada no coincide con el fixture. "
            f"Los tests unitarios estarían evaluando una bandera distinta "
            f"de la que usa el motor."
        )


async def test_toda_bandera_seedeada_tiene_doble_firma(
    admin_session: AsyncSession,
) -> None:
    """El CHECK de rule_sets ya lo exige; esto lo deja explícito y visible."""
    result = await admin_session.execute(
        text(
            """
            select key
              from tax_rules.rule_sets
             where domain = 'red_flag'
               and status = 'published'
               and (published_by_contador is null
                    or published_by_admin is null
                    or published_by_contador = published_by_admin)
            """
        )
    )
    sin_firma = [row.key for row in result]
    assert not sin_firma, f"Banderas publicadas sin doble firma: {sin_firma}"


async def test_resolve_domain_rules_trae_todas_las_banderas_vigentes(
    admin_session: AsyncSession,
) -> None:
    esperadas = {b["key"] for b in _fixture()["banderas"]}
    reglas = await resolve_domain_rules(admin_session, "red_flag", 2026)
    assert {r.key for r in reglas} >= esperadas


async def test_banderas_no_rigen_antes_de_su_vigencia(
    admin_session: AsyncSession,
) -> None:
    """Vigencia 2020-01-01: el art. 31 post Ley 21.210 rige desde el 1-ene-2020.

    Un ejercicio anterior no puede resolver estas banderas — si lo hiciera,
    estaríamos aplicando derecho vigente a un año que se regía por el texto
    antiguo (el que sí tenía el umbral de supermercados).
    """
    reglas = await resolve_domain_rules(admin_session, "red_flag", 2019)
    keys_gasto_giro = {b["key"] for b in _fixture()["banderas"]}
    assert not ({r.key for r in reglas} & keys_gasto_giro)


async def test_evaluar_gasto_giro_end_to_end_bloquea_el_auto_en_leasing(
    admin_session: AsyncSession,
) -> None:
    """Camino completo: DB → resolve_domain_rules → evaluate → Bandera."""
    gasto = GastoGiroInputs(
        categoria="vehiculo",
        nexo_giro_declarado=True,
        es_personal=False,
        es_vehiculo_automovil=True,
        giro_habitual_vehiculos=False,
        via_leasing=True,
        tiene_resolucion_director=False,
        tiene_documento_tributario=True,
        tipo_desembolso="ordinario",
        contraparte_relacionada=False,
        ia_declarado_y_pagado=False,
        exento_o_no_gravado_ia=False,
        es_gasto_extranjero=False,
        doc_extranjero_datos_completos=False,
        regimen="14_a",
        pagado=True,
        fraccionado_para_umbral=False,
    )
    banderas = await evaluar_gasto_giro(admin_session, gasto, 2026)

    assert bloqueado(banderas)
    assert "vehiculo_automovil_fuera_de_giro" in {b.id for b in banderas}
