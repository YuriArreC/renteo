-- =============================================================================
-- BORRADOR firma contador socio — 05_beneficios_topes
-- Checklist §6 (REVISION_CONTADOR_SOCIO.md).
-- Cierra parcialmente TODOS-CONTADOR.md #14 (sueldo empresarial razonable
-- queda en `null` si no hay firma todavía).
--
-- ✍️ CONTADOR_SOCIO: confirmar topes por (key, tax_year). Los más
--    sensibles son:
--      - sueldo_empresarial_tope_mensual_uf → TODO-CONTADOR #14
--        (dejar `null` o no insertar si no hay firma).
--      - credito_id_porcentaje_credito / gasto → Ley 20.241 art. 18
--      - apv_tope_anual_uf → DL 3.500 art. 42 bis
--      - depreciacion_acelerada_factor → art. 31 N°5 LIR (factor 3)
--
-- Cuando esté firmado, mover a:
--   supabase/migrations/YYYYMMDDHHMMSS_beneficios_topes_firmado.sql
-- =============================================================================

begin;

-- 1) Limpiar topes placeholder.
delete from tax_params.beneficios_topes
where fuente_legal like 'PLACEHOLDER%';

-- 2) Insertar topes firmados.
insert into tax_params.beneficios_topes (
    key, tax_year, valor, unidad, fuente_legal, descripcion
) values

-- ───────────────────────────────────────────────────────────────────────
-- P3 — Rebaja 14 E (reinversión Pro PyME General)
-- ───────────────────────────────────────────────────────────────────────
    ('rebaja_14e_porcentaje', 2024, 0.5000, 'porcentaje',
     'art. 14 E LIR', '50% RLI máximo rebajable'),                  -- ✍️
    ('rebaja_14e_porcentaje', 2025, 0.5000, 'porcentaje',
     'art. 14 E LIR', '50% RLI'),                                    -- ✍️
    ('rebaja_14e_porcentaje', 2026, 0.5000, 'porcentaje',
     'art. 14 E LIR', '50% RLI'),                                    -- ✍️

    ('rebaja_14e_uf', 2024, 5000.0000, 'uf',
     'art. 14 E LIR', 'Tope absoluto reinversión'),                  -- ✍️
    ('rebaja_14e_uf', 2025, 5000.0000, 'uf',
     'art. 14 E LIR', 'Tope absoluto'),                              -- ✍️
    ('rebaja_14e_uf', 2026, 5000.0000, 'uf',
     'art. 14 E LIR', 'Tope absoluto'),                              -- ✍️

-- ───────────────────────────────────────────────────────────────────────
-- P5 — Sueldo empresarial al socio activo
-- ✍️ TODO-CONTADOR #14: dejar SIN insertar hasta tener tope por
--    industria + función. Si no se inserta, el motor rechaza la palanca
--    con MissingTaxYearParams en _validate_eligibility.
-- ───────────────────────────────────────────────────────────────────────
--    ('sueldo_empresarial_tope_mensual_uf', 2026, <UF>, 'uf',
--     '<fuente>', 'Sueldo empresarial razonable mensual'),

-- ───────────────────────────────────────────────────────────────────────
-- P6 — Crédito I+D (Ley 20.241)
-- ───────────────────────────────────────────────────────────────────────
    ('credito_id_porcentaje_credito', 2024, 0.3500, 'porcentaje',
     'Ley 20.241 art. 4°', '35% del gasto I+D como crédito IDPC'),  -- ✍️
    ('credito_id_porcentaje_credito', 2025, 0.3500, 'porcentaje',
     'Ley 20.241 art. 4°', '35% gasto I+D'),                        -- ✍️
    ('credito_id_porcentaje_credito', 2026, 0.3500, 'porcentaje',
     'Ley 20.241 art. 4°', '35% gasto I+D'),                        -- ✍️

    ('credito_id_porcentaje_gasto', 2024, 0.6500, 'porcentaje',
     'Ley 20.241 art. 4°', '65% restante como gasto necesario'),    -- ✍️
    ('credito_id_porcentaje_gasto', 2025, 0.6500, 'porcentaje',
     'Ley 20.241', '65% gasto'),                                    -- ✍️
    ('credito_id_porcentaje_gasto', 2026, 0.6500, 'porcentaje',
     'Ley 20.241', '65% gasto'),                                    -- ✍️

    ('credito_id_tope_utm', 2024, 15000.0000, 'utm',
     'Ley 20.241', 'Tope anual crédito I+D'),                       -- ✍️
    ('credito_id_tope_utm', 2025, 15000.0000, 'utm',
     'Ley 20.241', 'Tope anual'),                                   -- ✍️
    ('credito_id_tope_utm', 2026, 15000.0000, 'utm',
     'Ley 20.241; extensión Ley 21.755', 'Tope anual'),             -- ✍️

-- ───────────────────────────────────────────────────────────────────────
-- P2 — SENCE (Ley 19.518)
-- ───────────────────────────────────────────────────────────────────────
    ('sence_porcentaje_planilla', 2024, 0.0100, 'porcentaje',
     'Ley 19.518 art. 36', '1% planilla anual SENCE'),              -- ✍️
    ('sence_porcentaje_planilla', 2025, 0.0100, 'porcentaje',
     'Ley 19.518', '1% planilla'),                                  -- ✍️
    ('sence_porcentaje_planilla', 2026, 0.0100, 'porcentaje',
     'Ley 19.518', '1% planilla'),                                  -- ✍️

    ('sence_tope_minimo_utm', 2024, 9.0000, 'utm',
     'Ley 19.518', 'Mínimo 9 UTM si planilla < 35 UTM'),            -- ✍️
    ('sence_tope_minimo_utm', 2025, 9.0000, 'utm',
     'Ley 19.518', 'Mínimo SENCE'),                                 -- ✍️
    ('sence_tope_minimo_utm', 2026, 9.0000, 'utm',
     'Ley 19.518', 'Mínimo SENCE'),                                 -- ✍️

-- ───────────────────────────────────────────────────────────────────────
-- P9 — APV (DL 3.500 + art. 42 bis LIR)
-- ───────────────────────────────────────────────────────────────────────
    ('apv_tope_anual_uf', 2024, 600.0000, 'uf',
     'art. 42 bis LIR', 'Tope rebaja APV régimen A'),                -- ✍️
    ('apv_tope_anual_uf', 2025, 600.0000, 'uf',
     'art. 42 bis LIR', 'Tope APV'),                                 -- ✍️
    ('apv_tope_anual_uf', 2026, 600.0000, 'uf',
     'art. 42 bis LIR', 'Tope APV'),                                 -- ✍️

-- ───────────────────────────────────────────────────────────────────────
-- P7 — PPM extraordinario (art. 84 LIR)
-- ───────────────────────────────────────────────────────────────────────
    ('ppm_extraordinario_max_factor', 2024, 2.0000, 'factor',
     'art. 84 LIR', 'Factor máx 2× tasa habitual sin red flag'),     -- ✍️
    ('ppm_extraordinario_max_factor', 2025, 2.0000, 'factor',
     'art. 84 LIR', 'Factor máx 2×'),                                -- ✍️
    ('ppm_extraordinario_max_factor', 2026, 2.0000, 'factor',
     'art. 84 LIR', 'Factor máx 2×'),                                -- ✍️

-- ───────────────────────────────────────────────────────────────────────
-- P8 — Postergación IVA (art. 64 N°9 CT)
-- ───────────────────────────────────────────────────────────────────────
    ('iva_postergacion_dias', 2024, 60.0000, 'dias',
     'art. 64 N°9 CT; Ley 21.210', 'Postergación 60 días para Pro PyME'),  -- ✍️
    ('iva_postergacion_dias', 2025, 60.0000, 'dias',
     'art. 64 N°9 CT', 'Postergación 60 días'),                            -- ✍️
    ('iva_postergacion_dias', 2026, 60.0000, 'dias',
     'art. 64 N°9 CT', 'Postergación 60 días'),                            -- ✍️

-- ───────────────────────────────────────────────────────────────────────
-- P10 — Crédito reinversión activo fijo (art. 33 bis LIR)
-- ───────────────────────────────────────────────────────────────────────
    ('credito_reinversion_porcentaje', 2024, 0.0600, 'porcentaje',
     'art. 33 bis LIR', '6% inversión activo fijo'),                 -- ✍️
    ('credito_reinversion_porcentaje', 2025, 0.0600, 'porcentaje',
     'art. 33 bis LIR', '6% activo fijo'),                           -- ✍️
    ('credito_reinversion_porcentaje', 2026, 0.0600, 'porcentaje',
     'art. 33 bis LIR', '6% activo fijo'),                           -- ✍️

    ('credito_reinversion_tope_utm', 2024, 500.0000, 'utm',
     'art. 33 bis LIR', 'Tope 500 UTM anual'),                       -- ✍️
    ('credito_reinversion_tope_utm', 2025, 500.0000, 'utm',
     'art. 33 bis LIR', 'Tope anual'),                               -- ✍️
    ('credito_reinversion_tope_utm', 2026, 500.0000, 'utm',
     'art. 33 bis LIR', 'Tope anual'),                               -- ✍️

-- ───────────────────────────────────────────────────────────────────────
-- P11 — Depreciación acelerada (art. 31 N°5 LIR)
-- ───────────────────────────────────────────────────────────────────────
    ('depreciacion_acelerada_factor', 2024, 3.0000, 'factor',
     'art. 31 N°5 LIR', 'Factor 3 sobre vida útil normal'),          -- ✍️
    ('depreciacion_acelerada_factor', 2025, 3.0000, 'factor',
     'art. 31 N°5 LIR', 'Factor 3'),                                 -- ✍️
    ('depreciacion_acelerada_factor', 2026, 3.0000, 'factor',
     'art. 31 N°5 LIR', 'Factor 3'),                                 -- ✍️

-- ───────────────────────────────────────────────────────────────────────
-- Crédito 5% último tramo IGC (art. 56 LIR) — se aplica fuera de
-- compute_igc, como deducción contra IGC del dueño.
-- ───────────────────────────────────────────────────────────────────────
    ('credito_5pct_ultimo_tramo_igc', 2024, 0.0500, 'porcentaje',
     'art. 56 LIR', 'Crédito 5% sobre fracción afecta al 40%'),      -- ✍️
    ('credito_5pct_ultimo_tramo_igc', 2025, 0.0500, 'porcentaje',
     'art. 56 LIR', 'Crédito 5% último tramo'),                      -- ✍️
    ('credito_5pct_ultimo_tramo_igc', 2026, 0.0500, 'porcentaje',
     'art. 56 LIR', 'Crédito 5% último tramo');                      -- ✍️

commit;
