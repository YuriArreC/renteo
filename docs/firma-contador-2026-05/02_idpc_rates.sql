-- =============================================================================
-- BORRADOR firma contador socio — 02_idpc_rates
-- Checklist §1 (REVISION_CONTADOR_SOCIO.md).
-- Cierra TODOS-CONTADOR.md #1.
--
-- Firma EN SITIO (UPSERT) de tax_params.idpc_rates.
--
-- ⚠️ Por qué UPSERT y NO delete+insert:
--    Un `delete ... where fuente_legal like 'PLACEHOLDER%'` borraría también
--    las filas AT 2027/2028, que el recomendador necesita para la proyección
--    a 3 años. El UPSERT actualiza las tasas firmadas (AT 2024-2026) sin
--    borrar filas y sin dejar años huérfanos.
--
-- ⚠️ Régimen 14 D N°3 "revertido" (fallback 25% si se rompe la
--    condicionalidad del art. 4° transitorio Ley 21.735): NO es una fila de
--    idpc_rates. El CHECK de la tabla solo admite regimen in
--    ('14_a','14_d_3','14_d_8'); un INSERT de '14_d_3_revertida' aborta la
--    migración. La tasa revertida se modela como FEATURE FLAG
--    `idpc_14d3_revertida_rate` (tax_rules.feature_flags_by_year), que
--    comparador.py / regime.py leen vía _get_revertida_rate. Se firma allí,
--    no acá.
--
-- ✍️ CONTADOR_SOCIO: confirmar tasa por (tax_year, regimen). Atención a la
--    condicionalidad del art. 4° transitorio Ley 21.735.
--
-- Cuando esté firmado, mover a:
--   supabase/migrations/YYYYMMDDHHMMSS_idpc_rates_firmado.sql
-- =============================================================================

begin;

-- UPSERT de las tasas firmadas (AT 2024-2026).
insert into tax_params.idpc_rates (
    tax_year, regimen, rate, es_transitoria, condicion_aplicacion, fuente_legal
) values

-- ───────────────────────────────────────────────────────────────────────
-- 14 A — régimen general semi integrado (tasa permanente 27%)
-- ───────────────────────────────────────────────────────────────────────
    (2024, '14_a', 0.2700, false, null,
     'art. 14 A LIR; Ley 21.210 art. 1° N°10'),   -- ✍️ confirmar
    (2025, '14_a', 0.2700, false, null,
     'art. 14 A LIR; Ley 21.210 art. 1° N°10'),   -- ✍️
    (2026, '14_a', 0.2700, false, null,
     'art. 14 A LIR; Ley 21.210 art. 1° N°10'),   -- ✍️

-- ───────────────────────────────────────────────────────────────────────
-- 14 D N°3 — Pro PyME General
-- AT 2024: tasa permanente 25% post-pandemia (rampa 10% AT 2023 ya
-- vencida).
-- AT 2025-2026: tasa transitoria 12,5% Ley 21.755 + Circ SII 53/2025
--               sujeta a condicionalidad Ley 21.735 art. 4° transitorio.
-- ───────────────────────────────────────────────────────────────────────
    (2024, '14_d_3', 0.2500, false, null,
     'art. 14 D N°3 LIR; rampa Ley 21.578 finalizada'),  -- ✍️ confirmar
    (2025, '14_d_3', 0.1250, true,
     'Tasa transitoria 12,5% condicionada al art. 4° transitorio Ley 21.735 (cumplimiento cotizaciones). Fallback 25% vía feature flag idpc_14d3_revertida_rate.',
     'Ley 21.755; Circular SII 53/2025'),                -- ✍️
    (2026, '14_d_3', 0.1250, true,
     'Tasa transitoria 12,5% condicionada al art. 4° transitorio Ley 21.735. Fallback 25% vía feature flag idpc_14d3_revertida_rate.',
     'Ley 21.755; Circular SII 53/2025'),                -- ✍️

-- ───────────────────────────────────────────────────────────────────────
-- 14 D N°8 — Pro PyME Transparente (IDPC 0%, dueños tributan IGC)
-- ───────────────────────────────────────────────────────────────────────
    (2024, '14_d_8', 0.0000, false,
     'Régimen transparente: IDPC corre por dueños vía atribución',
     'art. 14 D N°8 LIR'),                               -- ✍️
    (2025, '14_d_8', 0.0000, false,
     'Régimen transparente',
     'art. 14 D N°8 LIR'),                               -- ✍️
    (2026, '14_d_8', 0.0000, false,
     'Régimen transparente',
     'art. 14 D N°8 LIR')                                -- ✍️

on conflict (tax_year, regimen) do update set
    rate                 = excluded.rate,
    es_transitoria       = excluded.es_transitoria,
    condicion_aplicacion = excluded.condicion_aplicacion,
    fuente_legal         = excluded.fuente_legal;

-- AT 2027-2028: las filas placeholder se CONSERVAN (no se borran) para no
-- romper la proyección a 3 años del recomendador. Quedan como proyección no
-- firmada hasta que el contador valide que las tasas siguen vigentes.
-- ✍️ CONTADOR_SOCIO: refirmar por AT con el mismo UPSERT de arriba.

commit;
