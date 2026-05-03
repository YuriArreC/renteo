"""Lookup de textos legales versionados (skill 2).

Track 2: los disclaimers, consentimientos, T&C y política de privacidad
viven en `privacy.legal_texts` con vigencia temporal. Cualquier output
del motor que requiera mostrar texto legal lo lee de aquí — nunca
hardcodear.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True)
class LegalText:
    key: str
    version: str
    body: str
    effective_from: str  # ISO date


class LegalTextNotFound(Exception):
    """No hay texto legal vigente publicado para `key` en la fecha pedida."""


async def get_legal_text(
    session: AsyncSession,
    key: str,
    on_date: date | None = None,
) -> LegalText:
    """Devuelve el texto vigente de `key` en `on_date` (default hoy).

    Si hay solapamiento (raro), gana la `effective_from` más reciente.
    """
    target = on_date or date.today()
    result = await session.execute(
        text(
            """
            select key, version, body, effective_from
              from privacy.legal_texts
             where key = :k
               and effective_from <= :t
               and (effective_to is null or effective_to >= :t)
             order by effective_from desc, version desc
             limit 1
            """
        ),
        {"k": key, "t": target},
    )
    row = result.mappings().one_or_none()
    if row is None:
        raise LegalTextNotFound(
            f"No legal_text published for key={key!r} on {target.isoformat()}"
        )
    return LegalText(
        key=row["key"],
        version=row["version"],
        body=row["body"],
        effective_from=row["effective_from"].isoformat(),
    )
