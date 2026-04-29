-- =============================================================================
-- Migration: 20260428120000_init_schemas
-- Skills:    tax-data-model (skill 6), fastapi-supabase-patterns (skill 10)
-- Purpose:   Crear extensiones, los 7 schemas del producto + schema `app` con
--            helpers de RLS. Los helpers leen claims del JWT (`app_metadata`)
--            inyectados por Supabase Auth; nunca consultan tablas, para evitar
--            loops de RLS y simplificar las policies.
-- =============================================================================

-- Extensiones requeridas. Supabase ya las trae habilitadas en proyectos nuevos;
-- el `if not exists` deja la migración idempotente.
create extension if not exists "pgcrypto";

-- -----------------------------------------------------------------------------
-- Schemas del producto
-- -----------------------------------------------------------------------------
create schema if not exists app;
create schema if not exists core;
create schema if not exists tax_params;
create schema if not exists tax_data;
create schema if not exists tax_calc;
create schema if not exists security;
create schema if not exists privacy;
create schema if not exists tax_rules;

comment on schema app is
    'Helpers de aplicación (RLS, utilidades). No contiene datos de negocio.';
comment on schema core is
    'Multi-tenant base: workspaces, miembros, empresas, outputs del motor.';
comment on schema tax_params is
    'Parámetros tributarios por año (tasas IDPC, tramos IGC, IVA, PPM, topes).';
comment on schema tax_data is
    'Datos sincronizados desde SII (DTEs, RCV, F29, F22, BHE).';
comment on schema tax_calc is
    'Cálculos del motor (RLI, registros tributarios, retiros).';
comment on schema security is
    'Certificados digitales (solo metadata + KMS ARN), mandatos, audit log inmutable.';
comment on schema privacy is
    'Derechos ARCOP, consentimientos e incidentes (Ley 19.628 + Ley 21.719).';
comment on schema tax_rules is
    'Reglas declarativas versionadas con vigencia temporal (skill 11).';

-- Permisos básicos: los roles de Supabase necesitan USAGE para acceder.
grant usage on schema app, core, tax_params, tax_data, tax_calc,
                  security, privacy, tax_rules
    to authenticated, service_role;

-- -----------------------------------------------------------------------------
-- Helpers de RLS — leen el JWT vía auth.jwt(); nunca consultan tablas.
--
-- Los claims viven en app_metadata. El login Supabase debe inyectar:
--   app_metadata.workspace_id     uuid del workspace activo
--   app_metadata.workspace_type   'pyme' | 'accounting_firm'
--   app_metadata.role             'owner' | 'cfo' | 'accountant_lead'
--                                 | 'accountant_staff' | 'viewer'
--   app_metadata.empresa_ids      uuid[] (cliente B: empresas asignadas;
--                                 cliente A puede omitirse)
-- -----------------------------------------------------------------------------

create or replace function app.workspace_id()
returns uuid
language sql
stable
as $$
    select nullif(auth.jwt() -> 'app_metadata' ->> 'workspace_id', '')::uuid
$$;
comment on function app.workspace_id() is
    'workspace_id activo del usuario autenticado (extraído del JWT).';

create or replace function app.workspace_type()
returns text
language sql
stable
as $$
    select coalesce(auth.jwt() -> 'app_metadata' ->> 'workspace_type', '')
$$;
comment on function app.workspace_type() is
    'Tipo de workspace del usuario (pyme | accounting_firm).';

create or replace function app.user_role()
returns text
language sql
stable
as $$
    select coalesce(auth.jwt() -> 'app_metadata' ->> 'role', '')
$$;
comment on function app.user_role() is
    'Rol del usuario dentro del workspace activo.';

create or replace function app.empresa_ids()
returns uuid[]
language sql
stable
as $$
    select coalesce(
        array(
            select jsonb_array_elements_text(
                coalesce(auth.jwt() -> 'app_metadata' -> 'empresa_ids',
                         '[]'::jsonb)
            )::uuid
        ),
        '{}'::uuid[]
    )
$$;
comment on function app.empresa_ids() is
    'Lista de empresa_id asignadas al usuario (relevante para accountant_staff).';

create or replace function app.has_empresa_access(target_empresa_id uuid)
returns boolean
language sql
stable
as $$
    -- accountant_staff queda restringido a empresas asignadas explícitamente.
    -- Otros roles (owner, cfo, viewer cliente A; accountant_lead cliente B)
    -- ven todas las empresas de su workspace; el chequeo de workspace_id en
    -- la policy se encarga del aislamiento de tenant.
    select case
        when app.user_role() = 'accountant_staff'
            then target_empresa_id = any(app.empresa_ids())
        else true
    end
$$;
comment on function app.has_empresa_access(uuid) is
    'true si el usuario puede acceder a la empresa dada bajo su rol.';

-- Las funciones helper son lectura pura sobre el JWT; las exponemos a los
-- roles autenticados.
grant execute on function
    app.workspace_id(),
    app.workspace_type(),
    app.user_role(),
    app.empresa_ids(),
    app.has_empresa_access(uuid)
    to authenticated, service_role;
