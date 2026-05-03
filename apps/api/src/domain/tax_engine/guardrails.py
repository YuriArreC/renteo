"""Guardrails de cumplimiento (skill 1).

La lista blanca de recomendaciones permitidas vive como rule_set
declarativo (`recomendacion_whitelist/global`). Cada palanca aplicada
en el simulador y cada recomendación de cambio de régimen pasa por
`is_recomendacion_whitelisted` antes de consolidarse en el output.

Si un id de recomendación no está en la lista blanca, el motor lo
rechaza con `RedFlagBlocked` — la skill 1 lo trata como bandera
estructural (NGA arts. 4 bis/ter/quáter CT).
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.tax_engine.rule_resolver import resolve_rule


async def get_whitelist_ids(
    session: AsyncSession, tax_year: int
) -> set[str]:
    """Devuelve el set de `id` permitidos para `tax_year`."""
    rule_set = await resolve_rule(
        session, "recomendacion_whitelist", "global", tax_year
    )
    items = rule_set.rules.get("items", [])
    return {str(item["id"]) for item in items if "id" in item}


async def is_recomendacion_whitelisted(
    session: AsyncSession, item_id: str, tax_year: int
) -> bool:
    return item_id in await get_whitelist_ids(session, tax_year)
