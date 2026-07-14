# Demo cerrado en producción — runbook

> **Qué es esto.** Renteo desplegado en infraestructura de producción real,
> pero con **un único usuario ficticio** y el registro público **cerrado**.
> Sirve para mostrar el producto de punta a punta —incluidas las
> recomendaciones— sin exponer a nadie a un motor tributario que todavía no
> validó un contador socio.

---

## Por qué cerrado, y no abierto

No es burocracia interna: es la mitigación de un riesgo **propio de Renteo**.

El **art. 100 bis del Código Tributario** —en su texto vigente, sustituido por
la Ley 21.713 y luego por la Ley 21.755 (D.O. 11-jul-2025)— sanciona a **quien
diseña o planifica** los actos declarados abusivos o simulados, con **100 UTA**
(250 con reiteración, o hasta el total de los honorarios con tope de 250 UTA).

Dos hechos que definen todo este runbook:

1. **Renteo, al recomendar, actúa funcionalmente como diseñador/planificador.**
2. **La exención del art. 14 letra D ampara al *contribuyente*, no al *asesor*.**
   Que el cliente sea una PYME Pro PyME **no** atenúa la exposición de Renteo.

Con un contribuyente **ficticio** no hay exposición: nadie real actúa sobre la
recomendación, y no hay diferencia de impuesto que perseguir. Con registro
abierto, sí la habría.

A favor: la Circular SII N°31/2025 §6.3 precisa que lo sancionado es **la
actividad intelectual del diseño**, y que "la mera implementación de lo
diseñado o planificado no cumple con los presupuestos de hecho". Un motor que
solo *reconoce y documenta* está lejos del tipo; uno que *propone estructuras*
se acerca. Mientras tanto, el encierro es la garantía barata.

---

## Las tres capas de cierre

Ninguna alcanza sola. Se despliegan las tres.

| # | Capa | Dónde | Qué pasa si falla |
| --- | --- | --- | --- |
| 1 | **Signup cerrado** | Dashboard de Supabase | Alguien se registra… y choca con la capa 2. |
| 2 | **Allowlist `ALLOWED_USER_EMAILS`** | API, en `verify_jwt` | ⛔ **Sin esta, la app queda abierta.** La API **no arranca** en `production` si está vacía. |
| 3 | **Banner "motor no validado"** | UI, en cada output del motor | El usuario no sabría que las reglas no están firmadas. |

La capa 2 es el gate real: se aplica en `verify_jwt`, o sea que cubre **todo
endpoint autenticado** de una sola vez, no endpoint por endpoint.

---

## Pasos de despliegue

### 1. Base de datos

```bash
supabase link --project-ref <PROJECT_REF>
supabase db push
```

Esto aplica, entre otras:

- `20260713130000_citas_nga_circular_31_2025.sql` — corrige la cita de la NGA
  (la Circular 65/2015 fue **dejada sin efecto** por la 31/2025) publicando la
  whitelist v3 y deprecando v1/v2.
- `20260713140000_demo_cerrado.sql` — usuario ficticio, workspace, empresa
  (`Ferretería Demo SpA`, 14 D N°3), consentimiento y el texto del banner.

Verificación rápida (SQL editor del dashboard):

```sql
-- Debe devolver 0. Si devuelve más, hay una regla viva citando norma derogada.
select count(*) from tax_rules.rule_sets
 where status = 'published' and fuente_legal::text like '%65/2015%';

-- El hook debe emitir claims de tenancy para el usuario demo.
select public.custom_access_token_hook(
  '{"user_id":"00000000-0000-0000-0000-00000000de01","claims":{}}'::jsonb
) -> 'claims' -> 'app_metadata';
-- → {"role":"owner","workspace_id":"...de02","workspace_type":"pyme","empresa_ids":[]}
```

### 2. Contraseña del usuario demo

La migración **no** setea contraseña (no se commitean credenciales). El usuario
queda creado y confirmado, pero no puede entrar hasta correr:

```bash
export SUPABASE_URL=https://<PROJECT_REF>.supabase.co
export SUPABASE_SERVICE_ROLE_KEY=<service_role key>   # NO la anon key
export DEMO_USER_PASSWORD='<contraseña fuerte, mín. 12 caracteres>'
python scripts/set_demo_password.py
```

### 3. Cerrar el registro público

Dashboard de Supabase → **Authentication → Providers → Email** →
**"Enable sign-ups" = OFF**.

> `supabase/config.toml` deja `enable_signup = true` **a propósito**: ese
> archivo gobierna el stack local, y los tests e2e registran usuarios. Cerrarlo
> ahí rompe CI sin cerrar nada en producción.

### 4. Variables de entorno de la API (Render)

```bash
ENVIRONMENT=production
ALLOWED_USER_EMAILS=demo@renteo.cl,<tu-email>     # 🔴 sin esto la API NO arranca
INTERNAL_ADMIN_EMAILS=<tu-email>                  # panel admin de reglas
DATABASE_URL=<connection string de Supabase>
SUPABASE_JWKS_URL=https://<PROJECT_REF>.supabase.co/auth/v1/.well-known/jwks.json
CORS_ALLOWED_ORIGINS=https://<dominio-vercel>
```

> **`DATABASE_URL` y RLS.** La sesión de la aplicación baja el rol a
> `authenticated` (`SET LOCAL role`) antes de cada request, así que las
> policies multi-tenant se aplican **aunque el rol de la cadena de conexión sea
> `postgres` o `service_role`**. Eso no era así hasta este cambio: los claims
> por sí solos no activan RLS si el rol conectado tiene BYPASSRLS. Ver
> `apps/api/src/db.py` y el test `tests/integration/test_rls_app_session.py`.

### 5. Frontend (Vercel)

```bash
NEXT_PUBLIC_SUPABASE_URL=https://<PROJECT_REF>.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=<anon key>
NEXT_PUBLIC_API_URL=https://<render-api>.onrender.com
```

### 6. Verificación post-deploy

- [ ] `GET /healthz` y `GET /readyz` responden 200.
- [ ] Login con `demo@renteo.cl` entra al dashboard (no a `/onboarding`: el
      workspace ya existe).
- [ ] La empresa **Ferretería Demo SpA (ficticia)** aparece en el dashboard.
- [ ] El wizard de régimen emite un diagnóstico, y arriba se ve el banner
      ámbar **"Demo — motor sin validar"**.
- [ ] Un usuario **fuera** de `ALLOWED_USER_EMAILS` recibe **403** en cualquier
      endpoint autenticado.
- [ ] Registrarse desde `/signup` **falla** (signup cerrado en Supabase).

---

## Qué sigue vigente (y qué NO se hizo)

- **La firma del CONTADOR_SOCIO sigue pendiente.** Las reglas corren con firma
  **placeholder** (`c001`/`a001`). El contenido de las reglas nuevas está
  verificado contra fuente primaria; la firma no.
- Los `fuente_legal` de `tax_params` siguen diciendo `PLACEHOLDER`: son las
  tasas y topes que espera firmar el contador (TODO-CONTADOR #1 a #9).
- **No se abre a clientes reales.** Cuando llegue el primero: firmar las reglas,
  retirar el banner (publicando una v2 de `banner-motor-no-validado` con
  `effective_to` en la v1), vaciar `ALLOWED_USER_EMAILS` y reabrir el signup —
  **en ese orden**.

## Cómo retirar el demo más adelante

```sql
-- 1. Retirar el banner (no se borra: se cierra su vigencia).
update privacy.legal_texts
   set effective_to = current_date
 where key = 'banner-motor-no-validado' and version = 'v1';

-- 2. Borrar el tenant ficticio (cascada limpia empresa, membresía, consentimiento).
delete from core.workspaces where id = '00000000-0000-0000-0000-00000000de02';
delete from auth.users     where id = '00000000-0000-0000-0000-00000000de01';
```

Y en la API: quitar `ALLOWED_USER_EMAILS` (la allowlist se desactiva sola al
quedar vacía) **solo después** de que el motor esté firmado.
