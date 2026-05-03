-- =============================================================================
-- Migration: 20260503120000_escenarios_v2
-- Skills:    scenario-simulator (skill 8), tax-data-model (skill 6)
-- Purpose:   Permitir escenarios de simulación a nivel de workspace (sin
--            empresa_id) para Track 9 MVP, antes de que el onboarding cree
--            empresas. Agrega columnas `regimen` y `rules_snapshot_hash`
--            previstas en skill 8 / 11.
-- =============================================================================

-- empresa_id nullable: permite simulaciones standalone del workspace.
alter table core.escenarios_simulacion
    alter column empresa_id drop not null;

alter table core.escenarios_simulacion
    add column if not exists regimen text;

alter table core.escenarios_simulacion
    add column if not exists rules_snapshot_hash text;

comment on column core.escenarios_simulacion.regimen is
    'Régimen sobre el que se simuló (14_a, 14_d_3, 14_d_8). Indexado para listar.';
comment on column core.escenarios_simulacion.rules_snapshot_hash is
    'SHA-256 del rule set + parámetros usados (skill 11). NULL para escenarios pre-fase 6.';

create index if not exists escenarios_workspace_year_idx
    on core.escenarios_simulacion (workspace_id, tax_year, created_at desc);

-- -----------------------------------------------------------------------------
-- RLS: las policies originales asumen empresa_id NOT NULL. Las refrescamos
-- para permitir empresa_id NULL bajo el mismo workspace.
-- -----------------------------------------------------------------------------
drop policy if exists escenarios_select on core.escenarios_simulacion;
drop policy if exists escenarios_insert on core.escenarios_simulacion;
drop policy if exists escenarios_update on core.escenarios_simulacion;
drop policy if exists escenarios_delete on core.escenarios_simulacion;

create policy escenarios_select on core.escenarios_simulacion
    for select to authenticated
    using (
        workspace_id = app.workspace_id()
        and (empresa_id is null or app.has_empresa_access(empresa_id))
    );

create policy escenarios_insert on core.escenarios_simulacion
    for insert to authenticated
    with check (
        workspace_id = app.workspace_id()
        and (empresa_id is null or app.has_empresa_access(empresa_id))
    );

create policy escenarios_update on core.escenarios_simulacion
    for update to authenticated
    using (
        workspace_id = app.workspace_id()
        and (empresa_id is null or app.has_empresa_access(empresa_id))
    )
    with check (workspace_id = app.workspace_id());

create policy escenarios_delete on core.escenarios_simulacion
    for delete to authenticated
    using (
        workspace_id = app.workspace_id()
        and (empresa_id is null or app.has_empresa_access(empresa_id))
    );
