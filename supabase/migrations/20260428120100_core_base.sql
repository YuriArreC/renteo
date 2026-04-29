-- =============================================================================
-- Migration: 20260428120100_core_base
-- Skills:    tax-data-model (skill 6), dual-ux-patterns (skill 9)
-- Purpose:   Tablas multi-tenant base. workspaces (cliente A: pyme;
--            cliente B: accounting_firm), miembros con rol, empresas y
--            asignaciones empresa→staff para cliente B.
-- =============================================================================

-- Función reutilizable para trigger BEFORE UPDATE que mantiene updated_at.
create or replace function app.touch_updated_at()
returns trigger
language plpgsql
as $$
begin
    new.updated_at := now();
    return new;
end;
$$;
comment on function app.touch_updated_at() is
    'Trigger reutilizable: setea NEW.updated_at = now() en cada UPDATE.';

-- -----------------------------------------------------------------------------
-- core.workspaces
-- -----------------------------------------------------------------------------
create table if not exists core.workspaces (
    id              uuid primary key default gen_random_uuid(),
    name            text not null,
    type            text not null
                    check (type in ('pyme', 'accounting_firm')),
    billing_plan    text not null default 'free'
                    check (billing_plan in (
                        'free', 'pyme_basic', 'pyme_pro',
                        'firm_basic', 'firm_pro'
                    )),
    dpo_user_id     uuid references auth.users(id) on delete restrict,
    created_at      timestamptz not null default now(),
    updated_at      timestamptz not null default now(),
    deleted_at      timestamptz
);

comment on table core.workspaces is
    'Tenant raíz. Cliente A (pyme): 1 empresa o pocas; cliente B (accounting_firm): cartera N empresas.';
comment on column core.workspaces.dpo_user_id is
    'Delegado de Protección de Datos designado (Ley 21.719). Inicialmente contador socio.';

create trigger workspaces_touch_updated_at
    before update on core.workspaces
    for each row execute function app.touch_updated_at();

-- -----------------------------------------------------------------------------
-- core.workspace_members
-- -----------------------------------------------------------------------------
create table if not exists core.workspace_members (
    id              uuid primary key default gen_random_uuid(),
    workspace_id    uuid not null references core.workspaces(id) on delete cascade,
    user_id         uuid not null references auth.users(id) on delete cascade,
    role            text not null
                    check (role in (
                        'owner', 'cfo',
                        'accountant_lead', 'accountant_staff',
                        'viewer'
                    )),
    invited_at      timestamptz not null default now(),
    accepted_at     timestamptz,
    unique (workspace_id, user_id)
);

comment on table core.workspace_members is
    'Membresía usuario↔workspace con rol. Roles cliente A: owner/cfo/viewer. Roles cliente B: accountant_lead/accountant_staff/viewer.';

create index workspace_members_user_idx
    on core.workspace_members (user_id);

-- -----------------------------------------------------------------------------
-- core.empresas
-- -----------------------------------------------------------------------------
create table if not exists core.empresas (
    id                          uuid primary key default gen_random_uuid(),
    workspace_id                uuid not null references core.workspaces(id) on delete cascade,
    rut                         text not null
                                check (rut ~ '^[0-9]{1,8}-[0-9Kk]$'),
    razon_social                text not null,
    giro                        text,
    regimen_actual              text not null default 'desconocido'
                                check (regimen_actual in (
                                    '14_a', '14_d_3', '14_d_8',
                                    'presunta', 'desconocido'
                                )),
    fecha_inicio_actividades    date,
    capital_inicial_uf          numeric(18, 4),
    es_grupo_empresarial        boolean not null default false,
    sociedad_dominante_id       uuid references core.empresas(id) on delete set null,
    created_at                  timestamptz not null default now(),
    updated_at                  timestamptz not null default now(),
    deleted_at                  timestamptz,
    unique (workspace_id, rut)
);

comment on table core.empresas is
    'Contribuyentes (sujetos del cálculo tributario). regimen_actual = ''desconocido'' hasta sync con SII.';
comment on column core.empresas.regimen_actual is
    'Auto-detectado de SII cuando hay sync; ''desconocido'' antes del primer sync.';

create trigger empresas_touch_updated_at
    before update on core.empresas
    for each row execute function app.touch_updated_at();

create index empresas_workspace_idx
    on core.empresas (workspace_id) where deleted_at is null;

-- -----------------------------------------------------------------------------
-- core.accountant_assignments — cliente B: qué staff atiende qué empresa
-- -----------------------------------------------------------------------------
create table if not exists core.accountant_assignments (
    workspace_id        uuid not null references core.workspaces(id) on delete cascade,
    empresa_id          uuid not null references core.empresas(id) on delete cascade,
    user_id             uuid not null references auth.users(id) on delete cascade,
    permission_level    text not null
                        check (permission_level in (
                            'read', 'read_write', 'full'
                        )),
    created_at          timestamptz not null default now(),
    primary key (workspace_id, empresa_id, user_id)
);

comment on table core.accountant_assignments is
    'Cliente B: asignación staff↔empresa con nivel de permiso. Cambios deben replicarse en JWT app_metadata.empresa_ids[] vía hook de Supabase Auth.';

create index accountant_assignments_user_idx
    on core.accountant_assignments (user_id);
