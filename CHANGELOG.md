# Changelog

Sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y semver.
Los commits siguen Conventional Commits.

## [Unreleased]

### Added

#### Bloque 0A — Monorepo y bootstrap

- pnpm workspaces + Turborepo con pipelines `lint`, `typecheck`, `test`,
  `build`, `dev`.
- `apps/web` (Next.js 15 App Router + React 19 + TypeScript strict +
  Tailwind v3 + shadcn/ui base + next-intl es-CL single-locale).
- `apps/api` (Python 3.12 + FastAPI 0.115 + SQLAlchemy 2 async + Pydantic
  v2 + structlog + httpx + pyjwt + boto3 + Celery) con estructura de
  carpetas del skill 10.
- `packages/shared-types` scaffold para generación TS desde Pydantic.
- Lint global ruff (line 88) + mypy strict global con override extra-strict
  para `src.domain.*`.
- TypeScript strict + `noUncheckedIndexedAccess` heredado desde
  `tsconfig.base.json`.

#### Bloque 0B — Supabase + schemas + RLS

- 11 migraciones secuenciales en `supabase/migrations/` que cubren los
  schemas `core`, `tax_params`, `tax_data`, `tax_calc`, `security`,
  `privacy`, `tax_rules` + schema interno `app` con helpers de RLS que
  leen del JWT (`app.workspace_id()`, `app.user_role()`,
  `app.empresa_ids()`, `app.has_empresa_access()`).
- Trigger anti-UPDATE/DELETE/TRUNCATE en `security.audit_log`.
- Trigger anti-UPDATE en columnas snapshot (`engine_version`,
  `rule_set_snapshot`, `tax_year_params_snapshot`) de las 3 tablas de
  cálculo (`rli_calculations`, `escenarios_simulacion`,
  `recomendaciones`).
- CHECK constraint que exige doble firma + firmantes distintos al publicar
  reglas en `tax_rules.rule_sets`.
- RLS habilitado en TODAS las tablas con datos de usuario; `tax_params.*`
  y `tax_rules.*` con SELECT abierto a `authenticated`.
- GRANTs explícitos a `authenticated` y `alter default privileges` para
  tablas futuras.

#### Bloque 0C — Auth + tenancy + tests RLS

- `apps/api/src/auth/jwt.py` con verificación JWT + JWKS cache 1h (RS256).
- `apps/api/src/auth/tenancy.py` con `Tenancy` Pydantic frozen y dep
  `current_tenancy` desde `app_metadata`.
- `apps/api/src/auth/permissions.py` con `require_role` y
  `require_empresa_access` (alineados a `app.has_empresa_access` SQL).
- `apps/api/src/db.py` con `tenant_session(claims)` async ctx que ejecuta
  `set local request.jwt.claims = ...` para que RLS evalúe.
- 4 tests bloqueantes de aislamiento multi-tenant en
  `tests/integration/test_rls_isolation.py` (workspace + workspaces table
  + accountant_staff sin / con asignación).
- Frontend Supabase SSR: `client.ts` (browser), `server.ts` (server con
  `cookies()`), `middleware.ts` (refresh de sesión vía `getUser()`).

#### Bloque 0D — Versionado de reglas tributarias (skill 11)

- 5 JSON Schemas autocontenidos en
  `apps/api/src/domain/tax_engine/rule_schemas/` para los dominios
  `regime_eligibility`, `palanca_definition`, `red_flag`, `rli_formula`,
  `credit_imputation_order`.
- `rule_resolver.resolve_rule(session, domain, key, tax_year)` con
  selector por vigencia y `MissingRuleError` si no hay regla publicada.
- `rule_evaluator.evaluate(rule, ctx)` con 12 operadores
  (`eq, neq, lt, lte, gt, gte, between, in, not_in, exists, not_exists,
  matches_regex`) y 3 combinadores (`all_of, any_of, not`). Sin `eval`,
  sin lambdas, sin código arbitrario.
- 26+ tests unitarios del evaluator y 3 tests integration del resolver.
- 6 tests integration que verifican inmutabilidad de snapshots y CHECK
  de doble firma.
- `apps/api/legal-dependencies.yaml` placeholder con estructura comentada.
- `supabase/migrations/_template_tax_rule.sql.example` con SQL plantilla
  para publicar reglas con doble firma + golden cases.

#### Bloque 0E — CI/CD

- `.github/workflows/ci.yml` con jobs `lint-api`, `test-no-hardcoded`,
  `test-api-unit`, `test-api-integration` (levanta Supabase local +
  ejecuta `validate_rules.py`), `lint-web`, `build-web`.
- `apps/api/tests/test_no_hardcoded.py` bloqueante (skill 11) con scanner
  regex sobre `domain/tax_engine` + tests del propio scanner (limpio
  pasa, plantado falla, marcador `# noqa: tax-magic-number` exime).
- `apps/api/tools/validate_rules.py`: para cada regla publicada valida
  schema, fuente_legal, vigencia, ≥3 golden cases.

#### Bloque 0F — Landing pública

- Landing `/` Server Component con hero, 3 features y nota de
  cumplimiento; cero claims tributarios cuantitativos.
- `/legal/privacidad` y `/legal/terminos` placeholders v1 (es-CL,
  `robots: noindex`, banner explícito de versión preliminar).
- Componente `Footer_Shared` compartido.
- Copy centralizado en `apps/web/messages/es-CL.json` consumido vía
  next-intl `getTranslations()`.

#### Bloque 0G — Documentación

- `CHANGELOG.md` (este archivo).
- `CHANGELOG-LEGAL.md` con entry v1 preliminar.
- `TODOS-CONTADOR.md` con bloqueantes para fase 1, encolados para fase
  3-4, y pendientes pre-go-live.

### Notas de fase 0

- No se ejecutaron `pnpm install` ni `pip install` durante la
  construcción; la verificación end-to-end ocurre en la primera corrida
  del workflow CI.
- Coverage `≥85%` documentado pero corre como informativo en fase 0;
  enforcement real entra cuando el motor tenga seeds (fase 1+).
- Migraciones Supabase no se aplicaron localmente; `supabase start` en CI
  o local valida que apliquen clean.
- Reglas tributarias declarativas: 0 cargadas. El motor está listo, los
  datos los carga el contador socio en fase 1 vía migración + doble firma.
