# Deploy de Renteo — guía paso a paso

Stack en producción:

- **Backend (API + worker + beat)** — Render, blueprint `render.yaml`
  en la raíz del repo.
- **Base de datos** — Supabase (Postgres 15 + Auth + Storage).
- **Frontend** — Vercel (`@renteo/web`), conectado al repo con
  monorepo root `apps/web`.
- **Cache / broker Celery** — Render Redis (managed) o Upstash si la
  región lo amerita.
- **Storage de certificados** — S3 en `sa-east-1`, bucket privado
  `renteo-sii-certs-<env>`.
- **KMS** — AWS KMS en `sa-east-1`, una CMK dedicada por entorno.
- **Sentry** — un proyecto por servicio (api, worker, web) en una
  misma org.

## Primer deploy (one-time)

### 1. AWS

1. Crear bucket S3 `renteo-sii-certs-prod` con versioning ON,
   server-side encryption (SSE-KMS) y bloqueo público total.
2. Crear CMK KMS `arn:aws:kms:sa-east-1:<account>:key/<id>` con key
   policy que permita `Encrypt`/`Decrypt` solo al IAM user que usará
   Render. Habilitar key rotation anual.
3. Crear IAM user `renteo-prod-runtime` con policies mínimas:
   `s3:PutObject`, `s3:GetObject`, `s3:DeleteObject` sobre el bucket
   y `kms:Encrypt`/`kms:Decrypt` sobre la CMK. Generar
   access keys → guardarlas para el step Render.

### 2. Supabase

1. Crear proyecto Supabase prod (región `us-east-1` si Render
   `oregon`; latencia aceptable). Postgres 15 plan paid mínimo.
2. Aplicar migraciones:
   ```bash
   supabase link --project-ref <ref>
   supabase db push --linked
   ```
3. Configurar Auth: email/password ON, magic link OFF, redirect URLs
   = `https://renteo.cl/*`, JWT secret rotación anual.
4. Setup `Custom Access Token Hook` (track auth-hook): apuntar al
   schema `auth` y habilitar.
5. Anotar `DATABASE_URL` (postgresql+asyncpg://...) y JWT secret.

### 3. Render

1. Conectar el repo en Render (GitHub integration).
2. New + Blueprint → seleccionar `render.yaml`. Render detecta los
   tres services (API, worker, beat) + envVarGroup.
3. Setear los secrets marcados `sync: false` en el dashboard:
   - `DATABASE_URL` — del paso Supabase.
   - `SUPABASE_JWT_SECRET` y `SUPABASE_JWKS_URL` — del paso Supabase.
   - `SENTRY_DSN` — uno por servicio (api/worker).
   - `SII_KMS_KEY_ARN` — del paso AWS.
   - `SII_CERT_BUCKET` — `renteo-sii-certs-prod`.
   - `SII_SIMPLEAPI_TOKEN` — DPA SimpleAPI firmado.
   - `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` — del IAM user.
   - `REDIS_URL` — del Redis que crees en Render (worker + beat).
4. El primer deploy corre automático. Render hace `pip install -e .`
   + `uvicorn ...`. El healthCheckPath `/readyz` debe responder 200
   o Render hace rollback.

### 4. Vercel (frontend)

1. Importar el repo. Root directory = `apps/web`. Framework =
   Next.js. Install command = `pnpm install --frozen-lockfile`.
   Build command = `pnpm --filter @renteo/web build`.
2. Setear env vars:
   - `NEXT_PUBLIC_API_URL` = `https://renteo-api.onrender.com`.
   - `NEXT_PUBLIC_SUPABASE_URL` y `NEXT_PUBLIC_SUPABASE_ANON_KEY`.
   - `NEXT_PUBLIC_SENTRY_DSN` — distinto del backend (proyecto web).
3. Custom domain `renteo.cl` apuntando a Vercel.

### 5. Smoke post-deploy

```bash
python apps/api/tools/smoke_post_deploy.py https://renteo-api.onrender.com
```

Debe imprimir `Smoke test OK` y exit 0. Render lo puede correr como
`postDeployCommand` (no soportado nativamente; hoy se hace manual o
con un workflow de GitHub Actions que se dispara post-deploy).

## Matriz de variables por servicio

| Variable                     | API | Worker | Beat | Web | Notas                      |
| ---------------------------- | --- | ------ | ---- | --- | -------------------------- |
| `DATABASE_URL`               | ✅   | ✅      | ✅    | ❌   | postgresql+asyncpg          |
| `SUPABASE_JWT_SECRET`        | ✅   | ❌      | ❌    | ❌   | verificar JWT entrante     |
| `SUPABASE_JWKS_URL`          | ✅   | ❌      | ❌    | ❌   | rotación clave              |
| `REDIS_URL`                  | ❌   | ✅      | ✅    | ❌   | broker Celery               |
| `SENTRY_DSN`                 | ✅   | ✅      | ✅    | ❌   | uno por servicio            |
| `NEXT_PUBLIC_SENTRY_DSN`     | ❌   | ❌      | ❌    | ✅   | distinto del backend        |
| `SII_KMS_KEY_ARN`            | ✅   | ✅      | ❌    | ❌   | CMK por entorno             |
| `SII_CERT_BUCKET`            | ✅   | ✅      | ❌    | ❌   | bucket por entorno          |
| `SII_SIMPLEAPI_TOKEN`        | ✅   | ✅      | ❌    | ❌   | DPA firmado                 |
| `KMS_PROVIDER`               | ✅   | ✅      | ❌    | ❌   | `aws` en prod, `mock` en CI |
| `CERT_STORAGE_PROVIDER`      | ✅   | ✅      | ❌    | ❌   | `s3` en prod                |
| `AWS_ACCESS_KEY_ID/SECRET`   | ✅   | ✅      | ❌    | ❌   | IAM dedicado                |
| `INTERNAL_ADMIN_EMAILS`      | ✅   | ❌      | ❌    | ❌   | staff Renteo                |
| `CORS_ALLOWED_ORIGINS`       | ✅   | ❌      | ❌    | ❌   | dominio frontend            |
| `NEXT_PUBLIC_API_URL`        | ❌   | ❌      | ❌    | ✅   | URL pública de la API       |
| `NEXT_PUBLIC_SUPABASE_URL`   | ❌   | ❌      | ❌    | ✅   |                             |

## Promociones entre entornos

- `main` → preview (Render preview env por PR + Vercel preview por PR).
- Tag `vX.Y.Z` → staging (manual aprobación).
- Tag `vX.Y.Z-prod` → prod (manual aprobación + smoke obligatorio).

Las migraciones Supabase se aplican **antes** del deploy del backend
para que las tablas/columnas nuevas existan cuando el código nuevo
las consulte. `supabase db push --linked` se corre desde un workflow
de GitHub Actions con un service role key como secret.

## Rollback

- **Backend** — Render → service → Manual Deploy → seleccionar el SHA
  anterior. Se recupera en ~2 min.
- **Migraciones** — son forward-only. Para revertir un cambio se hace
  una nueva migración que corrija. Nunca borrar migraciones aplicadas.
- **Frontend** — Vercel → Deployments → rollback al deploy anterior.
- **Reglas tributarias** — un rule_set publicado se "deprecata" desde
  `/admin/rules` (panel admin v2); el motor automáticamente vuelve a
  la versión anterior vigente.
