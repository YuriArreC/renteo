# Renteo

Optimización tributaria proactiva para PYMEs y contadores en Chile. Motor
tributario único, dos UX (cliente A: PYME / mediana; cliente B: contador /
estudio).

> Ver `CLAUDE.md` para reglas no negociables y `.claude/skills/` para el
> contrato funcional, tributario, legal y técnico.

## Monorepo

```
renteo/
├── apps/
│   ├── web/              # Next.js 15 (App Router) + React 19 + Tailwind + shadcn/ui
│   └── api/              # FastAPI 0.115 + SQLAlchemy 2 async + Pydantic v2
├── packages/
│   └── shared-types/     # TS types generados desde Pydantic
├── supabase/
│   ├── migrations/
│   └── seeds/
└── .claude/skills/       # 11 skills (cumplimiento, motor, datos, UX, etc.)
```

## Setup

Requisitos: Node ≥ 20.11, pnpm 9, Python 3.12.

```bash
pnpm install
pnpm dev          # apps/web + apps/api en paralelo
pnpm lint
pnpm typecheck
pnpm test
```

## CI/CD

GitHub Actions corre en cada PR a `main` y en push a `main`:

| Job | Qué valida |
|---|---|
| `lint-api` | ruff (line 88) + mypy strict en `apps/api/src` |
| `test-no-hardcoded` | scan de literales tributarios prohibidos en `domain/tax_engine` (skill 11) |
| `test-api-unit` | pytest unit + coverage informativo en `domain/tax_engine` |
| `test-api-integration` | levanta Supabase local, aplica migraciones, corre tests de RLS + resolver + snapshot + doble firma + `validate_rules.py` |
| `lint-web` / `build-web` | eslint + tsc + `next build` con env placeholder |

Coverage gate `≥85%` está documentado pero corre como informativo en fase 0
hasta que el motor tenga seeds y funciones suficientes (fase 1+).

## Deploy preview

- **Web (`apps/web`):** Vercel se configura manualmente al conectar el repo
  (auto-detecta Next.js + monorepo con root `apps/web`). Vercel publica un
  preview por PR; sin workflow propio en GitHub Actions.
- **API (`apps/api`):** Render o Fly.io con region `sa-east-1` (latencia SII).
  Deploy preview por PR queda para fase 8 (hardening + go-live).
- **Supabase migraciones:** previewing real con preview branches requiere
  Supabase Pro. En fase 0/1 las migraciones se validan localmente vía
  `supabase start` (lo que hace el job `test-api-integration` en CI).

## Stack

- **Frontend:** Next.js 15, React 19, TypeScript strict, Tailwind, shadcn/ui,
  TanStack Query v5, Zustand, Zod, react-hook-form, Recharts, next-intl
  (es-CL).
- **Backend:** Python 3.12, FastAPI, SQLAlchemy 2 async, Pydantic v2,
  structlog, HTTPX, Celery + Redis.
- **DB / Auth / Storage:** Supabase managed (Postgres 15 + Auth + RLS +
  Storage).
- **SII:** SimpleAPI (primario), BaseAPI (backup), ApiGateway (alternativo).
  Certificados digitales en AWS KMS (sa-east-1).
- **Infra:** Vercel (web), Render/Fly.io en sa-east-1 (api), Cloudflare DNS,
  Sentry, Datadog.
