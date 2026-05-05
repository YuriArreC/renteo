# Renteo

Optimización tributaria proactiva para PYMEs y contadores en Chile. Motor
tributario único, dos UX (cliente A: PYME / mediana; cliente B: contador /
estudio).

> Política de producto, skills y prohibiciones: [CLAUDE.md](./CLAUDE.md).

## Documentación

| Doc | Cuándo leerlo |
|-----|---------------|
| [docs/DEVELOPMENT.md](./docs/DEVELOPMENT.md) | Levantar el stack local en 15 min, comandos día a día, workflows comunes (agregar palanca, regla, migración), troubleshooting. **Empezá acá.** |
| [docs/DEPLOY.md](./docs/DEPLOY.md) | Primer deploy a Render + Supabase prod + Vercel + AWS (KMS/S3). |
| [docs/RUNBOOK.md](./docs/RUNBOOK.md) | Incidentes operacionales (SII caído, watchdog stuck, latencia, audit_log unbounded, etc.). |
| [docs/REVISION_CONTADOR_SOCIO.md](./docs/REVISION_CONTADOR_SOCIO.md) | Checklist firmable por el contador socio — saca el motor del estado placeholder. |
| [TODOS-CONTADOR.md](./TODOS-CONTADOR.md) | Items pendientes de firma profesional (contador socio + estudio jurídico). |
| [CLAUDE.md](./CLAUDE.md) | Reglas no negociables del producto. Lectura obligada antes de tocar el motor. |
| [.claude/skills/](./.claude/skills/) | Decisiones de dominio por skill (1-11). |

## Stack en una pantalla

- **Frontend**: Next.js 15 + React 19 + TypeScript strict + Tailwind +
  shadcn/ui + TanStack Query v5 + zod + react-hook-form + next-intl es-CL.
- **Backend**: Python 3.12 + FastAPI + SQLAlchemy 2 async + asyncpg +
  Pydantic v2 + structlog + Celery + Redis.
- **DB / Auth / Storage**: Supabase (Postgres 15 + GoTrue + Storage). RLS
  multi-tenant en TODAS las tablas con datos cliente.
- **SII**: SimpleAPI (primario), BaseAPI (backup), ApiGateway (alternativo).
  Mock determinístico en dev/CI.
- **Custodia certificado digital**: AWS KMS + S3 (sa-east-1) en prod;
  mocks en CI.
- **Infra**: Render (api + worker + beat) · Vercel (web) · Sentry · Datadog.

## Setup rápido

```bash
git clone git@github.com:YuriArreC/renteo.git && cd renteo
pnpm install --frozen-lockfile
pip install -e "apps/api[dev]"
supabase start --workdir .
pnpm dev   # apps/web + apps/api en paralelo
```

Documentación completa de setup en [docs/DEVELOPMENT.md](./docs/DEVELOPMENT.md).

## CI/CD

GitHub Actions corre en cada PR y push a `main`:

| Job | Qué valida |
|---|---|
| `lint-api` | ruff + mypy strict en `apps/api/src` |
| `test-no-hardcoded` | scan literales tributarios en `domain/tax_engine` (skill 11) |
| `test-api-unit` | pytest unit + coverage |
| `test-api-integration` | Supabase local + migraciones + integration + RLS + golden + `validate_rules.py`. Coverage gate `≥85%`. |
| `lint-web` / `build-web` | eslint + tsc + `next build` |
| `e2e-web` | Playwright smoke público (sin backend) |
| `shared-types-sync` | openapi.json + api.generated.ts sincronizados |

Bloqueadores formales pre-merge (CLAUDE.md): tests golden, RLS, coverage,
lint + mypy strict en `domain/**`.

## Estado actual

Skills 1-11 al 100%. Bloqueador real para go-live: firma del contador socio
sobre los goldens (ver [docs/REVISION_CONTADOR_SOCIO.md](./docs/REVISION_CONTADOR_SOCIO.md)).
