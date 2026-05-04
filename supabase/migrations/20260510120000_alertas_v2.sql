-- =============================================================================
-- Migration: 20260510120000_alertas_v2
-- Skills:    scenario-simulator (skill 8), regime-recommendation (skill 7),
--            tax-data-model (skill 6)
-- Purpose:   Hace empresa_id nullable en core.alertas para soportar alertas
--            workspace-level (ej. "no has registrado ninguna empresa") y
--            refresca RLS bajo el patrón de los tracks 9 y 7b.
-- =============================================================================

alter table core.alertas
    alter column empresa_id drop not null;

create index if not exists alertas_workspace_estado_idx
    on core.alertas (workspace_id, estado, created_at desc);

drop policy if exists alertas_select on core.alertas;
drop policy if exists alertas_update on core.alertas;
drop policy if exists alertas_insert on core.alertas;
drop policy if exists alertas_delete on core.alertas;

create policy alertas_select on core.alertas
    for select to authenticated
    using (
        workspace_id = app.workspace_id()
        and (empresa_id is null or app.has_empresa_access(empresa_id))
    );

create policy alertas_insert on core.alertas
    for insert to authenticated
    with check (
        workspace_id = app.workspace_id()
        and (empresa_id is null or app.has_empresa_access(empresa_id))
    );

create policy alertas_update on core.alertas
    for update to authenticated
    using (
        workspace_id = app.workspace_id()
        and (empresa_id is null or app.has_empresa_access(empresa_id))
    )
    with check (workspace_id = app.workspace_id());
