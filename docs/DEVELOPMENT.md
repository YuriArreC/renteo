# Guía de desarrollo — Renteo

De cero a stack corriendo en ~15 minutos. Si algo no funciona como
está descrito, abrí un PR a este archivo: cada vez que un dev nuevo
se traba en un paso es un bug del onboarding.

## Stack en una pantalla

- **Backend**: Python 3.12 · FastAPI · SQLAlchemy 2 async · asyncpg
  · Pydantic v2 · Alembic-style migraciones SQL versionadas en
  `supabase/migrations/`. Tests con pytest (unit + integration +
  golden + RLS).
- **Frontend**: Next.js 15 (App Router) · React 19 · TypeScript
  strict · Tailwind v3 · shadcn/ui · TanStack Query v5 ·
  react-hook-form · zod · next-intl. Tests con vitest (unit) y
  Playwright (e2e).
- **DB / Auth**: Supabase (Postgres 15 + GoTrue + Storage). RLS
  multi-tenant en TODAS las tablas con datos de cliente.
- **Workers**: Celery + Redis (memory broker en CI / dev local).
- **Observabilidad**: structlog + Sentry (api, worker, web).
- **CI/CD**: GitHub Actions. Render (backend) + Vercel (frontend).

Para entender las decisiones de producto / dominio, leer
[CLAUDE.md](../CLAUDE.md) — es la fuente de verdad.

## Pre-requisitos

| Tool             | Versión          | Cómo instalar                                    |
| ---------------- | ---------------- | ------------------------------------------------ |
| Python           | ≥ 3.12           | `brew install python@3.12` o pyenv               |
| Node             | ≥ 20.11          | `brew install node@20` o nvm (`nvm use 20`)      |
| pnpm             | 9.12 (exacta)    | `corepack enable` lo selecciona del root         |
| Docker Desktop   | actualizado      | `brew install --cask docker`                     |
| Supabase CLI     | ≥ 1.200          | `brew install supabase/tap/supabase`             |
| git              | cualquier        | preinstalado en macOS / `apt install git`        |

Verificá con:

```bash
python --version    # 3.12.x
node --version      # 20.x
pnpm --version      # 9.12.x
docker --version
supabase --version
```

## Primer setup

```bash
# 1. Clonar
git clone git@github.com:YuriArreC/renteo.git
cd renteo

# 2. Instalar dependencias frontend (monorepo pnpm)
pnpm install --frozen-lockfile

# 3. Instalar dependencias backend (editable, con extras dev)
pip install -e "apps/api[dev]"

# 4. Levantar Supabase local (Postgres + Auth + Storage)
#    Crea contenedores Docker en :54321-54324; aplica TODAS las
#    migraciones de supabase/migrations/* en orden.
supabase start --workdir .

# 5. Variables de entorno locales
#    Backend: las config defaults en src/config.py funcionan
#    para dev local; la única que necesitás es DATABASE_URL.
export DATABASE_URL="postgresql+asyncpg://postgres:postgres@127.0.0.1:54322/postgres"

#    Frontend: copiar el bloque que imprime `supabase status`
#    a apps/web/.env.local:
#      NEXT_PUBLIC_SUPABASE_URL=http://127.0.0.1:54321
#      NEXT_PUBLIC_SUPABASE_ANON_KEY=<anon-key del status>
#      NEXT_PUBLIC_API_URL=http://localhost:8000

# 6. Levantar API y frontend en paralelo (terminales separadas)
# Terminal A:
cd apps/api && uvicorn src.main:app --reload --port 8000

# Terminal B:
pnpm --filter @renteo/web dev
```

Abrir <http://localhost:3000>; <http://localhost:54323> es el Studio
de Supabase para inspeccionar la DB.

## Comandos día a día

### Tests

```bash
# Backend
cd apps/api
python -m pytest tests/unit -q                   # unit puros (sin DB)
python -m pytest tests/integration -q            # requieren supabase up
python -m pytest tests/golden -q                 # cifras tributarias firmadas
python -m pytest --cov=src/domain/tax_engine     # coverage del motor

# Frontend
pnpm --filter @renteo/web test                   # vitest unit
pnpm --filter @renteo/web test:e2e               # Playwright (requiere
                                                 # browsers — correr una
                                                 # vez `pnpm --filter
                                                 # @renteo/web test:e2e:install`)
```

### Lint + types

```bash
# Backend
cd apps/api
python -m ruff check .            # lint
python -m mypy --strict src       # types (strict global en domain/**)

# Frontend
pnpm --filter @renteo/web lint
pnpm --filter @renteo/web typecheck
```

### Regenerar shared types (después de cambiar el contrato API)

```bash
cd apps/api && python tools/dump_openapi.py
pnpm --filter @renteo/web types:gen
```

CI tiene un job (`shared-types-sync`) que falla si commiteaste
cambios en endpoints sin regenerar. Si te corta el merge, esos
dos comandos lo resuelven.

### Stop / restart Supabase local

```bash
supabase stop --workdir .
supabase start --workdir .       # re-aplica migraciones
supabase db reset --linked       # ⚠️ destruye datos; solo si querés
                                 # empezar desde cero
```

## Layout del repo

```
renteo/
├── apps/
│   ├── api/                # FastAPI + SQLAlchemy + Celery
│   │   ├── src/
│   │   │   ├── domain/     # Lógica del motor (tax_engine, sii,
│   │   │   │               # papeles, security, legislation, privacy)
│   │   │   ├── routers/    # Endpoints HTTP
│   │   │   ├── tasks/      # Celery tasks
│   │   │   ├── lib/        # Helpers genéricos (audit, errors, jwt,
│   │   │   │               # legal_texts, observability, rule_schema)
│   │   │   ├── auth/       # Tenancy + JWT verification
│   │   │   ├── config.py
│   │   │   ├── db.py       # Session helpers (tenant_session,
│   │   │   │               # service_session)
│   │   │   ├── main.py
│   │   │   └── worker.py   # Celery app + beat schedule
│   │   ├── tests/          # unit | integration | golden | e2e_int
│   │   └── tools/          # dump_openapi, validate_rules, smoke_post_deploy
│   └── web/                # Next.js 15 frontend
│       ├── src/
│       │   ├── app/        # App Router pages
│       │   ├── components/ # Componentes UI
│       │   └── lib/        # api client, supabase, hooks, auth-errors
│       ├── e2e/            # Playwright tests
│       └── messages/       # i18n es-CL
├── supabase/
│   ├── config.toml
│   └── migrations/         # SQL versionadas <YYYYMMDDHHMMSS>_<nombre>.sql
├── docs/                   # DEPLOY, RUNBOOK, REVISION_CONTADOR_SOCIO,
│                           # DEVELOPMENT (este archivo)
├── render.yaml             # Blueprint Render
├── CLAUDE.md               # Política de producto / dominio
├── TODOS-CONTADOR.md       # Items pendientes de firma profesional
└── CHANGELOG.md
```

## Workflows comunes

### Agregar un endpoint nuevo

1. Definir el handler en `apps/api/src/routers/<modulo>.py` con
   `Depends(current_tenancy)` para que extraiga workspace_id del JWT.
2. Registrar el router en `apps/api/src/main.py`.
3. Si toca tablas nuevas, agregar migración (ver siguiente sección).
4. Test integration en `apps/api/tests/integration/test_<modulo>.py`
   con la fixture `http_client_*` y `_override_jwt`.
5. Regenerar shared types (`dump_openapi` + `types:gen`).
6. Si la UI lo consume, agregar el cliente en
   `apps/web/src/lib/api.ts` y los componentes correspondientes.

Convenciones:

- Endpoints multi-tenant: `workspace_id` SIEMPRE viene de
  `tenancy.workspace_id` (JWT), nunca del payload.
- Errores tributarios tipados (`IneligibleForRegime`,
  `RedFlagBlocked`, `SiiUnavailable`, etc.) con mapeo HTTP en
  `main.py`.
- Audit log con `log_audit()` para toda mutación de datos cliente.

### Agregar una migración

1. Crear `supabase/migrations/<YYYYMMDDHHMMSS>_<nombre>.sql`. El
   timestamp debe ser monotónico (Supabase aplica en orden).
2. Headers obligatorios: comentario con `Migration:`, `Skills:`,
   `Purpose:`. Mirá las migraciones existentes para el patrón.
3. Tablas con datos de cliente: RLS habilitado + policy por
   workspace.
4. Aplicar local: `supabase db reset --linked` (destructivo) o
   simplemente `supabase stop && supabase start`.
5. Test de aislamiento RLS en
   `apps/api/tests/integration/test_rls_exhaustivo.py`.

Las migraciones son **forward-only**. Para revertir un cambio,
escribir una nueva migración que corrija. Nunca editar una migración
ya commiteada (rompe el orden histórico).

### Agregar una palanca al simulador (skill 8)

Mirá el último ejemplo: `track_palancas_p7_p12` (commit
`feat(simulator): completar palancas P7-P12`).

Pasos:

1. Topes nuevos en `tax_params.beneficios_topes` (migración).
2. Lista blanca: nueva versión de `recomendacion_whitelist` con
   doble firma (track 11). Cierra v1 con `vigencia_hasta` y publica
   v2 con la palanca nueva.
3. Backend (`apps/api/src/routers/scenario.py`):
   - Agregar field a `Palancas` Pydantic.
   - Agregar a `PalancaTopes` + `_load_topes`.
   - Branch en `_apply_palancas` con su `PalancaImpacto` y banderas.
   - Eligibility check en `_validate_eligibility` si aplica.
   - Plan de acción texto en `_compute_plan_accion`.
4. Tests integration: aplicada con tope, no aplicada por régimen
   incompatible, banderas rojas.
5. Frontend `apps/web/src/app/dashboard/simulator/ScenarioSimulator.tsx`:
   - Field en el zod schema + defaultValues + buildPalancas.
   - Input UI con su label y hint.
6. i18n labels en `apps/web/messages/es-CL.json`.

### Publicar una regla declarativa (skill 11 — doble firma)

1. Draft: `POST /api/admin/rules` con `domain`, `key`, `version`,
   `vigencia_desde`, `rules` (JSON), `fuente_legal`. Crea fila con
   `status='draft'`.
2. Validar schema: `POST /api/admin/rules/validate-schema` corre el
   JSON Schema correspondiente al domain.
3. Dry-run: `POST /api/admin/rules/{id}/dry-run` evalúa la regla
   contra los golden cases existentes y reporta delta.
4. Firma contador: `POST /api/admin/rules/{id}/sign-contador` —
   debe estar logueado un user de `INTERNAL_ADMIN_EMAILS`. Pasa a
   `status='pending_approval'`.
5. Firma admin (segunda firma, user distinto):
   `POST /api/admin/rules/{id}/publish`. El constraint
   `rule_sets_double_sig_check` exige firmantes distintos. Pasa a
   `status='published'` con `vigencia_desde`.

UI: `/admin/rules/new` y `/admin/rules/{id}` cubren todo el flujo.

### Deprecar una regla

`POST /api/admin/rules/{id}/deprecate` setea
`status='deprecated'` + `vigencia_hasta=now()`. El motor usa
automáticamente la versión anterior vigente al recompute.

## Capas de testing

| Layer        | Ubicación                          | Requiere DB | Marker pytest |
| ------------ | ---------------------------------- | ----------- | ------------- |
| Unit         | `tests/unit/*`                     | no          | (default)     |
| Integration  | `tests/integration/test_*.py`     | sí          | `integration` |
| RLS          | `tests/integration/test_rls_*.py` | sí          | `rls`         |
| Golden       | `tests/golden/*`                   | sí          | `golden`      |
| E2E web      | `apps/web/e2e/*.spec.ts`           | no en CI    | (Playwright)  |

CI corre los tres backend en un solo run con `--cov-fail-under=85`.
Los golden están en `xfail` hasta que el contador socio firme (ver
`docs/REVISION_CONTADOR_SOCIO.md`).

## Troubleshooting

| Síntoma                                                      | Causa probable / fix                                                                                                                                  |
| ------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| `supabase start` cuelga en "Starting database..."            | Docker Desktop no está corriendo. Abrirlo y reintentar.                                                                                              |
| `pip install -e "apps/api[dev]"` falla por `psycopg`         | Python < 3.12 detectado. Verificar `python --version`.                                                                                              |
| `pnpm install` instala lockfiles diferentes                  | Estás usando npm en `apps/web` accidentalmente. Usar `pnpm` desde la raíz.                                                                           |
| `mypy --strict` se queja de `untyped-decorator` en Celery   | El stub correcto vive en `# type: ignore[untyped-decorator]`. Mirar `src/tasks/alertas.py` para el patrón.                                            |
| Test integration falla con "Task attached to different loop"| Importaste `src.main` antes de declarar `pytest_asyncio` mode session. Usá las fixtures de `tests/integration/conftest.py`.                          |
| CI bloqueado por `shared-types-sync`                         | Cambiaste el contrato API sin regenerar tipos. Correr `python apps/api/tools/dump_openapi.py` + `pnpm --filter @renteo/web types:gen` y commitear.   |
| `test_no_hardcoded` falla                                    | Plantaste un literal numérico tributario en `src/domain/tax_engine`. Mover a `tax_params.beneficios_topes` o agregar `# tax-magic-number-allow:`.    |
| Playwright falla con "Cannot find browser"                   | Falta instalación. Correr `pnpm --filter @renteo/web exec playwright install --with-deps chromium`.                                                  |
| Sentry warning sobre Turbopack en `next dev`                 | Esperado. Production build (sin `--turbo`) sí carga Sentry completo.                                                                                  |

## Pointers a otros docs

| Doc                                              | Cuándo leerlo                                                          |
| ------------------------------------------------ | ---------------------------------------------------------------------- |
| [CLAUDE.md](../CLAUDE.md)                       | Política de producto, skills, prohibiciones, validación pre-merge.    |
| [docs/DEPLOY.md](./DEPLOY.md)                   | Primer deploy a Render + Supabase prod + Vercel.                       |
| [docs/RUNBOOK.md](./RUNBOOK.md)                 | Incidentes operacionales (SII caído, watchdog stuck, latencia, etc.). |
| [docs/REVISION_CONTADOR_SOCIO.md](./REVISION_CONTADOR_SOCIO.md) | Checklist firmable; saca el motor del estado placeholder. |
| [TODOS-CONTADOR.md](../TODOS-CONTADOR.md)       | Items pendientes de firma profesional (contador socio + estudio jurídico). |
| [.claude/skills/*](../.claude/skills/)          | Decisiones de dominio por skill — leerlas antes de tocar el motor.     |

## Convenciones implícitas

- **Mensajes commit**: `<scope>(<area>): <título>` en es-CL.
  Ejemplos: `feat(simulator):`, `fix(empresas):`, `test(rls):`,
  `chore(types):`, `docs(contador):`. Los commits del repo siguen
  este patrón.
- **Co-author**: cada commit hecho por Claude lleva el trailer
  `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>`.
- **PRs**: nadie merge a `main` sin CI verde + review humano. La
  rama `master` quedó como rastreo histórico; se trabaja en `main`.
- **es-CL**: la app y los commits van en español de Chile. Sin
  voseo, sin tuteo argentino. La lengua del código sigue siendo
  inglés (variables, classes, errors).
