"""Banderas del optimizador de gasto del giro — evaluación pura, sin DB.

Evalúa las banderas REALMENTE seedeadas (fixture espejo de la migración
`20260713120000_red_flags_gasto_giro.sql`; `test_red_flags_seed.py` verifica que
no divergen), no banderas de juguete. Si alguien afloja una condición en la
migración, estos tests caen.

Cubre las tres clases de fallo que importan en un guardrail:
1. **Falso negativo** (lo grave): un gasto ilícito que NO se bloquea. Cada
   bandera de bloqueo tiene su caso positivo.
2. **Falso positivo**: un gasto legítimo que se bloquea de más.
3. **Fail-open silencioso**: una bandera que mira un campo ausente del contexto
   nunca dispara — ver `test_toda_field_de_las_banderas_existe_en_el_contexto`.
"""

from __future__ import annotations

import json
import re
from dataclasses import fields, replace
from datetime import date
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from src.domain.tax_engine.gasto_giro import (
    SEVERIDAD_BLOCK,
    SEVERIDAD_WARN,
    Bandera,
    GastoGiroInputs,
    assert_sin_bloqueo,
    bloqueado,
    evaluar_banderas,
)
from src.domain.tax_engine.rule_resolver import RuleSet
from src.lib.errors import InvalidRuleError, RedFlagBlocked

FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "red_flags_gasto_giro.json"
)


def _cargar_banderas() -> list[RuleSet]:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    vigencia = date.fromisoformat(data["vigencia_desde"])
    return [
        RuleSet(
            id=uuid4(),
            domain="red_flag",
            key=b["key"],
            version=1,
            vigencia_desde=vigencia,
            vigencia_hasta=None,
            rules=b["rules"],
            fuente_legal=b["fuente_legal"],
        )
        for b in data["banderas"]
    ]


REGLAS = _cargar_banderas()


def _gasto(**overrides: Any) -> GastoGiroInputs:
    """Gasto limpio y deducible: arriendo de bodega, documentado, régimen 14 A.

    Los tests parten de acá y ensucian UN atributo por vez, de modo que la
    bandera que se levante sea atribuible a ese atributo y no al ruido de la
    base.
    """
    base = GastoGiroInputs(
        categoria="arriendo",
        nexo_giro_declarado=True,
        es_personal=False,
        es_vehiculo_automovil=False,
        giro_habitual_vehiculos=False,
        via_leasing=False,
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
    return replace(base, **overrides)


def _ids(banderas: list[Bandera]) -> set[str]:
    return {b.id for b in banderas}


# ---------------------------------------------------------------------------
# Línea base: lo lícito no se molesta.
# ---------------------------------------------------------------------------


def test_gasto_limpio_no_levanta_ninguna_bandera() -> None:
    assert evaluar_banderas(REGLAS, _gasto()) == []


# ---------------------------------------------------------------------------
# Automóviles (art. 31 inc. 1°) — incluida la trampa del leasing.
# ---------------------------------------------------------------------------


def test_automovil_fuera_del_giro_bloquea() -> None:
    banderas = evaluar_banderas(
        REGLAS, _gasto(categoria="vehiculo", es_vehiculo_automovil=True)
    )
    assert "vehiculo_automovil_fuera_de_giro" in _ids(banderas)
    assert bloqueado(banderas)


def test_automovil_via_leasing_sigue_bloqueado() -> None:
    """El leasing NO es una salida — es el error que más se va a intentar.

    La Circular SII N°53/2020 incluye expresamente el leasing (financiero y
    operativo) dentro de la prohibición. Si esta condición alguna vez se
    "arregla" para exceptuar el leasing, este test cae.
    """
    banderas = evaluar_banderas(
        REGLAS,
        _gasto(
            categoria="vehiculo",
            es_vehiculo_automovil=True,
            via_leasing=True,
        ),
    )
    assert "vehiculo_automovil_fuera_de_giro" in _ids(banderas)
    assert bloqueado(banderas)


def test_automovil_es_el_giro_habitual_no_bloquea() -> None:
    """Excepción (a): rent-a-car / automotora. Falso positivo que debe evitarse."""
    banderas = evaluar_banderas(
        REGLAS,
        _gasto(
            categoria="vehiculo",
            es_vehiculo_automovil=True,
            giro_habitual_vehiculos=True,
        ),
    )
    assert not bloqueado(banderas)


def test_automovil_con_resolucion_fundada_del_director_no_bloquea() -> None:
    """Excepción (b): resolución fundada del Director del SII."""
    banderas = evaluar_banderas(
        REGLAS,
        _gasto(
            categoria="vehiculo",
            es_vehiculo_automovil=True,
            tiene_resolucion_director=True,
        ),
    )
    assert not bloqueado(banderas)


# ---------------------------------------------------------------------------
# Partes relacionadas (art. 31 incs. 3° y final, N°4 y N°12).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("tipo", ["transaccion", "clausula_penal"])
def test_transaccion_o_clausula_penal_con_relacionado_bloquea(tipo: str) -> None:
    banderas = evaluar_banderas(
        REGLAS, _gasto(tipo_desembolso=tipo, contraparte_relacionada=True)
    )
    assert "transaccion_o_clausula_penal_con_relacionado" in _ids(banderas)
    assert bloqueado(banderas)


@pytest.mark.parametrize("tipo", ["transaccion", "clausula_penal"])
def test_transaccion_o_clausula_penal_entre_no_relacionados_es_gasto(
    tipo: str,
) -> None:
    """El inciso final las admite expresamente entre partes NO relacionadas."""
    banderas = evaluar_banderas(
        REGLAS, _gasto(tipo_desembolso=tipo, contraparte_relacionada=False)
    )
    assert not bloqueado(banderas)


def test_pago_exterior_a_relacionado_sin_impuesto_adicional_bloquea() -> None:
    banderas = evaluar_banderas(
        REGLAS,
        _gasto(
            tipo_desembolso="pago_exterior_art59",
            contraparte_relacionada=True,
            ia_declarado_y_pagado=False,
            exento_o_no_gravado_ia=False,
        ),
    )
    assert "pago_exterior_art59_relacionado_sin_impuesto_adicional" in _ids(
        banderas
    )
    assert bloqueado(banderas)


def test_pago_exterior_a_relacionado_con_ia_pagado_solo_advierte_el_tope() -> None:
    """Con el IA pagado desaparece el bloqueo, pero queda el tope del N°12."""
    banderas = evaluar_banderas(
        REGLAS,
        _gasto(
            tipo_desembolso="pago_exterior_art59",
            contraparte_relacionada=True,
            ia_declarado_y_pagado=True,
        ),
    )
    assert not bloqueado(banderas)
    assert "pago_exterior_art59_relacionado_tope" in _ids(banderas)


def test_pago_exterior_exento_de_ia_no_bloquea() -> None:
    """Salida legal: renta exenta o no gravada (p. ej. por convenio de doble
    tributación)."""
    banderas = evaluar_banderas(
        REGLAS,
        _gasto(
            tipo_desembolso="pago_exterior_art59",
            contraparte_relacionada=True,
            exento_o_no_gravado_ia=True,
        ),
    )
    assert not bloqueado(banderas)


def test_credito_incobrable_con_relacionado_advierte() -> None:
    banderas = evaluar_banderas(
        REGLAS,
        _gasto(
            tipo_desembolso="credito_incobrable", contraparte_relacionada=True
        ),
    )
    assert "credito_incobrable_con_relacionado" in _ids(banderas)
    assert not bloqueado(banderas)


# ---------------------------------------------------------------------------
# Supermercados — el umbral derogado NO debe reaparecer.
# ---------------------------------------------------------------------------


def test_supermercado_advierte_caso_a_caso_y_no_bloquea() -> None:
    banderas = evaluar_banderas(REGLAS, _gasto(categoria="supermercado"))
    assert "compra_en_supermercado_caso_a_caso" in _ids(banderas)
    assert not bloqueado(banderas)


def test_ninguna_bandera_reintroduce_un_umbral_de_supermercados() -> None:
    """La Ley 21.210 derogó el tope de 5 UTA. Nada puede volver a mirarlo.

    Guardia de regresión: la 1a ronda de research dio por vigente ese umbral y
    el diseño estuvo a punto de parametrizarlo. Si alguien vuelve a introducir
    una condición numérica sobre compras en supermercado, este test lo caza.
    """
    for regla in REGLAS:
        condicion = json.dumps(regla.rules["condicion"], ensure_ascii=False)
        # \b para no chocar con "trib(uta)rio" — la subcadena vive dentro de
        # nombres de campo legítimos.
        assert not re.search(r"\buta\b", condicion, re.IGNORECASE), (
            f"{regla.key}: una condición referencia UTA. Los topes van a "
            f"tax_params con firma, nunca a una bandera."
        )
        for op in ("lt", "lte", "gt", "gte", "between"):
            assert f'"op": "{op}"' not in condicion, (
                f"{regla.key}: comparación numérica {op!r} en una bandera. "
                f"Un umbral pertenece a tax_params firmado, no acá."
            )


# ---------------------------------------------------------------------------
# Base caja 14 D N°3 (Circular SII N°62/2020).
# ---------------------------------------------------------------------------


def test_egreso_no_pagado_en_14_d_3_advierte() -> None:
    banderas = evaluar_banderas(
        REGLAS, _gasto(regimen="14_d_3", pagado=False)
    )
    assert "egreso_no_pagado_en_base_caja" in _ids(banderas)
    assert not bloqueado(banderas)


def test_egreso_no_pagado_en_14_a_no_advierte() -> None:
    """14 A es devengado: "pagado o adeudado". No pagado ≠ no deducible."""
    banderas = evaluar_banderas(REGLAS, _gasto(regimen="14_a", pagado=False))
    assert "egreso_no_pagado_en_base_caja" not in _ids(banderas)


# ---------------------------------------------------------------------------
# Nexo, documentación, extranjero, conducta.
# ---------------------------------------------------------------------------


def test_gasto_personal_bloquea() -> None:
    banderas = evaluar_banderas(REGLAS, _gasto(es_personal=True))
    assert "gasto_personal" in _ids(banderas)
    assert bloqueado(banderas)


def test_sin_nexo_con_el_giro_bloquea() -> None:
    banderas = evaluar_banderas(REGLAS, _gasto(nexo_giro_declarado=False))
    assert "sin_nexo_giro" in _ids(banderas)
    assert bloqueado(banderas)


def test_fraccionamiento_para_eludir_umbral_bloquea() -> None:
    banderas = evaluar_banderas(REGLAS, _gasto(fraccionado_para_umbral=True))
    assert "fraccionamiento_para_eludir_umbral" in _ids(banderas)
    assert bloqueado(banderas)


def test_sin_documento_tributario_advierte_pero_no_bloquea() -> None:
    """Falta de documento ⇒ PENDIENTE, no ilícito. Se puede corregir."""
    banderas = evaluar_banderas(
        REGLAS, _gasto(tiene_documento_tributario=False)
    )
    assert "sin_documento_tributario" in _ids(banderas)
    assert not bloqueado(banderas)


def test_gasto_extranjero_con_documento_incompleto_advierte() -> None:
    banderas = evaluar_banderas(
        REGLAS,
        _gasto(es_gasto_extranjero=True, doc_extranjero_datos_completos=False),
    )
    assert "gasto_extranjero_documento_incompleto" in _ids(banderas)
    assert not bloqueado(banderas)


def test_gasto_extranjero_con_documento_completo_no_advierte() -> None:
    banderas = evaluar_banderas(
        REGLAS,
        _gasto(es_gasto_extranjero=True, doc_extranjero_datos_completos=True),
    )
    assert "gasto_extranjero_documento_incompleto" not in _ids(banderas)


# ---------------------------------------------------------------------------
# Contrato del módulo: semántica, orden, y el fallo silencioso.
# ---------------------------------------------------------------------------


def test_toda_field_de_las_banderas_existe_en_el_contexto() -> None:
    """Anti fail-open: una bandera que mira un campo inexistente nunca dispara.

    `_resolve_field` devuelve None para un campo ausente, y `None == False` es
    False: una bandera de BLOQUEO cuya condición apunta a un campo que
    `GastoGiroInputs` no trae quedaría **permanentemente apagada**, en silencio
    y sin error. Este test convierte ese fallo mudo en un fallo de CI.
    """
    disponibles = {f.name for f in fields(GastoGiroInputs)}

    def _campos(clause: Any) -> set[str]:
        if not isinstance(clause, dict):
            return set()
        if "all_of" in clause:
            return set().union(*(_campos(c) for c in clause["all_of"]))
        if "any_of" in clause:
            return set().union(*(_campos(c) for c in clause["any_of"]))
        if "not" in clause:
            return _campos(clause["not"])
        if "field" in clause:
            return {clause["field"]}
        return set()

    for regla in REGLAS:
        referenciados = _campos(regla.rules["condicion"])
        huerfanos = referenciados - disponibles
        assert not huerfanos, (
            f"{regla.key}: la condición referencia campos que "
            f"GastoGiroInputs no provee: {sorted(huerfanos)}. La bandera "
            f"nunca se levantaría."
        )


def test_la_condicion_cumplida_levanta_la_bandera() -> None:
    """Fija la semántica invertida respecto de `eligibility`.

    En elegibilidad, `passed=True` = requisito cumplido = bueno.
    En una bandera roja, condición cumplida = problema = malo.
    Normalizar ambos al mismo signo invertiría los guardrails en silencio.
    """
    limpio = evaluar_banderas(REGLAS, _gasto(es_personal=False))
    sucio = evaluar_banderas(REGLAS, _gasto(es_personal=True))

    assert "gasto_personal" not in _ids(limpio)
    assert "gasto_personal" in _ids(sucio)


def test_los_bloqueos_se_ordenan_antes_que_los_avisos() -> None:
    banderas = evaluar_banderas(
        REGLAS,
        _gasto(
            es_personal=True,               # block
            tiene_documento_tributario=False,  # warn
        ),
    )
    severidades = [b.severidad for b in banderas]
    assert SEVERIDAD_BLOCK in severidades and SEVERIDAD_WARN in severidades
    assert severidades == sorted(
        severidades, key=lambda s: s != SEVERIDAD_BLOCK
    )


def test_assert_sin_bloqueo_lanza_red_flag_blocked() -> None:
    banderas = evaluar_banderas(REGLAS, _gasto(es_personal=True))
    with pytest.raises(RedFlagBlocked) as exc:
        assert_sin_bloqueo(banderas)
    assert "gasto_personal" in str(exc.value)
    assert "art. 31" in str(exc.value)


def test_assert_sin_bloqueo_deja_pasar_los_avisos() -> None:
    banderas = evaluar_banderas(
        REGLAS, _gasto(tiene_documento_tributario=False)
    )
    assert banderas  # hay avisos...
    assert_sin_bloqueo(banderas)  # ...pero no bloquean


def test_toda_bandera_seedeada_cita_su_fundamento() -> None:
    """Regla no negociable: cada output del motor cita artículo + circular."""
    for regla in REGLAS:
        fundamento = regla.rules["fundamento"]
        assert fundamento.strip(), f"{regla.key}: fundamento vacío"
        # "art." | "arts." | "Ley" — el fundamento debe anclar en norma citable.
        assert re.search(r"\barts?\.|\bLey\b", fundamento), (
            f"{regla.key}: fundamento sin referencia a artículo o ley: "
            f"{fundamento!r}"
        )


# ---------------------------------------------------------------------------
# Reglas mal formadas: fallar ruidosamente, jamás ignorar en silencio.
# ---------------------------------------------------------------------------


def _rule_set(rules: dict[str, Any]) -> RuleSet:
    return RuleSet(
        id=uuid4(),
        domain="red_flag",
        key="rota",
        version=1,
        vigencia_desde=date(2020, 1, 1),
        vigencia_hasta=None,
        rules=rules,
        fuente_legal=[],
    )


def test_bandera_incompleta_lanza_invalid_rule() -> None:
    rota = _rule_set({"id": "rota", "severidad": "block"})  # sin condicion
    with pytest.raises(InvalidRuleError):
        evaluar_banderas([rota], _gasto())


def test_condicion_mal_tipada_lanza_invalid_rule() -> None:
    """Una `condicion` que no es objeto no puede evaluarse — ni ignorarse."""
    rota = _rule_set(
        {
            "id": "rota",
            "severidad": "block",
            "condicion": "es_personal == true",  # string, no cláusula
            "mensaje": "x",
            "fundamento": "art. 31 LIR",
        }
    )
    with pytest.raises(InvalidRuleError):
        evaluar_banderas([rota], _gasto())


def test_severidad_desconocida_lanza_invalid_rule() -> None:
    """Una severidad no soportada no puede degradarse a 'warn' por defecto:
    si en realidad era un bloqueo, degradarla lo apaga."""
    rota = _rule_set(
        {
            "id": "rota",
            "severidad": "critico",
            "condicion": {"field": "es_personal", "op": "eq", "value": True},
            "mensaje": "x",
            "fundamento": "art. 31 LIR",
        }
    )
    with pytest.raises(InvalidRuleError):
        evaluar_banderas([rota], _gasto())
