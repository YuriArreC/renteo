-- =============================================================================
-- Migration: 20260428120700_privacy
-- Skills:    chilean-data-privacy (skill 5), tax-data-model (skill 6),
--            disclaimers-and-legal (skill 2)
-- Purpose:   Tablas de cumplimiento Ley 19.628 + Ley 21.719: derechos ARCOP,
--            consentimientos versionados e incidentes de brecha.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- privacy.arcop_requests — derechos ARCOP (plazo máx 30 días)
-- -----------------------------------------------------------------------------
create table if not exists privacy.arcop_requests (
    id              uuid primary key default gen_random_uuid(),
    workspace_id    uuid not null
                    references core.workspaces(id) on delete cascade,
    user_id         uuid not null references auth.users(id) on delete restrict,
    tipo            text not null
                    check (tipo in (
                        'acceso', 'rectificacion', 'cancelacion',
                        'oposicion', 'portabilidad'
                    )),
    estado          text not null default 'recibida'
                    check (estado in (
                        'recibida', 'en_proceso', 'cumplida', 'rechazada'
                    )),
    descripcion     text,
    recibida_at     timestamptz not null default now(),
    respondida_at   timestamptz,
    respuesta       text
);

comment on table privacy.arcop_requests is
    'Solicitudes ARCOP (Acceso, Rectificación, Cancelación, Oposición, Portabilidad). Plazo de respuesta máximo 30 días corridos (Ley 21.719).';

create index arcop_requests_user_idx
    on privacy.arcop_requests (user_id, recibida_at desc);
create index arcop_requests_estado_idx
    on privacy.arcop_requests (estado, recibida_at desc);

-- -----------------------------------------------------------------------------
-- privacy.consentimientos — consentimientos otorgados, versionados
-- -----------------------------------------------------------------------------
create table if not exists privacy.consentimientos (
    id                  uuid primary key default gen_random_uuid(),
    user_id             uuid not null references auth.users(id) on delete cascade,
    workspace_id        uuid references core.workspaces(id) on delete cascade,
    empresa_id          uuid references core.empresas(id) on delete cascade,
    tipo_consentimiento text not null
                        check (tipo_consentimiento in (
                            'tratamiento_datos',
                            'certificado_digital',
                            'mandato_digital'
                        )),
    version_texto       text not null,
    otorgado_at         timestamptz not null default now(),
    revocado_at         timestamptz,
    ip_otorgamiento     inet
);

comment on table privacy.consentimientos is
    'Registro auditable de consentimientos. version_texto apunta al bloque versionado en disclaimers-and-legal.md (ej. consentimiento-tratamiento-datos-v1).';

create index consentimientos_user_tipo_idx
    on privacy.consentimientos (user_id, tipo_consentimiento, otorgado_at desc);

-- -----------------------------------------------------------------------------
-- privacy.incidentes_brecha — Ley 21.719 obliga notificación 72h
-- -----------------------------------------------------------------------------
create table if not exists privacy.incidentes_brecha (
    id                          uuid primary key default gen_random_uuid(),
    descripcion                 text not null,
    detectado_at                timestamptz not null,
    contenido_at                timestamptz,
    notificado_agencia_at       timestamptz,
    notificado_titulares_at     timestamptz,
    post_mortem_url             text,
    created_at                  timestamptz not null default now()
);

comment on table privacy.incidentes_brecha is
    'Incidentes de brecha de datos. Notificación a la Agencia sin dilación indebida (estándar 72h). Notificación a titulares cuando el riesgo sea alto.';

create index incidentes_brecha_detectado_idx
    on privacy.incidentes_brecha (detectado_at desc);
