-- =============================================================================
-- Migration: 20260428120900_calc_snapshots
-- Skills:    tax-rules-versioning (skill 11)
-- Purpose:   Agregar columnas snapshot inmutables a las 3 tablas de cálculo
--            (rli_calculations, escenarios_simulacion, recomendaciones) y un
--            trigger BEFORE UPDATE que rechaza modificaciones a esas columnas.
--            Recalcular = nuevo registro, jamás overwrite.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Columnas snapshot. Agregadas como NOT NULL — las tablas están vacías al
-- aplicar esta migración por primera vez (creadas en B6/B7 sin filas).
-- -----------------------------------------------------------------------------
alter table tax_calc.rli_calculations
    add column if not exists rule_set_snapshot jsonb not null,
    add column if not exists tax_year_params_snapshot jsonb not null;

comment on column tax_calc.rli_calculations.rule_set_snapshot is
    'Dump JSON de las reglas declarativas usadas en este cálculo (snapshot inmutable).';
comment on column tax_calc.rli_calculations.tax_year_params_snapshot is
    'Dump JSON de los parámetros tributarios usados (tasas, tramos, topes).';

alter table core.escenarios_simulacion
    add column if not exists rule_set_snapshot jsonb not null,
    add column if not exists tax_year_params_snapshot jsonb not null;

comment on column core.escenarios_simulacion.rule_set_snapshot is
    'Dump JSON de las reglas declarativas usadas en este escenario (snapshot inmutable).';
comment on column core.escenarios_simulacion.tax_year_params_snapshot is
    'Dump JSON de los parámetros tributarios usados.';

alter table core.recomendaciones
    add column if not exists rule_set_snapshot jsonb not null,
    add column if not exists tax_year_params_snapshot jsonb not null;

comment on column core.recomendaciones.rule_set_snapshot is
    'Dump JSON de las reglas declarativas usadas (snapshot inmutable).';
comment on column core.recomendaciones.tax_year_params_snapshot is
    'Dump JSON de los parámetros tributarios usados.';

-- -----------------------------------------------------------------------------
-- Trigger: rechaza UPDATE que modifique columnas snapshot.
-- Otros campos (dismissed_at, acted_on_at, es_recomendado, etc.) sí pueden
-- actualizarse — solo los 3 campos snapshot son inmutables.
-- -----------------------------------------------------------------------------
create or replace function app.prevent_snapshot_modification()
returns trigger
language plpgsql
as $$
begin
    if old.engine_version is distinct from new.engine_version then
        raise exception
            'engine_version es inmutable en %.% (skill 11: snapshot inmutable de cálculos).',
            tg_table_schema, tg_table_name
            using errcode = 'check_violation';
    end if;
    if old.rule_set_snapshot is distinct from new.rule_set_snapshot then
        raise exception
            'rule_set_snapshot es inmutable en %.% (skill 11).',
            tg_table_schema, tg_table_name
            using errcode = 'check_violation';
    end if;
    if old.tax_year_params_snapshot is distinct from new.tax_year_params_snapshot then
        raise exception
            'tax_year_params_snapshot es inmutable en %.% (skill 11).',
            tg_table_schema, tg_table_name
            using errcode = 'check_violation';
    end if;
    return new;
end;
$$;

comment on function app.prevent_snapshot_modification() is
    'Trigger reutilizable que rechaza UPDATE sobre engine_version, rule_set_snapshot y tax_year_params_snapshot. Permite cambiar otros campos.';

create trigger rli_calculations_snapshot_immutable
    before update on tax_calc.rli_calculations
    for each row execute function app.prevent_snapshot_modification();

create trigger escenarios_simulacion_snapshot_immutable
    before update on core.escenarios_simulacion
    for each row execute function app.prevent_snapshot_modification();

create trigger recomendaciones_snapshot_immutable
    before update on core.recomendaciones
    for each row execute function app.prevent_snapshot_modification();
