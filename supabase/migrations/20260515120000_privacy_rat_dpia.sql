-- =============================================================================
-- Migration: 20260515120000_privacy_rat_dpia
-- Skills:    chilean-data-privacy (skill 5)
-- Purpose:   Cumplimiento Ley 21.719 (vigor 2026-12-01):
--              * privacy.rat_records  — Registro de Actividades de Tratamiento
--                                       (art. 15-16 Ley 21.719). Documenta toda
--                                       actividad de tratamiento del workspace.
--              * privacy.dpia_records — Evaluación de Impacto en Protección de
--                                       Datos (art. 35). Obligatoria para
--                                       tratamientos de alto riesgo.
--            Ambas son work del DPO; restringidas a roles owner / accountant_lead
--            del workspace. RLS estándar por workspace_id.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- privacy.rat_records — Registro de Actividades de Tratamiento
-- -----------------------------------------------------------------------------
create table if not exists privacy.rat_records (
    id                              uuid primary key default gen_random_uuid(),
    workspace_id                    uuid not null
                                    references core.workspaces(id) on delete cascade,
    nombre_actividad                text not null,
    finalidad                       text not null,
    base_legal                      text not null
                                    check (base_legal in (
                                        'consentimiento', 'contrato',
                                        'interes_legitimo', 'obligacion_legal',
                                        'interes_vital', 'interes_publico'
                                    )),
    categorias_titulares            jsonb not null default '[]'::jsonb,
    categorias_datos                jsonb not null default '[]'::jsonb,
    datos_sensibles                 boolean not null default false,
    encargados_referenciados        jsonb not null default '[]'::jsonb,
    transferencias_internacionales  jsonb not null default '[]'::jsonb,
    plazo_conservacion              text not null,
    medidas_seguridad               jsonb not null default '[]'::jsonb,
    responsable_email               text not null,
    created_at                      timestamptz not null default now(),
    updated_at                      timestamptz not null default now(),
    archived_at                     timestamptz
);

comment on table privacy.rat_records is
    'Registro de Actividades de Tratamiento (RAT) — art. 15-16 Ley 21.719. Se mantiene actualizado por el DPO; archived_at señaliza retiro lógico.';

create index rat_records_workspace_idx
    on privacy.rat_records (workspace_id, created_at desc)
    where archived_at is null;

create trigger rat_records_touch_updated_at
    before update on privacy.rat_records
    for each row execute function app.touch_updated_at();

-- -----------------------------------------------------------------------------
-- privacy.dpia_records — Evaluación de Impacto en Protección de Datos
-- -----------------------------------------------------------------------------
create table if not exists privacy.dpia_records (
    id                          uuid primary key default gen_random_uuid(),
    workspace_id                uuid not null
                                references core.workspaces(id) on delete cascade,
    rat_id                      uuid references privacy.rat_records(id)
                                on delete set null,
    nombre_evaluacion           text not null,
    descripcion_tratamiento     text not null,
    necesidad_proporcionalidad  text not null,
    riesgos_identificados       jsonb not null default '[]'::jsonb,
    medidas_mitigacion          jsonb not null default '[]'::jsonb,
    riesgo_residual             text not null
                                check (riesgo_residual in (
                                    'bajo', 'medio', 'alto'
                                )),
    aprobado_por_dpo_email      text,
    aprobado_at                 timestamptz,
    version                     int not null default 1,
    created_at                  timestamptz not null default now(),
    updated_at                  timestamptz not null default now()
);

comment on table privacy.dpia_records is
    'Evaluación de Impacto en Protección de Datos (DPIA / EIPD) — art. 35 Ley 21.719. Obligatoria para tratamientos de alto riesgo. Sólo se considera vigente cuando aprobado_at no es nulo.';

create index dpia_records_workspace_idx
    on privacy.dpia_records (workspace_id, created_at desc);
create index dpia_records_rat_idx
    on privacy.dpia_records (rat_id);

create trigger dpia_records_touch_updated_at
    before update on privacy.dpia_records
    for each row execute function app.touch_updated_at();

-- -----------------------------------------------------------------------------
-- RLS — patrón estándar por workspace.
-- -----------------------------------------------------------------------------
alter table privacy.rat_records enable row level security;

create policy rat_records_select on privacy.rat_records
    for select to authenticated
    using (workspace_id = app.workspace_id());

create policy rat_records_modify on privacy.rat_records
    for all to authenticated
    using (
        workspace_id = app.workspace_id()
        and app.user_role() in ('owner', 'accountant_lead')
    )
    with check (
        workspace_id = app.workspace_id()
        and app.user_role() in ('owner', 'accountant_lead')
    );

alter table privacy.dpia_records enable row level security;

create policy dpia_records_select on privacy.dpia_records
    for select to authenticated
    using (workspace_id = app.workspace_id());

create policy dpia_records_modify on privacy.dpia_records
    for all to authenticated
    using (
        workspace_id = app.workspace_id()
        and app.user_role() in ('owner', 'accountant_lead')
    )
    with check (
        workspace_id = app.workspace_id()
        and app.user_role() in ('owner', 'accountant_lead')
    );
