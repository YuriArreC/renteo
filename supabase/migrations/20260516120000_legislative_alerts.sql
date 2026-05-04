-- =============================================================================
-- Migration: 20260516120000_legislative_alerts
-- Skills:    tax-rules-versioning (skill 11) — closure
-- Purpose:   Watchdog legislativo: tabla bitácora de cambios detectados en
--            DOF / SII (circulares, oficios, resoluciones) / Ley de
--            Presupuestos. Cada hit dispara un ticket que el equipo legal
--            revisa y, si corresponde, promueve a draft de regla con
--            doble firma (admin_rules workflow existente).
--
--            Workflow:
--              1. Worker watchdog (Celery beat 04:00 SCL) corre cada source
--                 y, por cada hit nuevo, INSERT con status='open'.
--              2. Equipo legal revisa en /admin/legislation:
--                 - dismiss → status='dismissed' (cambio no relevante).
--                 - ignore  → status='ignored' (ya cubierto en otra regla).
--                 - draft   → status='drafted' (creado un draft en
--                              tax_rules.rule_sets con propuesta_diff).
--              3. Draft sigue su workflow normal (validar, doble firma,
--                 publicar).
--
--            Multi-source dedup por (source, source_id): si DOF publica
--            la misma circular dos veces, no duplicamos el ticket.
-- =============================================================================

create table if not exists tax_rules.legislative_alerts (
    id                  uuid primary key default gen_random_uuid(),
    source              text not null
                        check (source in (
                            'dof',
                            'sii_circular',
                            'sii_oficio',
                            'sii_resolucion',
                            'presupuestos'
                        )),
    source_id           text not null,
    title               text not null,
    summary             text,
    url                 text,
    publication_date    date not null,
    status              text not null default 'open'
                        check (status in (
                            'open',
                            'dismissed',
                            'ignored',
                            'drafted'
                        )),
    target_domain       text,
    target_key          text,
    propuesta_diff      jsonb not null default '{}'::jsonb,
    drafted_rule_set_id uuid references tax_rules.rule_sets(id)
                        on delete set null,
    reviewed_by         uuid references auth.users(id) on delete set null,
    reviewed_at         timestamptz,
    review_note         text,
    created_at          timestamptz not null default now(),
    updated_at          timestamptz not null default now(),
    unique (source, source_id)
);

comment on table tax_rules.legislative_alerts is
    'Bitácora de cambios legislativos detectados por el watchdog (skill 11). Cada hit es un ticket que el equipo legal revisa y promueve, si corresponde, a un draft de regla.';
comment on column tax_rules.legislative_alerts.source_id is
    'ID estable de la fuente (folio circular, número resolución, ID DOF). Junto con source forma el unique key de dedup.';
comment on column tax_rules.legislative_alerts.propuesta_diff is
    'Diff JSON propuesto al rule_set (target_domain, target_key) — sirve de borrador para el draft. Lo arma el monitor o lo edita el revisor.';

create index legislative_alerts_status_pubdate_idx
    on tax_rules.legislative_alerts (status, publication_date desc);
create index legislative_alerts_source_idx
    on tax_rules.legislative_alerts (source, publication_date desc);

create trigger legislative_alerts_touch_updated_at
    before update on tax_rules.legislative_alerts
    for each row execute function app.touch_updated_at();

-- RLS: lectura/mutación solo desde service_role (admin endpoints corren
-- con service_session). authenticated no tiene acceso directo: el panel
-- pasa por endpoints con require_internal_admin.
alter table tax_rules.legislative_alerts enable row level security;
-- Sin policy = bloqueado para roles no-superuser (el patrón estándar
-- de skill 11 para tablas exclusivas del backoffice).
