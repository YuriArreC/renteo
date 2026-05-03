-- =============================================================================
-- Migration: 20260507120000_track_7b_recomendaciones_v2
-- Skills:    regime-recommendation (skill 7), tax-compliance-guardrails (1),
--            tax-rules-versioning (skill 11)
-- Purpose:   Permitir recomendaciones a nivel de workspace (sin empresa_id)
--            mientras el onboarding no cree empresas, y registrar quién
--            generó la recomendación (created_by). Refresca RLS para
--            soportar empresa_id NULL bajo el patrón del track 9.
-- =============================================================================

alter table core.recomendaciones
    alter column empresa_id drop not null;

alter table core.recomendaciones
    add column if not exists created_by uuid references auth.users(id)
        on delete set null;

comment on column core.recomendaciones.created_by is
    'Usuario que originó la recomendación (responde el wizard). Nullable si llega desde un worker batch (cliente B fase 6+).';

create index if not exists recomendaciones_workspace_year_idx
    on core.recomendaciones (workspace_id, tax_year, created_at desc);

-- RLS — políticas originales asumen empresa_id NOT NULL.
drop policy if exists recomendaciones_select on core.recomendaciones;
drop policy if exists recomendaciones_update on core.recomendaciones;
drop policy if exists recomendaciones_insert on core.recomendaciones;
drop policy if exists recomendaciones_delete on core.recomendaciones;

create policy recomendaciones_select on core.recomendaciones
    for select to authenticated
    using (
        workspace_id = app.workspace_id()
        and (empresa_id is null or app.has_empresa_access(empresa_id))
    );

create policy recomendaciones_insert on core.recomendaciones
    for insert to authenticated
    with check (
        workspace_id = app.workspace_id()
        and (empresa_id is null or app.has_empresa_access(empresa_id))
    );

create policy recomendaciones_update on core.recomendaciones
    for update to authenticated
    using (
        workspace_id = app.workspace_id()
        and (empresa_id is null or app.has_empresa_access(empresa_id))
    )
    with check (workspace_id = app.workspace_id());

create policy recomendaciones_delete on core.recomendaciones
    for delete to authenticated
    using (
        workspace_id = app.workspace_id()
        and (empresa_id is null or app.has_empresa_access(empresa_id))
    );
