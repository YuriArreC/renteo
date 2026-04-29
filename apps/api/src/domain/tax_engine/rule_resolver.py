"""Selector de regla vigente — el motor pasa por aquí para resolver reglas.

Contrato (skill 11):
- El motor NO conoce años específicos. Recibe `tax_year` y consulta reglas.
- Si no hay regla publicada para el año pedido, MissingRuleError. Bloqueo.
- Si hay solapamiento, gana `vigencia_desde` más reciente; en empate, mayor
  `version`. Esto soporta publicar transiciones legislativas con anticipación.
"""

from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.lib.errors import MissingRuleError


class RuleSet(BaseModel):
    """Subset de tax_rules.rule_sets necesario para evaluación."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    domain: str
    key: str
    version: int
    vigencia_desde: date
    vigencia_hasta: date | None
    rules: dict[str, Any]
    fuente_legal: list[dict[str, Any]]


async def resolve_rule(
    session: AsyncSession,
    domain: str,
    key: str,
    tax_year: int,
) -> RuleSet:
    """Retorna la versión publicada cuya vigencia incluye el ejercicio.

    Args:
        session: AsyncSession con request.jwt.claims seteado (RLS).
        domain: dominio de la regla (ej. 'regime_eligibility').
        key: identificador estable dentro del dominio (ej. '14_d_3').
        tax_year: año tributario consultado; el ejercicio comercial cierra
            el 31 de diciembre, ese día sirve de target_date.

    Raises:
        MissingRuleError: no hay regla publicada cuya vigencia cubra
            tax_year. Bloqueo total: nada se calcula sin regla.
    """
    target_date = date(tax_year, 12, 31)
    result = await session.execute(
        text(
            """
            select id, domain, key, version,
                   vigencia_desde, vigencia_hasta,
                   rules, fuente_legal
              from tax_rules.rule_sets
             where domain = :domain
               and key = :key
               and status = 'published'
               and vigencia_desde <= :target_date
               and (vigencia_hasta is null or vigencia_hasta >= :target_date)
             order by vigencia_desde desc, version desc
             limit 1
            """
        ),
        {"domain": domain, "key": key, "target_date": target_date},
    )
    row = result.mappings().one_or_none()
    if row is None:
        raise MissingRuleError(
            f"No published rule for ({domain!r}, {key!r}) at tax_year {tax_year}"
        )
    return RuleSet.model_validate(dict(row))
