#!/usr/bin/env python3
"""Setea la contraseña del usuario demo vía Admin API de Supabase.

POR QUÉ NO ESTÁ EN LA MIGRACIÓN
La migración `20260713140000_demo_cerrado.sql` crea el usuario ficticio
`demo@renteo.cl` con el email ya confirmado, pero SIN contraseña: una
credencial no se commitea al repo, ni siquiera la de un demo. Este script la
inyecta en el momento del deploy leyéndola del entorno.

Es idempotente: correrlo dos veces deja la misma contraseña.

USO
    export SUPABASE_URL=https://<proyecto>.supabase.co
    export SUPABASE_SERVICE_ROLE_KEY=<service_role key>   # NO la anon key
    export DEMO_USER_PASSWORD='<contraseña del demo>'
    python scripts/set_demo_password.py

La service_role key es un secreto de administrador: sale del dashboard de
Supabase (Settings → API) y no debe quedar en el shell history ni en el repo.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

# Debe coincidir con el UUID seedeado en 20260713140000_demo_cerrado.sql.
DEMO_USER_ID = "00000000-0000-0000-0000-00000000de01"
DEMO_EMAIL = "demo@renteo.cl"

MIN_PASSWORD_LEN = 12


def _require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        sys.exit(
            f"ERROR: falta la variable de entorno {name}.\n"
            f"Ver el docstring de este script o docs/DEMO-PROD.md."
        )
    return value


def main() -> None:
    supabase_url = _require_env("SUPABASE_URL").rstrip("/")
    service_key = _require_env("SUPABASE_SERVICE_ROLE_KEY")
    password = _require_env("DEMO_USER_PASSWORD")

    if len(password) < MIN_PASSWORD_LEN:
        sys.exit(
            f"ERROR: DEMO_USER_PASSWORD tiene {len(password)} caracteres; "
            f"se exigen al menos {MIN_PASSWORD_LEN}. La cuenta demo vive en "
            f"producción: no le pongas una contraseña de juguete."
        )

    endpoint = f"{supabase_url}/auth/v1/admin/users/{DEMO_USER_ID}"
    payload = json.dumps(
        {"password": password, "email_confirm": True}
    ).encode()

    request = urllib.request.Request(
        endpoint,
        data=payload,
        method="PUT",
        headers={
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Content-Type": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = json.loads(response.read())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        if exc.code == 404:
            sys.exit(
                f"ERROR 404: el usuario {DEMO_USER_ID} no existe en este "
                f"proyecto. ¿Aplicaste las migraciones "
                f"(supabase db push) antes de correr esto?"
            )
        sys.exit(f"ERROR {exc.code} desde Supabase: {detail}")
    except urllib.error.URLError as exc:
        sys.exit(f"ERROR de red hacia {supabase_url}: {exc.reason}")

    if body.get("email") != DEMO_EMAIL:
        sys.exit(
            f"ERROR: el usuario {DEMO_USER_ID} tiene email "
            f"{body.get('email')!r}, no {DEMO_EMAIL!r}. Se aborta: ese UUID "
            f"pertenece a otra cuenta y cambiarle la contraseña sería un "
            f"secuestro accidental."
        )

    print(f"OK: contraseña actualizada para {DEMO_EMAIL} ({DEMO_USER_ID}).")
    print(
        "Recuerda que el acceso además exige que ese email esté en "
        "ALLOWED_USER_EMAILS de la API."
    )


if __name__ == "__main__":
    main()
