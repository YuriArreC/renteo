# Runbook de incidentes — Renteo

Guía operacional para los incidentes recurrentes de los primeros
meses post-launch. Cada sección tiene síntoma, diagnóstico y
mitigación en orden de severidad ascendente.

## Convenciones

- **Sev1** — clientes no pueden usar el producto (downtime total).
- **Sev2** — degradación parcial (un endpoint cae, datos
  desactualizados, latencia 10×).
- **Sev3** — alerta interna sin impacto al cliente todavía.

Todo incidente Sev1/Sev2 abre un post-mortem en
`docs/postmortems/<fecha>-<slug>.md` dentro de las 48 h.

---

## SII proveedor caído (`SiiUnavailable` recurrente)

**Síntoma**: `/api/empresas/{id}/sync-sii` y onboarding-from-rut
devuelven 503 con `code: sii_unavailable`. Sentry alerta error rate
> 5% en `simpleapi_client`.

**Diagnóstico**:
1. Status del proveedor (SimpleAPI dashboard).
2. Logs Render: `sii_simpleapi_5xx` o `sii_simpleapi_timeout`.
3. Dashboard Datadog → latency p99 del cliente HTTP.

**Mitigación**:
1. Si SimpleAPI está caído → publicar feature flag
   `sii_provider=baseapi` (fallback) vía panel admin.
2. Si todos los proveedores caen → mantener flag
   `sii_provider=mock` para que el resto del producto siga vivo;
   bloquear endpoints de sync con un banner explicativo.
3. Ningún rollback de código necesario; los flags resuelven en
   minutos.

---

## Watchdog legislativo no corre

**Síntoma**: en `/admin/legislation` no aparecen filas nuevas en >24 h.
`logger.info("watchdog_legislativo_done")` ausente del log Render.

**Diagnóstico**:
1. Render → service `renteo-beat` → logs. Si está caído, beat no
   dispara nada y `worker_alertas` tampoco corre.
2. `redis-cli` contra `REDIS_URL` → `KEYS celery:beat:*`. Si está
   vacío, el beat nunca se inicializó.

**Mitigación**:
1. Restart `renteo-beat` desde Render.
2. Si persiste, correr ad-hoc `POST /api/admin/legislative-alerts/run`
   desde el panel admin (rinde mientras se diagnostica el cron).

---

## Latencia API alta (p95 > 2 s)

**Síntoma**: Sentry / Datadog alertan p95 sostenido. Los endpoints
más afectados suelen ser `/api/regime/diagnose` y
`/api/scenario/simulate`.

**Diagnóstico**:
1. Sentry transactions → endpoint top-N por p95.
2. Supabase dashboard → connection count + slow queries.
3. Logs estructurados con `request_id` cruzado entre frontend y
   backend → identificar request específico.

**Mitigación**:
1. Si `connection_count` cerca del límite del plan Supabase →
   subir plan o configurar pgbouncer.
2. Si una query específica está lenta → revisar `EXPLAIN ANALYZE`
   contra prod (read replica). Considerar índice nuevo (vía nueva
   migración).
3. Si `/api/regime/diagnose` está lento → revisar
   `build_snapshots` (track 11c). El JSON snapshot puede crecer si
   los rule_sets son grandes; considerar serialización canónica.

---

## audit_log creciendo sin techo

**Síntoma**: Supabase storage > 80% del plan. Tabla
`security.audit_log` con > 10M filas.

**Diagnóstico**:
1. `select count(*) from security.audit_log;`
2. `select action, count(*) from security.audit_log group by action
   order by 2 desc limit 20;`

**Mitigación**:
1. Configurar **policy de retención** (no implementado en MVP):
   archivar a S3 las filas > 24 meses + delete con
   `session_replication_role = 'replica'` para evitar bloquear el
   trigger append-only.
2. Antes de borrar, generar dump CSV cifrado y subirlo a
   `s3://renteo-audit-archive-<env>/`.
3. CLAUDE.md exige "Audit log inmutable", por lo que NO borramos
   sin archivado previo.

---

## Custodia certificado: KMS decrypt falla

**Síntoma**: SimpleAPI calls fallan con `CertificateError: KMS
decrypt falló`. El cert está en S3 pero no se puede descifrar.

**Diagnóstico**:
1. `aws kms describe-key --key-id <arn>` → estado `Enabled`?
2. IAM policy → permite `kms:Decrypt` al user `renteo-prod-runtime`?
3. Verificar que el key_arn persistido en
   `security.certificados_digitales` coincide con la CMK actual
   (post-rotación pueden divergir).

**Mitigación**:
1. Si la CMK fue accidentalmente disabled → re-habilitar.
2. Si fue rotada y el blob viejo no descifra → revocar el cert en
   `/api/empresas/{id}/certificado` y pedir al cliente subir uno
   nuevo. CLAUDE.md prohíbe persistir el plaintext, así que no hay
   forma de re-cifrar sin el blob original.
3. Documentar el incidente en post-mortem y considerar política
   de re-encriptación previa a cada rotación de CMK.

---

## Doble firma de regla rechazada

**Síntoma**: contador socio firma una regla pero al publicar el
endpoint devuelve 422 con `published_by_contador = published_by_admin`.

**Diagnóstico**: el constraint `rule_sets_double_sig_check` exige
firmantes distintos. Probablemente el mismo user firmó las dos veces
desde una sesión con doble email mapeado.

**Mitigación**:
1. Verificar que ambos emails (`contador-socio@renteo.cl` y
   `admin-tecnico@renteo.cl`) están en la whitelist
   `INTERNAL_ADMIN_EMAILS`.
2. Pedir al admin técnico (segunda firma) que use su sesión propia
   para invocar `POST /api/admin/rules/{id}/publish`.

---

## Sentry desbordado / cuota agotada

**Síntoma**: nuevos errores no aparecen en Sentry. Banner de la cuenta
indica "monthly quota reached".

**Mitigación inmediata**:
1. Sentry → Settings → Quotas → temporary increase.
2. Identificar el evento ruidoso vía "Top Issues" → agregar a
   `ignore` o subir el sample rate down a 10%.
3. Revisar `init_sentry` en `lib/observability` → considerar
   `traces_sample_rate` más conservador para endpoints chatty
   (`/healthz`, `/readyz`).
