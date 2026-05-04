-- =============================================================================
-- Migration: 20260513120000_tighten_snapshot_hash
-- Skills:    tax-rules-versioning (skill 11)
-- Purpose:   Cerrar la promesa de skill 11 ("cada cálculo persiste snapshot
--            inmutable") tightening rules_snapshot_hash a NOT NULL en las
--            tablas de cálculo. Track 9 lo dejó nullable para compat;
--            track 11c llenó los nuevos inserts. Ahora lo hacemos requisito
--            de schema y la inmutabilidad del hash la añadimos al trigger
--            ya existente (app.prevent_snapshot_modification).
-- =============================================================================

-- core.escenarios_simulacion: filas legadas (pre-track 11c) reciben un
-- sentinel explícito para no confundirse con cálculos firmados. Cualquier
-- INSERT nuevo provee el hash real (build_snapshots).
update core.escenarios_simulacion
   set rules_snapshot_hash = 'legacy-pre-track-11c'
 where rules_snapshot_hash is null;

alter table core.escenarios_simulacion
    alter column rules_snapshot_hash set not null;

-- core.recomendaciones: idéntico tightening.
update core.recomendaciones
   set rules_snapshot_hash = 'legacy-pre-track-11c'
 where rules_snapshot_hash is null;

alter table core.recomendaciones
    alter column rules_snapshot_hash set not null;

-- tax_calc.rli_calculations.
update tax_calc.rli_calculations
   set rules_snapshot_hash = 'legacy-pre-track-11c'
 where rules_snapshot_hash is null;

alter table tax_calc.rli_calculations
    alter column rules_snapshot_hash set not null;

-- Extender el trigger existente para que también bloquee UPDATEs que
-- modifiquen `rules_snapshot_hash`. Track 11c agregó la columna pero
-- no la cubrió en el guard. Un UPDATE incoherente (mismo payload,
-- hash distinto) podría pasar — lo cerramos.
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
    if old.rules_snapshot_hash is distinct from new.rules_snapshot_hash then
        raise exception
            'rules_snapshot_hash es inmutable en %.% (skill 11).',
            tg_table_schema, tg_table_name
            using errcode = 'check_violation';
    end if;
    return new;
end;
$$;

comment on function app.prevent_snapshot_modification() is
    'Trigger reutilizable que rechaza UPDATE sobre engine_version, rule_set_snapshot, tax_year_params_snapshot y rules_snapshot_hash. Permite cambiar otros campos.';
