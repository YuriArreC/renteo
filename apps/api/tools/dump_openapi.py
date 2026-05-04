"""Genera apps/api/openapi.json desde la app FastAPI.

Uso:
    cd apps/api
    python tools/dump_openapi.py [output_path]

Default escribe a `apps/api/openapi.json`. CI corre este script y luego
`openapi-typescript` para generar `apps/web/src/lib/api.generated.ts`.
Si el output difiere del committed, `git diff --exit-code` rompe el
build — los tipos shared deben commitear sincronizados.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from src.main import app


def _output_path() -> Path:
    if len(sys.argv) > 1:
        return Path(sys.argv[1])
    here = Path(__file__).resolve().parent
    return here.parent / "openapi.json"


def main() -> int:
    target = _output_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    schema = app.openapi()
    target.write_text(
        json.dumps(schema, indent=2, sort_keys=True, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )
    print(f"OpenAPI schema written to {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
