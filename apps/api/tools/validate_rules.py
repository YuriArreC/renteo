"""Validador de reglas publicadas (skill 11).

Para cada `tax_rules.rule_sets` con status='published':
  1. JSON Schema del dominio valida el campo `rules`.
  2. `fuente_legal` no está vacío.
  3. Vigencia coherente: `vigencia_hasta > vigencia_desde` cuando hay hasta.
  4. Mínimo 3 casos golden registrados.

Uso:
    DATABASE_URL=postgresql://... python tools/validate_rules.py

Sale con código 1 si hay errores; 0 si todo pasa (incluido el caso
fase-0 con cero reglas publicadas).
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

import asyncpg
import jsonschema

HERE = Path(__file__).resolve().parent
SCHEMAS_DIR = HERE.parent / "src" / "domain" / "tax_engine" / "rule_schemas"


def _load_schema(domain: str) -> dict[str, Any] | None:
    schema_file = SCHEMAS_DIR / f"{domain}.schema.json"
    if not schema_file.exists():
        return None
    return json.loads(schema_file.read_text(encoding="utf-8"))


async def _validate(conn: asyncpg.Connection) -> list[str]:
    errors: list[str] = []
    rows = await conn.fetch(
        """
        select id, domain, key, version,
               vigencia_desde, vigencia_hasta,
               rules, fuente_legal
          from tax_rules.rule_sets
         where status = 'published'
        """
    )

    for row in rows:
        rule_id = f"{row['domain']}/{row['key']}@v{row['version']}"

        # asyncpg returns JSONB as a string by default; parse if so.
        rules = (
            json.loads(row["rules"])
            if isinstance(row["rules"], str)
            else row["rules"]
        )
        fuente = (
            json.loads(row["fuente_legal"])
            if isinstance(row["fuente_legal"], str)
            else row["fuente_legal"]
        )

        # 1. JSON Schema validation
        schema = _load_schema(row["domain"])
        if schema is None:
            errors.append(
                f"{rule_id}: no schema file for domain {row['domain']!r} "
                f"(expected {row['domain']}.schema.json)"
            )
        else:
            try:
                jsonschema.validate(rules, schema)
            except jsonschema.ValidationError as exc:
                errors.append(f"{rule_id}: schema validation failed: {exc.message}")

        # 2. fuente_legal non-empty
        if not fuente:
            errors.append(f"{rule_id}: fuente_legal is empty")

        # 3. vigencia coherente
        if (
            row["vigencia_hasta"] is not None
            and row["vigencia_hasta"] <= row["vigencia_desde"]
        ):
            errors.append(
                f"{rule_id}: vigencia_hasta ({row['vigencia_hasta']}) "
                f"<= vigencia_desde ({row['vigencia_desde']})"
            )

        # 4. ≥3 golden cases
        golden_count = await conn.fetchval(
            "select count(*) from tax_rules.rule_golden_cases "
            "where rule_set_id = $1",
            row["id"],
        )
        if golden_count < 3:
            errors.append(
                f"{rule_id}: only {golden_count} golden cases registered "
                f"(minimum 3 required)"
            )

    return errors


async def main() -> int:
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("DATABASE_URL not set", file=sys.stderr)
        return 2

    # asyncpg expects `postgresql://` (no `+asyncpg`); strip if present.
    asyncpg_url = db_url.replace("postgresql+asyncpg://", "postgresql://")

    conn = await asyncpg.connect(asyncpg_url)
    try:
        errors = await _validate(conn)
    finally:
        await conn.close()

    if errors:
        print("Rule validation failed:", file=sys.stderr)
        for err in errors:
            print(f"  {err}", file=sys.stderr)
        return 1

    print("Rule validation passed.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
