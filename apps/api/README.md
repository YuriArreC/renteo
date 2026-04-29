# Renteo API

Backend Python 3.12 + FastAPI + SQLAlchemy 2 (async) + Pydantic v2.

## Setup local

```bash
python -m venv .venv
. .venv/Scripts/activate   # Windows
pip install -e ".[dev]"
cp .env.example .env       # llenar valores locales
```

## Comandos

```bash
pnpm --filter @renteo/api dev        # uvicorn con reload en :8000
pnpm --filter @renteo/api lint       # ruff
pnpm --filter @renteo/api typecheck  # mypy
pnpm --filter @renteo/api test       # pytest
```

## Estructura

```
src/
├── main.py            # FastAPI app
├── config.py          # settings (pydantic-settings)
├── deps.py            # dependencies (auth/tenancy en fase 0C)
├── db.py              # async engine + session factory
├── auth/              # JWT + tenancy + RBAC (fase 0C)
├── domain/
│   ├── tax_engine/    # motor — sin números mágicos (skill 11)
│   ├── empresas/
│   ├── sii_integration/
│   ├── recommendations/
│   ├── scenarios/
│   ├── alerts/
│   └── privacy/
├── routers/           # FastAPI routers
├── adapters/          # SimpleAPI / BaseAPI / KMS / S3
├── workers/           # Celery
└── lib/               # errors, logging, audit
tests/
├── unit/
├── integration/
└── golden/            # casos validados por contador socio
```
