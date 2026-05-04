-- =============================================================================
-- Migration: 20260512120000_sii_sync_log
-- Skills:    sii-integration (skill 4), tax-data-model (skill 6)
-- Purpose:   Bitácora append-only de sincronizaciones SII por empresa.
--            Cada llamada de POST /api/empresas/{id}/sync-sii registra una
--            fila con estado, provider, ventana de períodos y conteos.
--            Sirve para 1) mostrar última sync en UI, 2) reintento manual,
--            3) auditoría. RLS multi-tenant idéntico al resto de tax_data.
-- =============================================================================

create table if not exists tax_data.sii_sync_log (
    id              uuid primary key default gen_random_uuid(),
    workspace_id    uuid not null
                    references core.workspaces(id) on delete cascade,
    empresa_id      uuid not null
                    references core.empresas(id) on delete cascade,
    provider        text not null
                    check (provider in (
                        'mock', 'simpleapi', 'baseapi', 'apigateway'
                    )),
    kind            text not null
                    check (kind in ('rcv', 'f29', 'f22', 'full')),
    status          text not null
                    check (status in (
                        'started', 'success', 'failed', 'partial'
                    )),
    period_from     text
                    check (period_from is null
                           or period_from ~ '^[0-9]{4}-(0[1-9]|1[0-2])$'),
    period_to       text
                    check (period_to is null
                           or period_to ~ '^[0-9]{4}-(0[1-9]|1[0-2])$'),
    rows_inserted   int not null default 0,
    rows_updated    int not null default 0,
    error_class     text,
    error_message   text,
    started_at      timestamptz not null default now(),
    finished_at     timestamptz,
    created_by      uuid references auth.users(id) on delete set null
);

comment on table tax_data.sii_sync_log is
    'Bitácora append-only de sincronizaciones SII. Una fila por intento por empresa.';

create index sii_sync_log_empresa_idx
    on tax_data.sii_sync_log (empresa_id, started_at desc);
create index sii_sync_log_workspace_idx
    on tax_data.sii_sync_log (workspace_id, started_at desc);

alter table tax_data.sii_sync_log enable row level security;

create policy sii_sync_log_select on tax_data.sii_sync_log
    for select to authenticated
    using (
        workspace_id = app.workspace_id()
        and app.has_empresa_access(empresa_id)
    );

-- INSERT/UPDATE solo desde service_role (el endpoint corre con service_session).
