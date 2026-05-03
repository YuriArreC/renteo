"""Snapshots inmutables de cálculo (skill 11 §"Snapshot inmutable").

Cada escenario o recomendación persistida lleva tres campos atados:

- `rule_set_snapshot` (jsonb): dump de las reglas declarativas que el
  motor evaluó al hacer el cálculo (regime_eligibility/14_a, 14_d_3,
  etc., recomendacion_whitelist/global, …).
- `tax_year_params_snapshot` (jsonb): tasas IDPC, tramos IGC, topes
  PPM, beneficios_topes y feature_flags vigentes para el `tax_year`
  pedido.
- `rules_snapshot_hash` (text): SHA-256 de la serialización canónica
  de ambos dumps. Permite verificar que dos cálculos usaron exactamente
  los mismos parámetros sin comparar JSON gigantes.

Si la ley cambia un parámetro mañana, el cálculo de ayer queda con
sus snapshots intactos — recalcular = NUEVO registro, jamás
sobrescribir (los triggers de `app.prevent_snapshot_modification`
bloquean el UPDATE de estos campos).
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Dominios de rule_sets relevantes para escenarios y diagnósticos.
# Track 11c arranca con estos; track 12+ podrá ampliar la lista
# (palanca_definition, rli_formula, credit_imputation_order, …).
_RULE_DOMAINS_KEYS: list[tuple[str, str]] = [
    ("regime_eligibility", "14_a"),
    ("regime_eligibility", "14_d_3"),
    ("regime_eligibility", "14_d_8"),
    ("regime_eligibility", "renta_presunta"),
    ("recomendacion_whitelist", "global"),
]


async def build_snapshots(
    session: AsyncSession, *, tax_year: int
) -> tuple[dict[str, Any], dict[str, Any], str]:
    """Construye (rule_set_snapshot, tax_year_params_snapshot, hash).

    El hash es SHA-256 hex de la serialización canónica (sort_keys,
    sin espacios) de `{"rule_set": ..., "tax_year_params": ...}`.
    Usar este formato garantiza que el mismo conjunto de reglas y
    parámetros produce siempre el mismo hash, sin importar el orden
    en que las queries devolvieron las filas.
    """
    rule_set = await _load_rule_set_snapshot(session, tax_year=tax_year)
    params = await _load_tax_year_params_snapshot(session, tax_year=tax_year)
    canonical = json.dumps(
        {"rule_set": rule_set, "tax_year_params": params},
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return rule_set, params, digest


# ---------------------------------------------------------------------------
# rule_set_snapshot
# ---------------------------------------------------------------------------


async def _load_rule_set_snapshot(
    session: AsyncSession, *, tax_year: int
) -> dict[str, Any]:
    rules: dict[str, Any] = {}
    for domain, key in _RULE_DOMAINS_KEYS:
        result = await session.execute(
            text(
                """
                select id, version, vigencia_desde, vigencia_hasta,
                       rules, fuente_legal
                  from tax_rules.rule_sets
                 where domain = :d
                   and key = :k
                   and status = 'published'
                   and vigencia_desde <= make_date(:y, 12, 31)
                   and (
                        vigencia_hasta is null
                        or vigencia_hasta >= make_date(:y, 12, 31)
                   )
                 order by vigencia_desde desc, version desc
                 limit 1
                """
            ),
            {"d": domain, "k": key, "y": tax_year},
        )
        row = result.mappings().one_or_none()
        if row is None:
            # No hay regla publicada para este dominio en el año pedido.
            # No es un error fatal del snapshot: simplemente queda
            # marcada como ausente para que la auditoría lo detecte.
            rules[f"{domain}/{key}"] = None
            continue
        rules[f"{domain}/{key}"] = {
            "rule_set_id": str(row["id"]),
            "version": row["version"],
            "vigencia_desde": row["vigencia_desde"].isoformat(),
            "vigencia_hasta": (
                row["vigencia_hasta"].isoformat()
                if row["vigencia_hasta"] is not None
                else None
            ),
            "rules": row["rules"],
            "fuente_legal": row["fuente_legal"],
        }
    return rules


# ---------------------------------------------------------------------------
# tax_year_params_snapshot
# ---------------------------------------------------------------------------


async def _load_tax_year_params_snapshot(
    session: AsyncSession, *, tax_year: int
) -> dict[str, Any]:
    """Dump de los parámetros tributarios vigentes para `tax_year`."""
    idpc = await session.execute(
        text(
            """
            select regimen, rate, fuente_legal
              from tax_params.idpc_rates
             where tax_year = :y
             order by regimen
            """
        ),
        {"y": tax_year},
    )
    igc = await session.execute(
        text(
            """
            select tramo, desde_uta, hasta_uta, tasa, rebajar_uta
              from tax_params.igc_brackets
             where tax_year = :y
             order by tramo
            """
        ),
        {"y": tax_year},
    )
    ppm = await session.execute(
        text(
            """
            select regimen, umbral_uf, tasa_bajo, tasa_alto,
                   es_transitoria, fuente_legal
              from tax_params.ppm_pyme_rates
             where tax_year = :y
             order by regimen
            """
        ),
        {"y": tax_year},
    )
    topes = await session.execute(
        text(
            """
            select key, valor, unidad, fuente_legal
              from tax_params.beneficios_topes
             where tax_year = :y
             order by key
            """
        ),
        {"y": tax_year},
    )
    flags = await session.execute(
        text(
            """
            select flag_key, value, effective_from, reason
              from tax_rules.feature_flags_by_year
             where effective_from <= make_date(:y, 12, 31)
             order by flag_key, effective_from desc
            """
        ),
        {"y": tax_year},
    )

    return {
        "tax_year": tax_year,
        "idpc_rates": [dict(r) for r in idpc.mappings().all()],
        "igc_brackets": [dict(r) for r in igc.mappings().all()],
        "ppm_pyme_rates": [dict(r) for r in ppm.mappings().all()],
        "beneficios_topes": [dict(r) for r in topes.mappings().all()],
        "feature_flags": [dict(r) for r in flags.mappings().all()],
    }
