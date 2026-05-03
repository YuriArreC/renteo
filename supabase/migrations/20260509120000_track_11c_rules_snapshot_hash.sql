-- =============================================================================
-- Migration: 20260509120000_track_11c_rules_snapshot_hash
-- Skills:    tax-rules-versioning (skill 11)
-- Purpose:   Sumar rules_snapshot_hash a core.recomendaciones y a
--            tax_calc.rli_calculations (la columna ya existe en
--            core.escenarios_simulacion desde track 9). Track 11c llena
--            el hash con SHA-256 hex de la serialización canónica del
--            rule_set + tax_year_params usados en cada cálculo —
--            permite verificar reproducibilidad bit-a-bit.
-- =============================================================================

alter table core.recomendaciones
    add column if not exists rules_snapshot_hash text;

comment on column core.recomendaciones.rules_snapshot_hash is
    'SHA-256 hex de la serialización canónica del rule_set + tax_year_params usados (skill 11). Permite verificar reproducibilidad sin comparar JSON gigantes.';

alter table tax_calc.rli_calculations
    add column if not exists rules_snapshot_hash text;

comment on column tax_calc.rli_calculations.rules_snapshot_hash is
    'SHA-256 hex de la serialización canónica del rule_set + tax_year_params usados (skill 11).';
