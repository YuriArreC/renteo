# Modelo de Datos Tributario — Renteo

## Propósito
Definir el esquema de base de datos del proyecto Renteo: tablas,
relaciones, RLS multi-tenant, parametrización temporal y auditoría.
Toda nueva tabla, columna o migración debe respetar las reglas de
esta skill.

## Principios no negociables
1. **Multi-tenant desde el día 1.** Toda tabla con datos de
   contribuyentes tiene `workspace_id` Y `empresa_id` cuando aplica.
2. **RLS habilitado en TODAS las tablas con datos de usuario.**
   Sin excepción.
3. **`workspace_id` y `empresa_id` se derivan del JWT** (claim en
   `app_metadata`), nunca del payload del cliente.
4. **Toda tasa, tope o factor tributario está parametrizado por
   año tributario.** Hardcoding prohibido.
5. **Auditoría inmutable** de accesos a datos tributarios:
   tabla `audit_log` append-only.
6. **Cifrado at-rest** (Postgres + Supabase) y **TLS 1.3** in-transit.
7. **Certificados digitales viven solo en KMS.** En DB solo el ARN
   y metadatos no sensibles.

## Stack
- Postgres 15+ (Supabase managed).
- RLS + JWT con claims `workspace_id`, `empresa_id`, `role`.
- Migraciones versionadas (`supabase/migrations/<timestamp>_<nombre>.sql`).
- Sin SQL ad-hoc en producción.

## Convenciones de nombres
- Tablas: snake_case plural (`empresas`, `rli_calculations`).
- Columnas: snake_case (`empresa_id`, `created_at`).
- Tablas con dimensión temporal tributaria llevan `tax_year` o
  período mensual `period` (formato `YYYY-MM`).
- FKs: `<tabla_singular>_id`.
- Booleans: `is_<estado>` o `has_<atributo>`.
- Timestamps: `created_at`, `updated_at`, `deleted_at` (soft delete).

## Tipos de cliente y roles
Renteo atiende dos clientes paralelos (ver `dual-ux-patterns.md`):

- **Cliente A — PYME / mediana:** workspace contiene 1 empresa
  (o pocas en caso de grupo); roles: `owner`, `cfo`, `viewer`.
- **Cliente B — Contador / estudio:** workspace contiene N empresas;
  roles: `accountant_lead`, `accountant_staff`, `viewer`.

El esquema es el mismo. Lo que cambia es la cardinalidad workspace
↔ empresas y los permisos por rol.

---

## Esquemas y tablas

### Schema `auth` (gestionado por Supabase)
- `auth.users`: registro nativo de Supabase.

### Schema `core` — multi-tenant base

**workspaces**
| col | tipo | notas |
|---|---|---|
| id | uuid PK | |
| name | text | |
| type | text | enum: `pyme` (cliente A), `accounting_firm` (cliente B) |
| billing_plan | text | `free`, `pyme_basic`, `pyme_pro`, `firm_basic`, `firm_pro` |
| dpo_user_id | uuid FK auth.users | DPO designado para Ley 21.719 |
| created_at | timestamptz | default now() |
| updated_at | timestamptz | |

**workspace_members**
| col | tipo | notas |
|---|---|---|
| id | uuid PK | |
| workspace_id | uuid FK workspaces | |
| user_id | uuid FK auth.users | |
| role | text | `owner`, `cfo`, `accountant_lead`, `accountant_staff`, `viewer` |
| invited_at | timestamptz | |
| accepted_at | timestamptz | nullable |

UNIQUE (workspace_id, user_id).

**empresas**
| col | tipo | notas |
|---|---|---|
| id | uuid PK | |
| workspace_id | uuid FK workspaces | |
| rut | text | formato `12345678-9` |
| razon_social | text | |
| giro | text | |
| regimen_actual | text | enum: `14_a`, `14_d_3`, `14_d_8`, `presunta`, `desconocido` |
| fecha_inicio_actividades | date | |
| capital_inicial_uf | numeric(18,4) | |
| es_grupo_empresarial | bool | |
| sociedad_dominante_id | uuid FK empresas | nullable |
| created_at | timestamptz | |

UNIQUE (workspace_id, rut).

**accountant_assignments** (cliente B: qué staff atiende qué empresa)
| col | tipo | notas |
|---|---|---|
| workspace_id | uuid FK | |
| empresa_id | uuid FK | |
| user_id | uuid FK auth.users | |
| permission_level | text | `read`, `read_write`, `full` |

PK compuesta (workspace_id, empresa_id, user_id).

---

### Schema `tax_params` — parametrización temporal

**tax_year_params**
| col | tipo | notas |
|---|---|---|
| tax_year | int PK | ej. 2026 |
| iva_rate | numeric(5,4) | 0.1900 |
| retencion_honorarios | numeric(5,4) | 0.1525 para AT 2026 |
| uta_pesos_dic | numeric(12,2) | UTA dic año comercial |
| utm_pesos_dic | numeric(12,2) | |
| uf_pesos_dic | numeric(12,4) | |
| fuente_legal | text | ley/circular |
| vigencia_inicio | date | |
| vigencia_fin | date | nullable |
| observaciones | text | |

**idpc_rates**
| col | tipo | notas |
|---|---|---|
| tax_year | int FK | |
| regimen | text | `14_a`, `14_d_3`, `14_d_8` |
| rate | numeric(5,4) | |
| es_transitoria | bool | |
| condicion_aplicacion | text | ej. condicionalidad Ley 21.735 |
| fuente_legal | text | |

PK (tax_year, regimen).

**igc_brackets**
| col | tipo | notas |
|---|---|---|
| tax_year | int FK | |
| tramo | int | 1 a 8 |
| desde_uta | numeric(8,4) | |
| hasta_uta | numeric(8,4) | nullable para tramo 8 |
| tasa | numeric(5,4) | |
| rebajar_uta | numeric(8,4) | |

PK (tax_year, tramo).

**ppm_pyme_rates**
| col | tipo | notas |
|---|---|---|
| tax_year | int FK | |
| regimen | text | |
| umbral_uf | numeric(12,2) | 50.000 UF |
| tasa_bajo | numeric(6,5) | 0.00125 transitoria |
| tasa_alto | numeric(6,5) | 0.00250 transitoria |
| es_transitoria | bool | |

---

### Schema `tax_data` — datos tributarios sincronizados desde SII

**dtes** (Documentos Tributarios Electrónicos)
| col | tipo | notas |
|---|---|---|
| id | uuid PK | |
| workspace_id | uuid FK | RLS |
| empresa_id | uuid FK | RLS |
| tipo | int | tipo DTE SII (33, 34, 39, 41, 56, 61, etc.) |
| folio | bigint | |
| direccion | text | `emitido` o `recibido` |
| rut_contraparte | text | |
| razon_social_contraparte | text | |
| fecha_emision | date | |
| neto | numeric(18,2) | |
| iva | numeric(18,2) | |
| total | numeric(18,2) | |
| estado_sii | text | `aceptado`, `rechazado`, `reclamado`, etc. |
| raw_payload | jsonb | respuesta cruda del proveedor |
| sync_provider | text | `simpleapi`, `baseapi`, `apigateway` |
| synced_at | timestamptz | |

INDEX (empresa_id, fecha_emision).
INDEX (empresa_id, direccion, fecha_emision).

**rcv_lines** (Registro de Compras y Ventas)
| col | tipo | notas |
|---|---|---|
| id | uuid PK | |
| workspace_id | uuid FK | |
| empresa_id | uuid FK | |
| period | text | `YYYY-MM` |
| tipo | text | `compra` o `venta` |
| dte_id | uuid FK dtes | nullable |
| neto | numeric(18,2) | |
| iva | numeric(18,2) | |
| total | numeric(18,2) | |
| categoria | text | |

INDEX (empresa_id, period, tipo).

**f29_periodos**
| col | tipo | notas |
|---|---|---|
| id | uuid PK | |
| workspace_id | uuid FK | |
| empresa_id | uuid FK | |
| period | text | `YYYY-MM` |
| iva_debito | numeric(18,2) | |
| iva_credito | numeric(18,2) | |
| ppm | numeric(18,2) | |
| retenciones | numeric(18,2) | |
| postergacion_iva | bool | |
| presentado_at | timestamptz | nullable |
| raw_payload | jsonb | |

UNIQUE (empresa_id, period).

**f22_anios** (declaración anual de renta)
| col | tipo | notas |
|---|---|---|
| id | uuid PK | |
| workspace_id | uuid FK | |
| empresa_id | uuid FK | |
| tax_year | int | |
| regimen_declarado | text | |
| rli_declarada | numeric(18,2) | |
| idpc_pagado | numeric(18,2) | |
| creditos_imputados | jsonb | desglose por crédito |
| presentado_at | timestamptz | |
| raw_payload | jsonb | |

UNIQUE (empresa_id, tax_year).

**boletas_honorarios**
| col | tipo | notas |
|---|---|---|
| id | uuid PK | |
| workspace_id | uuid FK | |
| empresa_id | uuid FK | |
| numero | bigint | |
| fecha_emision | date | |
| monto_bruto | numeric(18,2) | |
| retencion | numeric(18,2) | |
| monto_liquido | numeric(18,2) | |
| rut_emisor | text | |

---

### Schema `tax_calc` — cálculos del motor

**rli_calculations**
| col | tipo | notas |
|---|---|---|
| id | uuid PK | |
| workspace_id | uuid FK | |
| empresa_id | uuid FK | |
| tax_year | int | |
| ingresos_brutos | numeric(18,2) | |
| costos | numeric(18,2) | |
| gastos_aceptados | numeric(18,2) | |
| agregados_art_33 | numeric(18,2) | |
| perdidas_anteriores | numeric(18,2) | |
| rli_final | numeric(18,2) | |
| engine_version | text | hash + tag |
| inputs_snapshot | jsonb | reproducibilidad |
| computed_at | timestamptz | |

**registros_tributarios** (SAC, RAI, REX, DDAN para 14 A y 14 D N°3)
| col | tipo | notas |
|---|---|---|
| id | uuid PK | |
| workspace_id | uuid FK | |
| empresa_id | uuid FK | |
| tax_year | int | |
| sac_inicial | numeric(18,2) | |
| sac_movimientos | jsonb | |
| sac_final | numeric(18,2) | |
| rai_inicial | numeric(18,2) | |
| rai_final | numeric(18,2) | |
| rex_inicial | numeric(18,2) | |
| rex_final | numeric(18,2) | |
| ddan_final | numeric(18,2) | |

UNIQUE (empresa_id, tax_year).

**retiros_y_distribuciones**
| col | tipo | notas |
|---|---|---|
| id | uuid PK | |
| workspace_id | uuid FK | |
| empresa_id | uuid FK | |
| socio_id | uuid | identificador interno del socio/dueño |
| fecha | date | |
| monto | numeric(18,2) | |
| imputacion | text | `rex`, `rai_con_credito`, `rai_sin_credito` |
| credito_idpc | numeric(18,2) | nullable |

---

### Schema `core` — escenarios y recomendaciones

**escenarios_simulacion**
| col | tipo | notas |
|---|---|---|
| id | uuid PK | |
| workspace_id | uuid FK | |
| empresa_id | uuid FK | |
| tax_year | int | |
| nombre | text | ej. "Cierre 2026 — depreciación + SENCE" |
| inputs | jsonb | sliders del simulador |
| outputs | jsonb | RLI, IDPC, IGC, ahorro |
| es_recomendado | bool | el motor lo marca como mejor opción lícita |
| created_by | uuid FK auth.users | |
| created_at | timestamptz | |

**recomendaciones**
| col | tipo | notas |
|---|---|---|
| id | uuid PK | |
| workspace_id | uuid FK | |
| empresa_id | uuid FK | |
| tipo | text | enum lista blanca de `tax-compliance-guardrails.md` |
| descripcion | text | qué se recomienda |
| fundamento_legal | jsonb | `[{art:"31 N°5 bis LIR", circular:"53/2025"}]` |
| ahorro_estimado_clp | numeric(18,2) | |
| disclaimer_version | text | `v1` |
| engine_version | text | |
| created_at | timestamptz | |
| dismissed_at | timestamptz | nullable |
| acted_on_at | timestamptz | nullable |

INDEX (empresa_id, tax_year).

**alertas**
| col | tipo | notas |
|---|---|---|
| id | uuid PK | |
| workspace_id | uuid FK | |
| empresa_id | uuid FK | |
| tipo | text | catálogo: `sence_no_usado`, `cerca_tope_14d`, etc. |
| severidad | text | `info`, `warning`, `critical` |
| titulo | text | |
| descripcion | text | |
| ahorro_estimado_clp | numeric(18,2) | |
| accion_recomendada | text | |
| estado | text | `nueva`, `vista`, `descartada`, `accionada` |
| fecha_limite | date | nullable |
| created_at | timestamptz | |

INDEX (empresa_id, estado, severidad).

---

### Schema `security` — certificados, mandatos y auditoría

**certificados_digitales**
| col | tipo | notas |
|---|---|---|
| id | uuid PK | |
| workspace_id | uuid FK | |
| empresa_id | uuid FK | |
| rut_titular | text | del certificado |
| kms_key_arn | text | NUNCA el binario |
| s3_object_key | text | apunta al PFX cifrado |
| nombre_titular | text | |
| valido_desde | date | |
| valido_hasta | date | |
| revocado_at | timestamptz | nullable |
| created_at | timestamptz | |

**mandatos_digitales** (cliente B: contador opera en nombre de empresa)
| col | tipo | notas |
|---|---|---|
| id | uuid PK | |
| workspace_id | uuid FK | |
| empresa_id | uuid FK | |
| contador_user_id | uuid FK auth.users | |
| alcance | text[] | `consultar_f29`, `declarar_f22`, etc. |
| inicio | date | |
| termino | date | |
| revocado_at | timestamptz | nullable |
| sii_referencia | text | folio o id en portal SII |

**cert_usage_log** (auditoría de uso de certificados)
| col | tipo | notas |
|---|---|---|
| id | uuid PK | |
| certificado_id | uuid FK | |
| user_id | uuid FK auth.users | quien lo usó |
| proposito | text | `sync_rcv`, `consult_f29`, etc. |
| resultado | text | `success`, `auth_failed`, `sii_down`, etc. |
| at | timestamptz | |

**audit_log** (append-only)
| col | tipo | notas |
|---|---|---|
| id | uuid PK | |
| workspace_id | uuid FK | |
| empresa_id | uuid FK | nullable |
| user_id | uuid FK auth.users | |
| action | text | `read`, `write`, `delete`, `recommend`, etc. |
| resource_type | text | `dte`, `f29`, `recomendacion`, etc. |
| resource_id | uuid | |
| metadata | jsonb | sin PII |
| at | timestamptz | |

INDEX (workspace_id, at DESC).
Tabla con trigger para impedir UPDATE/DELETE.

---

### Schema `privacy` — Ley 21.719

**arcop_requests**
| col | tipo | notas |
|---|---|---|
| id | uuid PK | |
| workspace_id | uuid FK | |
| user_id | uuid FK auth.users | titular del derecho |
| tipo | text | `acceso`, `rectificacion`, `cancelacion`, `oposicion`, `portabilidad` |
| estado | text | `recibida`, `en_proceso`, `cumplida`, `rechazada` |
| descripcion | text | |
| recibida_at | timestamptz | |
| respondida_at | timestamptz | nullable, máx 30 días |
| respuesta | text | |

**consentimientos**
| col | tipo | notas |
|---|---|---|
| id | uuid PK | |
| user_id | uuid FK auth.users | |
| workspace_id | uuid FK | nullable |
| empresa_id | uuid FK | nullable |
| tipo_consentimiento | text | `tratamiento_datos`, `certificado_digital`, `mandato_digital` |
| version_texto | text | ej. `consentimiento-tratamiento-datos-v1` |
| otorgado_at | timestamptz | |
| revocado_at | timestamptz | nullable |
| ip_otorgamiento | inet | |

**incidentes_brecha**
| col | tipo | notas |
|---|---|---|
| id | uuid PK | |
| descripcion | text | |
| detectado_at | timestamptz | |
| contenido_at | timestamptz | nullable |
| notificado_agencia_at | timestamptz | nullable, máx 72h |
| notificado_titulares_at | timestamptz | nullable |
| post_mortem_url | text | nullable |

---

## RLS — políticas estándar

Plantilla aplicable a tablas con `workspace_id` y `empresa_id`:

```sql
ALTER TABLE <tabla> ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_select ON <tabla>
FOR SELECT
USING (
  workspace_id = (auth.jwt() -> 'app_metadata' ->> 'workspace_id')::uuid
  AND (
    -- cliente A: acceso a su empresa
    empresa_id IN (
      SELECT id FROM empresas
      WHERE workspace_id = (auth.jwt() -> 'app_metadata' ->> 'workspace_id')::uuid
    )
    -- cliente B: acceso restringido a empresas asignadas
    AND (
      (auth.jwt() -> 'app_metadata' ->> 'role') IN ('owner','accountant_lead')
      OR empresa_id IN (
        SELECT empresa_id FROM accountant_assignments
        WHERE user_id = auth.uid()
      )
    )
  )
);
```

Reglas:
- SELECT, INSERT, UPDATE, DELETE: una policy por verbo.
- Tests automatizados: por cada tabla, test que valide que un user
  de workspace X no puede leer datos de workspace Y.
- Nunca confiar en el cliente para `workspace_id` o `empresa_id`.

---

## Parametrización temporal (regla maestra)

Cualquier valor que pueda cambiar entre años tributarios va en
`tax_params.*` o tabla equivalente. Lista no exhaustiva:

- Tasa IDPC por régimen → `idpc_rates`.
- Tramos IGC → `igc_brackets`.
- Tasa retención honorarios → `tax_year_params.retencion_honorarios`.
- IVA → `tax_year_params.iva_rate`.
- PPM PyME → `ppm_pyme_rates`.
- Topes UF, UTA, UTM → `tax_year_params`.
- Topes específicos (ej. 5.000 UF rebaja 14 E) → `beneficios_topes`.

Las funciones del motor reciben `tax_year` y consultan estas tablas.
Si `tax_year` no existe en la tabla, error explícito y bloqueo.

---

## Soft delete y retención

- Toda tabla con datos tributarios soporta `deleted_at` (soft delete).
- Hard delete solo vía proceso ARCOP (`privacy.arcop_requests` tipo
  `cancelacion`) y respetando retención legal mínima del Código
  Tributario (6 años art. 17 CT).
- Job mensual purga datos elegibles cuya retención venció.

---

## Migraciones

- Todas en `supabase/migrations/`.
- Nombre: `YYYYMMDDHHMMSS_<descripcion>.sql`.
- Idempotentes cuando sea posible (`IF NOT EXISTS`).
- Reversibles: cada migración tiene su `down.sql` en
  `supabase/migrations/<id>/down.sql`.
- Cero migraciones manuales en producción.

## Seeds

- `supabase/seeds/tax_params_2024_2030.sql`: carga inicial de
  parámetros tributarios.
- `supabase/seeds/regimen_catalog.sql`.
- Datos de prueba jamás en seeds productivos.

## TODO(contador)
- Validar el listado de columnas de `registros_tributarios` (SAC,
  RAI, REX, DDAN) contra estructura oficial post Ley 21.713.
- Confirmar formato de `imputacion` en `retiros_y_distribuciones`
  (orden y subcategorías).
- Definir catálogo completo de tipos de `recomendaciones` y `alertas`
  consistente con `tax-compliance-guardrails.md`.
