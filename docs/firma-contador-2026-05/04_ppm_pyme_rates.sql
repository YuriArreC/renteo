-- =============================================================================
-- BORRADOR firma contador socio — 04_ppm_pyme_rates
-- Checklist §4 (REVISION_CONTADOR_SOCIO.md).
-- Cierra TODOS-CONTADOR.md #4 (factor SAC) parcial — la imputación
-- del SAC se firma como regla en 06_whitelist_palancas_v2.sql.
--
-- ✍️ CONTADOR_SOCIO: confirmar tasas PPM por régimen y AT. El umbral
--    50.000 UF separa tasa baja (0,125%) de tasa alta (0,25%) para
--    14 D N°3 en régimen transitorio Ley 21.755.
--
-- Cuando esté firmado, mover a:
--   supabase/migrations/YYYYMMDDHHMMSS_ppm_pyme_rates_firmado.sql
-- =============================================================================

begin;

-- 1) Limpiar placeholders.
delete from tax_params.ppm_pyme_rates
where fuente_legal like 'PLACEHOLDER%';

-- 2) Insertar tasas firmadas.
insert into tax_params.ppm_pyme_rates (
    tax_year, regimen, umbral_uf, tasa_bajo, tasa_alto,
    es_transitoria, fuente_legal
) values

-- ───────────────────────────────────────────────────────────────────────
-- 14 D N°3 — Pro PyME General, PPM transitorio 0,125% / 0,25%
-- (Ley 21.755 + Circular SII 53/2025)
-- ───────────────────────────────────────────────────────────────────────
    (2025, '14_d_3', 50000.00, 0.00125, 0.00250, true,
     'Ley 21.755; Circular SII 53/2025 — PPM transitorio'),  -- ✍️
    (2026, '14_d_3', 50000.00, 0.00125, 0.00250, true,
     'Ley 21.755; Circular SII 53/2025'),                    -- ✍️

-- AT 2024: ✍️ confirmar — ¿ya estaba el PPM transitorio o tasa
-- permanente 0,25%?
    (2024, '14_d_3', 50000.00, 0.00250, 0.00250, false,
     'art. 84 LIR — PPM permanente'),                        -- ✍️ verificar

-- ───────────────────────────────────────────────────────────────────────
-- 14 D N°8 — Pro PyME Transparente: PPM lo paga el dueño, no la empresa.
-- Las filas siguientes existen por compatibilidad de schema; el motor
-- detecta tasa 0 y omite el cálculo a nivel empresa.
-- ───────────────────────────────────────────────────────────────────────
    (2024, '14_d_8', 50000.00, 0.00000, 0.00000, false,
     'art. 14 D N°8 LIR — régimen transparente, PPM nivel dueños'),  -- ✍️
    (2025, '14_d_8', 50000.00, 0.00000, 0.00000, false,
     'art. 14 D N°8 LIR'),                                            -- ✍️
    (2026, '14_d_8', 50000.00, 0.00000, 0.00000, false,
     'art. 14 D N°8 LIR');                                            -- ✍️

-- 14 A: ✍️ confirmar si requiere fila aquí o si el PPM 14 A se calcula
--      con tasa variable propia (no PyME) en otra tabla.

commit;
