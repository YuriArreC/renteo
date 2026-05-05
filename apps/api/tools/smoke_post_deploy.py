"""Smoke test post-deploy.

Pega contra una URL desplegada y verifica que la app responde.
Pensado para correr como `postDeployCommand` en Render o como step
de CI después de un deploy preview.

Uso:
    python tools/smoke_post_deploy.py https://renteo-api.onrender.com

Exit codes:
    0 — todos los checks pasan
    1 — algún check falla; el body del fail va a stderr para que el
        pipeline lo capture
"""

from __future__ import annotations

import sys
from urllib.parse import urljoin

import httpx

_TIMEOUT_SECONDS = 30.0


def _check(client: httpx.Client, base_url: str, path: str) -> bool:
    url = urljoin(base_url, path)
    try:
        response = client.get(url)
    except httpx.HTTPError as exc:
        print(f"[FAIL] {path} → {type(exc).__name__}: {exc}", file=sys.stderr)
        return False
    if response.status_code >= 500:
        print(
            f"[FAIL] {path} → HTTP {response.status_code}\n"
            f"       body: {response.text[:200]}",
            file=sys.stderr,
        )
        return False
    print(
        f"[ OK ] {path} → HTTP {response.status_code} "
        f"({response.elapsed.total_seconds() * 1000:.0f} ms)"
    )
    return True


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(
            "uso: smoke_post_deploy.py <base_url>\n"
            "ej.: python tools/smoke_post_deploy.py "
            "https://renteo-api.onrender.com",
            file=sys.stderr,
        )
        return 1
    base_url = argv[1].rstrip("/") + "/"

    print(f"Smoke test contra {base_url}")
    with httpx.Client(timeout=_TIMEOUT_SECONDS) as client:
        results = [
            _check(client, base_url, "/healthz"),
            _check(client, base_url, "/readyz"),
        ]
    if not all(results):
        print("\nSmoke test FAILED", file=sys.stderr)
        return 1
    print("\nSmoke test OK")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
