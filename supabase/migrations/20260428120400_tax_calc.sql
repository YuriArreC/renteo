-- =============================================================================
-- Migration: 20260428120400_tax_calc
-- Skills:    chilean-tax-engine (skill 3), tax-data-model (skill 6)
-- Purpose:   Cálculos del motor: RLI, registros tributarios (SAC/RAI/REX/DDAN)
--            y retiros / distribuciones del dueño. Las columnas snapshot
--            (rule_set_snapshot, tax_year_params_snapshot) y el trigger
--            anti-UPDATE viven en B11.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- tax_calc.rli_calculations — Renta Líquida Imponible por (empresa, año)
-- -----------------------------------------------------------------------------
create table if not exists tax_calc.rli_calculations (
    id                      uuid primary key default gen_random_uuid(),
    workspace_id            uuid not null
                            references core.workspaces(id) on delete cascade,
    empresa_id              uuid not null
                            references core.empresas(id) on delete cascade,
    tax_year                int not null,
    ingresos_brutos         numeric(18, 2) not null default 0,
    costos                  numeric(18, 2) not null default 0,
    gastos_aceptados        numeric(18, 2) not null default 0,
    agregados_art_33        numeric(18, 2) not null default 0,
    perdidas_anteriores     numeric(18, 2) not null default 0,
    rli_final               numeric(18, 2) not null,
    engine_version          text not null,
    inputs_snapshot         jsonb not null,
    computed_at             timestamptz not null default now(),
    created_at              timestamptz not null default now()
);

comment on table tax_calc.rli_calculations is
    'Cálculo de RLI por (empresa_id, tax_year). Recalcular = nuevo registro; nunca se sobrescribe (snapshot inmutable, ver B11). engine_version + inputs_snapshot permiten reproducibilidad.';

create index rli_calculations_empresa_year_idx
    on tax_calc.rli_calculations (empresa_id, tax_year, computed_at desc);

-- -----------------------------------------------------------------------------
-- tax_calc.registros_tributarios — SAC, RAI, REX, DDAN para 14 A y 14 D N°3
-- -----------------------------------------------------------------------------
create table if not exists tax_calc.registros_tributarios (
    id                  uuid primary key default gen_random_uuid(),
    workspace_id        uuid not null
                        references core.workspaces(id) on delete cascade,
    empresa_id          uuid not null
                        references core.empresas(id) on delete cascade,
    tax_year            int not null,
    sac_inicial         numeric(18, 2) not null default 0,
    sac_movimientos     jsonb not null default '[]'::jsonb,
    sac_final           numeric(18, 2) not null default 0,
    rai_inicial         numeric(18, 2) not null default 0,
    rai_final           numeric(18, 2) not null default 0,
    rex_inicial         numeric(18, 2) not null default 0,
    rex_final           numeric(18, 2) not null default 0,
    ddan_final          numeric(18, 2) not null default 0,
    created_at          timestamptz not null default now(),
    updated_at          timestamptz not null default now(),
    unique (empresa_id, tax_year)
);

comment on table tax_calc.registros_tributarios is
    'Saldos y movimientos de los registros SAC/RAI/REX/DDAN para regímenes 14 A y 14 D N°3. Composición exacta post Ley 21.713 a confirmar por contador socio (ver TODOS-CONTADOR.md).';

create trigger registros_tributarios_touch_updated_at
    before update on tax_calc.registros_tributarios
    for each row execute function app.touch_updated_at();

-- -----------------------------------------------------------------------------
-- tax_calc.retiros_y_distribuciones
-- -----------------------------------------------------------------------------
create table if not exists tax_calc.retiros_y_distribuciones (
    id              uuid primary key default gen_random_uuid(),
    workspace_id    uuid not null
                    references core.workspaces(id) on delete cascade,
    empresa_id      uuid not null
                    references core.empresas(id) on delete cascade,
    socio_id        uuid not null,
    fecha           date not null,
    monto           numeric(18, 2) not null,
    imputacion      text not null
                    check (imputacion in (
                        'rex', 'rai_con_credito', 'rai_sin_credito'
                    )),
    credito_idpc    numeric(18, 2),
    created_at      timestamptz not null default now()
);

comment on table tax_calc.retiros_y_distribuciones is
    'Retiros y distribuciones por socio/dueño. Orden de imputación REX → RAI con crédito → RAI sin crédito (Circular SII 73/2020 y posteriores). socio_id es identificador interno; la tabla de socios/dueños llega cuando el modelo lo requiera.';

create index retiros_empresa_fecha_idx
    on tax_calc.retiros_y_distribuciones (empresa_id, fecha desc);
