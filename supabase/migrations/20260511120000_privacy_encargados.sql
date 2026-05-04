-- =============================================================================
-- Migration: 20260511120000_privacy_encargados
-- Skills:    chilean-data-privacy (skill 5)
-- Purpose:   Registro de encargados de tratamiento (Ley 21.719 obliga
--            publicar la lista en la política de privacidad). Cada
--            encargado tiene un DPA firmado con vigencia; alertas de
--            vencimiento las consume el panel admin.
-- =============================================================================

create table if not exists privacy.encargados (
    id                  uuid primary key default gen_random_uuid(),
    nombre              text not null,
    proposito           text not null,
    pais_tratamiento    text not null default 'CL',
    dpa_firmado_at      date,
    dpa_vigente_hasta   date,
    dpa_url             text,
    contacto_dpo        text,
    notas               text,
    activo              boolean not null default true,
    created_at          timestamptz not null default now(),
    updated_at          timestamptz not null default now(),
    deleted_at          timestamptz,
    check (
        dpa_vigente_hasta is null
        or dpa_firmado_at is null
        or dpa_vigente_hasta > dpa_firmado_at
    )
);

comment on table privacy.encargados is
    'Encargados de tratamiento (Ley 21.719). El público ve nombre + propósito + país; admin gestiona DPAs.';

create index encargados_activo_idx
    on privacy.encargados (activo, nombre);

-- RLS: lectura abierta a authenticated (los datos no son confidenciales);
-- mutaciones solo desde service_role (vía panel admin con doble firma o
-- migraciones).
alter table privacy.encargados enable row level security;

create policy encargados_select on privacy.encargados
    for select to authenticated using (deleted_at is null);

grant select on privacy.encargados to authenticated;
grant select on privacy.encargados to anon;

create policy encargados_select_anon on privacy.encargados
    for select to anon using (deleted_at is null);

create trigger encargados_touch_updated_at
    before update on privacy.encargados
    for each row execute function app.touch_updated_at();

-- -----------------------------------------------------------------------------
-- Seeds: encargados actuales del producto.
-- 🟡 dpa_firmado_at / dpa_vigente_hasta = NULL hasta firmar DPAs
-- reales con cada proveedor antes del go-live público.
-- -----------------------------------------------------------------------------
insert into privacy.encargados
    (nombre, proposito, pais_tratamiento, contacto_dpo, notas)
values
    ('Supabase Inc.',
     'Base de datos PostgreSQL + autenticación + almacenamiento.',
     'US',
     'privacy@supabase.com',
     'Encargado principal. Datos en Postgres con RLS multi-tenant.'),
    ('Amazon Web Services',
     'KMS para custodia de certificados digitales SII y S3 para PDFs cifrados.',
     'BR',
     'aws-privacy@amazon.com',
     'Región sa-east-1 (São Paulo). Reduce latencia con SII.'),
    ('Vercel Inc.',
     'Hosting del frontend Next.js y CDN edge.',
     'US',
     'privacy@vercel.com',
     'Solo páginas estáticas y SSR; sin datos tributarios persistentes.'),
    ('Render Services',
     'Hosting del backend FastAPI (workers Celery en fase 5).',
     'US',
     'privacy@render.com',
     'Procesa requests autenticadas; sin almacenamiento permanente.'),
    ('Sentry (Functional Software)',
     'Captura de errores y trazabilidad observable (sin PII).',
     'US',
     'privacy@sentry.io',
     'send_default_pii=false; structlog filtra RUTs y JWTs antes.'),
    ('SimpleAPI',
     'Proveedor primario de integración con SII (RCV, F29, F22, BHE).',
     'CL',
     'soporte@simpleapi.cl',
     '🟡 Fase 1+ (track skill 4). DPA pendiente.'),
    ('BaseAPI',
     'Proveedor backup de integración con SII (failover de SimpleAPI).',
     'CL',
     'soporte@baseapi.cl',
     '🟡 Fase 1+ (track skill 4). DPA pendiente.')
on conflict do nothing;
