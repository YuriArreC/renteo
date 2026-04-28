# Renteo — CLAUDE.md

App de optimización tributaria para Chile. Atiende dos clientes en
paralelo: PYME / mediana (cliente A) y contadores / estudios
(cliente B). Motor tributario único, dos UX.

## Skills del proyecto

Toda decisión de diseño, código o copy debe pasar por las skills en
`.claude/skills/`. Si una decisión no calza con ninguna, se escala
antes de implementar.

1. **tax-compliance-guardrails** — Lista blanca/negra de
   recomendaciones permitidas. Define los tres niveles (economía de
   opción ✅, elusión ❌, evasión ❌). Marco NGA arts. 4 bis/ter/quáter
   CT y art. 100 bis.
2. **disclaimers-and-legal** — Textos legales versionados:
   disclaimers de recomendación y simulación, consentimientos
   (datos, certificado digital, mandato digital), términos de
   servicio, política de privacidad, ribbon de decisiones
   automatizadas.
3. **chilean-tax-engine** — Reglas y parámetros del motor: tasas
   IDPC por régimen y AT, IGC, IVA, PPM, RLI, gastos aceptados/
   rechazados, registros SAC/RAI/REX/DDAN, créditos contra IDPC.
4. **sii-integration** — Conexión con SII vía SimpleAPI (primario),
   BaseAPI (backup), ApiGateway (alternativo). Manejo de
   certificado digital, mandato digital, resiliencia y errores.
5. **chilean-data-privacy** — Cumplimiento Ley 19.628 (vigente) y
   Ley 21.719 (1-dic-2026). ARCOP, DPO, RAT, DPIA, brechas,
   reserva tributaria art. 35 CT.
6. **tax-data-model** — Esquema Postgres/Supabase: schemas `core`,
   `tax_params`, `tax_data`, `tax_calc`, `security`, `privacy`. RLS
   multi-tenant, parametrización temporal, audit log inmutable.
7. **regime-recommendation** — Wizard de 12-15 preguntas, motor de
   elegibilidad para 14 A / 14 D N°3 / 14 D N°8 / renta presunta,
   proyección financiera 3 años con escenario dual de tasa
   transitoria 12,5%.
8. **scenario-simulator** — Simulador what-if de cierre con 12
   palancas lícitas (P1-P12), validación ex-ante, banderas rojas,
   comparador de hasta 4 escenarios.
9. **dual-ux-patterns** — Patrones UX cliente A (1 empresa, narrativo,
   CTA simulación) vs cliente B (cartera densa, batch, score de
   oportunidad, papeles de trabajo).
10. **fastapi-supabase-patterns** — Backend Python 3.12 + FastAPI +
    SQLAlchemy 2 + Pydantic v2 + Supabase. JWT/JWKS, tenancy,
    RBAC, Celery, KMS, structlog sin PII.

## Reglas no negociables

### Cumplimiento tributario
- Solo recomendaciones de la **lista blanca** de
  `tax-compliance-guardrails`. Si no encaja, se rechaza.
- **Cero** sugerencias de elusión, simulación o evasión. Banderas
  rojas bloquean automáticamente.
- **Disclaimer obligatorio** (`disclaimer-recomendacion-v1`) en cada
  recomendación entregada al usuario.
- Cada output de motor cita **artículo LIR + Circular SII** vigente.

### Datos y privacidad
- **Multi-tenant desde el día 1.** RLS habilitado en TODAS las
  tablas con datos de usuario. Sin excepción.
- `workspace_id` y `empresa_id` se derivan del **JWT**, nunca del
  payload del cliente.
- **Cifrado:** AES-256 en reposo, TLS 1.3 en tránsito.
- **Reserva tributaria art. 35 CT** vincula a la app y a todos sus
  encargados.
- **Audit log inmutable** para todo acceso a datos tributarios.

### Certificados y SII
- **NUNCA** pedir Clave Tributaria del usuario en texto plano.
- Certificados digitales viven solo en **AWS KMS**. En DB solo el
  ARN y metadatos no sensibles.
- Llamadas a SII vía proveedores autorizados (SimpleAPI/BaseAPI/
  ApiGateway) con feature flag para conmutar sin downtime.

### Motor tributario
- Toda **tasa, tope, tramo o factor** parametrizado por año tributario
  en tabla. Hardcoding **prohibido**.
- Toda función de cálculo tiene **test golden** validado por contador
  socio.
- Toda función incluye en su docstring **fundamento legal** (artículo
  + circular/oficio).
- Sin fundamento → `TODO(contador)` y no se mergea.

### UX dual
- Motor tributario **único**. Las dos UX consumen los mismos cálculos.
- Componentes compartidos llevan suffix `_Shared`; específicos
  `_A` o `_B`. No mezclar densidad.
- Ningún componente del motor vive fuera de `domain/tax_engine`.

### Logging y observabilidad
- Logs **JSON sin PII** (RUTs enmascarados, sin claves, sin payloads
  SII completos).
- Errores tributarios tipados (`IneligibleForRegime`, `RedFlagBlocked`,
  `SiiUnavailable`, etc.) con mapeo HTTP explícito.

## Prohibiciones explícitas

- ❌ Hardcodear tasas, tramos o topes en código.
- ❌ Persistir certificado digital o password en DB / variables de
  entorno / logs.
- ❌ Pasar `workspace_id` o `empresa_id` desde el cliente.
- ❌ Loguear payload SII completo o RUTs sin enmascarar.
- ❌ Eliminar registros de `audit_log`.
- ❌ Bypassar el motor de guardrails.
- ❌ Aplicar lógica tributaria fuera de `domain/tax_engine`.
- ❌ Sugerir reorganizaciones societarias con motivo principal
  tributario.
- ❌ Texto legal en UI distinto del versionado en
  `disclaimers-and-legal`.

## Validación obligatoria pre-merge

- Tests golden tributarios pasan.
- Tests de RLS multi-tenant pasan.
- Coverage ≥ 85% en `domain/tax_engine`.
- Lint ruff + mypy strict en `domain/**`.
- Migración Supabase aplicada en preview branch.
- Si la PR toca recomendaciones o motor: revisión de contador socio.

## Roles humanos

- **CONTADOR_SOCIO**: valida lista blanca, casos golden, rangos
  razonables (sueldo empresarial), interpretación SII, escalamiento
  TODO(contador). DPO inicial (Ley 21.719).
- **ESTUDIO_JURIDICO**: redacta y firma textos legales finales,
  DPAs con encargados, cláusulas de mandato digital.

## Stack técnico

- **Frontend:** TBD (componentes con suffix `_A` / `_B` / `_Shared`).
- **Backend:** Python 3.12, FastAPI, SQLAlchemy 2 async, Pydantic v2.
- **DB/Auth:** Supabase (Postgres 15+) con RLS y JWT.
- **Storage:** AWS S3 + KMS (sa-east-1 preferente).
- **Workers:** Celery + Redis.
- **Observabilidad:** Sentry + structlog + Datadog (o equivalente).
- **CI/CD:** GitHub Actions con lint, tests, golden, RLS, deploy
  preview por PR.
