-- =============================================================================
-- Migration: 20260428120500_core_outputs
-- Skills:    tax-data-model (skill 6), regime-recommendation (skill 7),
--            scenario-simulator (skill 8), tax-compliance-guardrails (skill 1),
--            disclaimers-and-legal (skill 2)
-- Purpose:   Outputs del motor: escenarios simulados, recomendaciones, alertas.
--            Las columnas snapshot inmutable se agregan en B11.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- core.escenarios_simulacion
-- -----------------------------------------------------------------------------
create table if not exists core.escenarios_simulacion (
    id              uuid primary key default gen_random_uuid(),
    workspace_id    uuid not null
                    references core.workspaces(id) on delete cascade,
    empresa_id      uuid not null
                    references core.empresas(id) on delete cascade,
    tax_year        int not null,
    nombre          text not null,
    inputs          jsonb not null,
    outputs         jsonb not null,
    es_recomendado  boolean not null default false,
    engine_version  text not null,
    created_by      uuid references auth.users(id) on delete set null,
    created_at      timestamptz not null default now()
);

comment on table core.escenarios_simulacion is
    'Escenarios del simulador de cierre (skill 8). inputs = palancas y valores; outputs = RLI/IDPC/IGC/ahorro. es_recomendado lo marca el motor sobre el escenario lícito de menor carga total.';

create index escenarios_empresa_year_idx
    on core.escenarios_simulacion (empresa_id, tax_year, created_at desc);

-- -----------------------------------------------------------------------------
-- core.recomendaciones
-- -----------------------------------------------------------------------------
create table if not exists core.recomendaciones (
    id                      uuid primary key default gen_random_uuid(),
    workspace_id            uuid not null
                            references core.workspaces(id) on delete cascade,
    empresa_id              uuid not null
                            references core.empresas(id) on delete cascade,
    tax_year                int not null,
    tipo                    text not null,
    descripcion             text not null,
    fundamento_legal        jsonb not null,
    ahorro_estimado_clp     numeric(18, 2),
    disclaimer_version      text not null,
    engine_version          text not null,
    inputs_snapshot         jsonb not null,
    outputs                 jsonb not null,
    created_at              timestamptz not null default now(),
    dismissed_at            timestamptz,
    acted_on_at             timestamptz
);

comment on table core.recomendaciones is
    'Recomendaciones generadas por el motor. tipo restringido a la lista blanca de tax-compliance-guardrails.md. fundamento_legal con artículo + circular/oficio. disclaimer_version apunta al texto versionado en disclaimers-and-legal.md.';
comment on column core.recomendaciones.disclaimer_version is
    'Versión del disclaimer aplicado (ej. disclaimer-recomendacion-v1). Cambios = nueva versión, nunca edición in-place.';

create index recomendaciones_empresa_year_idx
    on core.recomendaciones (empresa_id, tax_year, created_at desc);

-- -----------------------------------------------------------------------------
-- core.alertas
-- -----------------------------------------------------------------------------
create table if not exists core.alertas (
    id                      uuid primary key default gen_random_uuid(),
    workspace_id            uuid not null
                            references core.workspaces(id) on delete cascade,
    empresa_id              uuid not null
                            references core.empresas(id) on delete cascade,
    tipo                    text not null,
    severidad               text not null
                            check (severidad in ('info', 'warning', 'critical')),
    titulo                  text not null,
    descripcion             text not null,
    ahorro_estimado_clp     numeric(18, 2),
    accion_recomendada      text,
    estado                  text not null default 'nueva'
                            check (estado in (
                                'nueva', 'vista', 'descartada', 'accionada'
                            )),
    fecha_limite            date,
    created_at              timestamptz not null default now(),
    updated_at              timestamptz not null default now()
);

comment on table core.alertas is
    'Alertas proactivas pre-cierre. Catálogo inicial en fase 5. estado refleja workflow del usuario.';

create trigger alertas_touch_updated_at
    before update on core.alertas
    for each row execute function app.touch_updated_at();

create index alertas_empresa_estado_severidad_idx
    on core.alertas (empresa_id, estado, severidad);
