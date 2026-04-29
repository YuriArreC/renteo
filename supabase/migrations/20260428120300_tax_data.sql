-- =============================================================================
-- Migration: 20260428120300_tax_data
-- Skills:    tax-data-model (skill 6), sii-integration (skill 4)
-- Purpose:   Datos tributarios sincronizados desde SII (DTEs, RCV, F29, F22,
--            BHE). Multi-tenant con workspace_id + empresa_id; RLS llega en
--            B12. raw_payload guarda la respuesta cruda del proveedor para
--            trazabilidad y para soportar cambios de schema sin perder data.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- tax_data.dtes — Documentos Tributarios Electrónicos
-- -----------------------------------------------------------------------------
create table if not exists tax_data.dtes (
    id                          uuid primary key default gen_random_uuid(),
    workspace_id                uuid not null
                                references core.workspaces(id) on delete cascade,
    empresa_id                  uuid not null
                                references core.empresas(id) on delete cascade,
    tipo                        int not null,
    folio                       bigint not null,
    direccion                   text not null
                                check (direccion in ('emitido', 'recibido')),
    rut_contraparte             text,
    razon_social_contraparte    text,
    fecha_emision               date not null,
    neto                        numeric(18, 2) not null default 0,
    iva                         numeric(18, 2) not null default 0,
    total                       numeric(18, 2) not null,
    estado_sii                  text,
    raw_payload                 jsonb,
    sync_provider               text
                                check (sync_provider in (
                                    'simpleapi', 'baseapi', 'apigateway'
                                )),
    synced_at                   timestamptz not null default now(),
    created_at                  timestamptz not null default now(),
    unique (empresa_id, direccion, tipo, folio)
);

comment on table tax_data.dtes is
    'DTEs sincronizados desde SII vía proveedor autorizado (SimpleAPI/BaseAPI/ApiGateway). raw_payload preserva la respuesta original sin PII innecesario.';

create index dtes_empresa_fecha_idx
    on tax_data.dtes (empresa_id, fecha_emision desc);
create index dtes_empresa_dir_fecha_idx
    on tax_data.dtes (empresa_id, direccion, fecha_emision desc);

-- -----------------------------------------------------------------------------
-- tax_data.rcv_lines — Registro de Compras y Ventas
-- -----------------------------------------------------------------------------
create table if not exists tax_data.rcv_lines (
    id              uuid primary key default gen_random_uuid(),
    workspace_id    uuid not null
                    references core.workspaces(id) on delete cascade,
    empresa_id      uuid not null
                    references core.empresas(id) on delete cascade,
    period          text not null
                    check (period ~ '^[0-9]{4}-(0[1-9]|1[0-2])$'),
    tipo            text not null check (tipo in ('compra', 'venta')),
    dte_id          uuid references tax_data.dtes(id) on delete set null,
    neto            numeric(18, 2) not null default 0,
    iva             numeric(18, 2) not null default 0,
    total           numeric(18, 2) not null default 0,
    categoria       text,
    synced_at       timestamptz not null default now(),
    created_at      timestamptz not null default now()
);

comment on table tax_data.rcv_lines is
    'Líneas del Registro de Compras y Ventas (RCV). period en formato YYYY-MM.';

create index rcv_lines_empresa_period_tipo_idx
    on tax_data.rcv_lines (empresa_id, period, tipo);

-- -----------------------------------------------------------------------------
-- tax_data.f29_periodos — Declaración mensual F29
-- -----------------------------------------------------------------------------
create table if not exists tax_data.f29_periodos (
    id                  uuid primary key default gen_random_uuid(),
    workspace_id        uuid not null
                        references core.workspaces(id) on delete cascade,
    empresa_id          uuid not null
                        references core.empresas(id) on delete cascade,
    period              text not null
                        check (period ~ '^[0-9]{4}-(0[1-9]|1[0-2])$'),
    iva_debito          numeric(18, 2),
    iva_credito         numeric(18, 2),
    ppm                 numeric(18, 2),
    retenciones         numeric(18, 2),
    postergacion_iva    boolean not null default false,
    presentado_at       timestamptz,
    raw_payload         jsonb,
    synced_at           timestamptz not null default now(),
    created_at          timestamptz not null default now(),
    unique (empresa_id, period)
);

comment on table tax_data.f29_periodos is
    'F29 mensual por empresa. presentado_at NULL si aún no ha sido declarado en SII.';

-- -----------------------------------------------------------------------------
-- tax_data.f22_anios — Declaración anual F22
-- -----------------------------------------------------------------------------
create table if not exists tax_data.f22_anios (
    id                      uuid primary key default gen_random_uuid(),
    workspace_id            uuid not null
                            references core.workspaces(id) on delete cascade,
    empresa_id              uuid not null
                            references core.empresas(id) on delete cascade,
    tax_year                int not null,
    regimen_declarado       text
                            check (regimen_declarado in (
                                '14_a', '14_d_3', '14_d_8', 'presunta'
                            )),
    rli_declarada           numeric(18, 2),
    idpc_pagado             numeric(18, 2),
    creditos_imputados      jsonb,
    presentado_at           timestamptz,
    raw_payload             jsonb,
    synced_at               timestamptz not null default now(),
    created_at              timestamptz not null default now(),
    unique (empresa_id, tax_year)
);

comment on table tax_data.f22_anios is
    'Declaración anual F22 por empresa y tax_year. Una fila por año tributario.';

-- -----------------------------------------------------------------------------
-- tax_data.boletas_honorarios — BHE
-- -----------------------------------------------------------------------------
create table if not exists tax_data.boletas_honorarios (
    id              uuid primary key default gen_random_uuid(),
    workspace_id    uuid not null
                    references core.workspaces(id) on delete cascade,
    empresa_id      uuid not null
                    references core.empresas(id) on delete cascade,
    numero          bigint not null,
    fecha_emision   date not null,
    monto_bruto     numeric(18, 2) not null,
    retencion       numeric(18, 2) not null,
    monto_liquido   numeric(18, 2) not null,
    rut_emisor      text not null,
    raw_payload     jsonb,
    synced_at       timestamptz not null default now(),
    created_at      timestamptz not null default now(),
    unique (empresa_id, numero)
);

comment on table tax_data.boletas_honorarios is
    'Boletas de Honorarios Electrónicas recibidas por la empresa.';

create index boletas_honorarios_empresa_fecha_idx
    on tax_data.boletas_honorarios (empresa_id, fecha_emision desc);
