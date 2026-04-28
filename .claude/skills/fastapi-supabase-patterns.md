# Patrones de Backend — FastAPI + Supabase (Renteo)

## Propósito
Definir patrones técnicos para el backend en Python (FastAPI) con
Supabase como DB/Auth, con foco en multi-tenant, RLS, integración SII
y observabilidad.

## Stack
- Python 3.12.
- FastAPI 0.115+.
- SQLAlchemy 2 (async).
- Pydantic v2 (request/response models).
- Supabase Python client (auth + storage).
- HTTPX para clientes externos (SimpleAPI/BaseAPI).
- Celery + Redis para jobs asíncronos (sync SII, alertas).
- Alembic NO (migraciones en Supabase migrations).
- Sentry (errores) + structlog (logs JSON sin PII).
- Boto3 para AWS KMS / S3.

## Estructura de carpetas
apps/api/
├── src/
│   ├── main.py                 # FastAPI app
│   ├── config.py               # settings con pydantic-settings
│   ├── deps.py                 # dependencies inyectables
│   ├── db.py                   # async engine, session
│   ├── auth/
│   │   ├── jwt.py              # validación JWT con JWKS
│   │   ├── tenancy.py          # extracción workspace_id, role
│   │   └── permissions.py      # RBAC por rol
│   ├── domain/
│   │   ├── empresas/
│   │   ├── tax_engine/
│   │   ├── sii_integration/
│   │   ├── recommendations/
│   │   ├── scenarios/
│   │   ├── alerts/
│   │   └── privacy/            # ARCOP, consentimientos, brechas
│   ├── routers/
│   │   ├── empresas.py
│   │   ├── tax.py
│   │   ├── scenarios.py
│   │   ├── alerts.py
│   │   ├── privacy.py
│   │   └── webhooks.py
│   ├── adapters/
│   │   ├── sii_simpleapi.py
│   │   ├── sii_baseapi.py
│   │   ├── sii_apigateway.py
│   │   ├── kms_certs.py
│   │   └── notifications.py
│   ├── workers/
│   │   ├── celery_app.py
│   │   ├── tasks_sync_sii.py
│   │   ├── tasks_alerts.py
│   │   └── tasks_privacy.py
│   └── lib/
│       ├── errors.py
│       ├── logging.py
│       └── audit.py
├── tests/
│   ├── unit/
│   ├── integration/
│   └── golden/                 # casos validados por contador socio
├── pyproject.toml
└── ruff.toml

---

## Auth y JWT con Supabase

### Validación
Supabase emite JWT con claims custom en `app_metadata`. Renteo lee:
- `sub`: user_id.
- `app_metadata.workspace_id`.
- `app_metadata.workspace_type`: `pyme` | `accounting_firm`.
- `app_metadata.role`.
- `app_metadata.empresa_ids[]` (cliente B: empresas asignadas).

JWKS endpoint: `https://<project>.supabase.co/auth/v1/jwks`.
Cache local 1h.

```python
# src/auth/jwt.py
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer
import jwt
from jwt import PyJWKClient

bearer = HTTPBearer()
jwks = PyJWKClient(JWKS_URL, cache_keys=True, lifespan=3600)

def verify_jwt(creds = Depends(bearer)) -> dict:
    token = creds.credentials
    signing_key = jwks.get_signing_key_from_jwt(token).key
    try:
        return jwt.decode(
            token,
            signing_key,
            algorithms=["RS256"],
            audience="authenticated",
        )
    except jwt.PyJWTError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(e))
```

### Tenancy
```python
# src/auth/tenancy.py
from pydantic import BaseModel

class Tenancy(BaseModel):
    user_id: str
    workspace_id: str
    workspace_type: str  # 'pyme' | 'accounting_firm'
    role: str
    empresa_ids: list[str]

def current_tenancy(claims = Depends(verify_jwt)) -> Tenancy:
    meta = claims.get("app_metadata", {})
    if not meta.get("workspace_id"):
        raise HTTPException(403, "no workspace")
    return Tenancy(
        user_id=claims["sub"],
        workspace_id=meta["workspace_id"],
        workspace_type=meta["workspace_type"],
        role=meta["role"],
        empresa_ids=meta.get("empresa_ids", []),
    )
```

### RBAC
```python
# src/auth/permissions.py
def require_role(*roles: str):
    def dep(t: Tenancy = Depends(current_tenancy)) -> Tenancy:
        if t.role not in roles:
            raise HTTPException(403, "forbidden")
        return t
    return dep

def require_empresa_access(empresa_id: str):
    def dep(t: Tenancy = Depends(current_tenancy)) -> Tenancy:
        if t.role in ("owner", "accountant_lead"):
            return t
        if empresa_id in t.empresa_ids:
            return t
        raise HTTPException(403, "no access to empresa")
    return dep
```

---

## DB y RLS desde el backend

Supabase impone RLS al nivel de Postgres. El backend debe enviar el
JWT del usuario en cada query para que las policies se evalúen.

Patrón: usar conexión PostgREST de Supabase para queries simples; usar
SQLAlchemy con session que setee `request.jwt.claims` cuando se requiera
SQL avanzado.

```python
# Pattern: ejecutar SQL con claims
async with engine.begin() as conn:
    await conn.execute(
        text("SET LOCAL request.jwt.claims = :claims"),
        {"claims": json.dumps(claims)},
    )
    result = await conn.execute(...)
```

**Nunca** pasar `workspace_id` o `empresa_id` desde el body o query
del cliente; siempre derivarlos del JWT vía `current_tenancy`.

---

## Pydantic v2 — request / response

```python
# src/routers/scenarios.py
from pydantic import BaseModel, Field
from typing import Literal

class CrearEscenarioReq(BaseModel):
    empresa_id: str
    tax_year: int = Field(ge=2024, le=2030)
    palancas: list[Palanca]
    nombre: str = Field(max_length=120)

class EscenarioResp(BaseModel):
    id: str
    rli: float
    idpc: float
    igc_total: float
    carga_total: float
    ahorro: float
    es_recomendado: bool
    engine_version: str
    fundamento_legal: list[Cita]
```

Usar `model_config = {"strict": True}` cuando aplica.

---

## Manejo de errores

Tipos de error tributario:

```python
# src/lib/errors.py
class TaxError(Exception): pass
class IneligibleForRegime(TaxError): ...
class RedFlagBlocked(TaxError): ...
class MissingTaxYearParams(TaxError): ...
class SiiUnavailable(TaxError): ...
class CertificateError(TaxError): ...
class ConsentMissing(TaxError): ...
```

Handler global mapea a HTTP:
- `IneligibleForRegime` → 422 con razones.
- `RedFlagBlocked` → 422 con explicación legal.
- `MissingTaxYearParams` → 500 + alerta interna.
- `SiiUnavailable` → 503 + retry-after.
- `CertificateError` → 401.
- `ConsentMissing` → 403.

---

## Cliente SII con feature flag

```python
# src/adapters/sii_simpleapi.py
class SimpleApiClient:
    async def fetch_rcv(self, rut: str, period: str, cert_pem: str): ...

# src/adapters/sii_baseapi.py
class BaseApiClient:
    async def fetch_rcv(self, rut: str, period: str, cert_pem: str): ...

# src/domain/sii_integration/service.py
class SiiService:
    def __init__(self, primary, backup, feature_flags):
        self.primary, self.backup, self.flags = primary, backup, feature_flags

    async def fetch_rcv(self, rut, period, cert_pem):
        provider = self.flags.get("sii_provider", "simpleapi")
        client = self.primary if provider == "simpleapi" else self.backup
        try:
            return await client.fetch_rcv(rut, period, cert_pem)
        except SiiUnavailable:
            other = self.backup if client is self.primary else self.primary
            return await other.fetch_rcv(rut, period, cert_pem)
```

Idempotencia: cada sync se identifica con
`hash(empresa_id + period + tipo_dato)` y se evita duplicación.

---

## Certificados digitales y KMS

```python
# src/adapters/kms_certs.py
import boto3

kms = boto3.client("kms", region_name="sa-east-1")
s3 = boto3.client("s3")

async def upload_certificate(empresa_id: str, pfx_bytes: bytes,
                             pfx_password: str) -> str:
    # Validar PFX (vencimiento, RUT) sin persistir password en claro.
    valid = validate_pfx(pfx_bytes, pfx_password)
    if not valid:
        raise CertificateError("invalid pfx")

    # Generar data key con KMS, cifrar PFX en memoria.
    data_key = kms.generate_data_key(KeyId=KMS_KEY_ARN, KeySpec="AES_256")
    encrypted = encrypt(pfx_bytes, data_key["Plaintext"])

    object_key = f"certs/{empresa_id}/{uuid4()}.enc"
    s3.put_object(
        Bucket=CERTS_BUCKET,
        Key=object_key,
        Body=encrypted,
        ServerSideEncryption="aws:kms",
        SSEKMSKeyId=KMS_KEY_ARN,
        Metadata={"data_key_ciphertext_b64": b64(data_key["CiphertextBlob"])},
    )

    # Persistir solo metadatos en DB.
    await save_cert_metadata(
        empresa_id=empresa_id,
        kms_key_arn=KMS_KEY_ARN,
        s3_object_key=object_key,
        rut_titular=valid.rut,
        valido_hasta=valid.expires_at,
    )
    return object_key
```

Reglas:
- PFX y password jamás se persisten en DB ni en logs.
- Sesión efímera: descifrar en memoria al usar, descartar al terminar.
- `cert_usage_log`: cada uso queda registrado.

---

## Audit log inmutable

```python
# src/lib/audit.py
async def log_audit(workspace_id, empresa_id, user_id, action,
                    resource_type, resource_id, metadata=None):
    await db.execute(
        text("""
        INSERT INTO security.audit_log (
            workspace_id, empresa_id, user_id, action,
            resource_type, resource_id, metadata, at
        ) VALUES (:w, :e, :u, :a, :rt, :ri, :m, now())
        """),
        {"w": workspace_id, "e": empresa_id, "u": user_id,
         "a": action, "rt": resource_type, "ri": resource_id,
         "m": json.dumps(metadata or {})},
    )
```

Trigger Postgres impide UPDATE/DELETE en `audit_log`.

---

## Logging sin PII

structlog con processor que filtra:

```python
SENSITIVE_KEYS = {"rut", "password", "pfx", "claim", "token",
                  "razon_social", "monto"}

def filter_sensitive(_, __, event_dict):
    for k in list(event_dict):
        if k.lower() in SENSITIVE_KEYS:
            event_dict[k] = "***"
    return event_dict
```

Log levels: errores a Sentry; debug solo en local; info+ con
correlation_id propagado por header `X-Correlation-Id`.

---

## Workers Celery

Tareas:
- `sync_sii_monthly`: por empresa, descarga RCV + F29 del mes.
- `compute_alerts_daily`: evalúa reglas de alerta por empresa.
- `purge_expired_data_nightly`: aplica política de retención post
  Ley 21.719.
- `notify_arcop_pending`: reminders para responder ARCOP en plazo.

Idempotencia mediante locks en Redis con expiración.

---

## Observabilidad

- Sentry para errores Python; agrupar por `tax_year` y `regimen`.
- Datadog (o equivalente) para métricas: latencia SII, tasa de éxito
  de syncs, simulaciones por minuto.
- Health checks: `/healthz` (DB + Redis) y `/readyz` (incluye
  proveedores SII).
- Alertas a Slack/PagerDuty: caída de proveedor primario SII,
  brechas detectadas, errores de cifrado.

---

## CI/CD

GitHub Actions:
- Lint: ruff + mypy (strict).
- Tests: pytest + pytest-asyncio + coverage 85%+.
- Tests golden tributarios: bloquean merge si fallan.
- Tests de RLS: simular múltiples tenants y verificar aislamiento.
- Migraciones Supabase: ejecutar en preview branch antes del merge.
- Deploy preview por cada PR.

---

## Convenciones de código

- Ruff con preset estricto, line length 88.
- mypy strict habilitado para `src/domain/**`.
- Sin `Any` salvo en boundaries documentados.
- Funciones del motor tributario tienen docstring obligatorio con:
  - Fundamento legal (artículo + circular).
  - Caso golden de referencia.
  - Año tributario aplicable.
- Conventional Commits: `feat(tax): ...`, `fix(sii): ...`, `chore: ...`.

---

## Anti-patrones (no hacer)

- ❌ Pasar `workspace_id` o `empresa_id` desde el cliente.
- ❌ Hardcodear tasas o tramos en el código.
- ❌ Persistir certificado digital o password en DB / variables de
  entorno / logs.
- ❌ Loguear payload SII completo (puede contener PII).
- ❌ Eliminar registros de `audit_log`.
- ❌ Bypassar el motor de guardrails para "ahorrar" llamadas.
- ❌ Aplicar lógica tributaria fuera de `domain/tax_engine`.

---

## TODO
- Definir SLA con Sentry y umbrales de alerta.
- Test suite específico para multi-tenancy (importante: RLS no es
  suficiente sin tests).
- Runbook para incidente de proveedor SII caído.
- Plantilla DPA para Supabase, AWS y proveedores SII.
