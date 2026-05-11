-- =============================================================================
-- BORRADOR firma contador socio — 02_idpc_rates
-- Checklist §1 (REVISION_CONTADOR_SOCIO.md).
-- Cierra TODOS-CONTADOR.md #1.
--
-- ✍️ CONTADOR_SOCIO: confirmar tasa por (tax_year, regimen). Atención
--    a la condicionalidad del art. 4° transitorio Ley 21.735 — si se
--    rompe (ej. empleador no cotiza), el motor debe usar la fila
--    `14_d_3_revertida` con tasa 25%.
--
-- Cuando esté firmado, mover a:
--   supabase/migrations/YYYYMMDDHHMMSS_idpc_rates_firmado.sql
-- =============================================================================

begin;

-- 1) Limpiar placeholders.
delete from tax_params.idpc_rates
where fuente_legal like 'PLACEHOLDER%';

-- 2) Insertar tasas firmadas.
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
     'Tasa transitoria 12,5% condicionada al art. 4° transitorio Ley 21.735 (cumplimiento cotizaciones)',
     'Ley 21.755; Circular SII 53/2025'),                -- ✍️
    (2026, '14_d_3', 0.1250, true,
     'Tasa transitoria 12,5% condicionada al art. 4° transitorio Ley 21.735',
     'Ley 21.755; Circular SII 53/2025'),                -- ✍️

-- 14 D N°3 revertida — fallback si se rompe condicionalidad Ley 21.735.
-- Item #17 de TODOS-CONTADOR.md: política de aplicación.
    (2025, '14_d_3_revertida', 0.2500, false,
     'Aplica si empresa no cumple condicionalidad Ley 21.735 (ej. no cotizó por empleadores)',
     'art. 14 D N°3 LIR; Ley 21.735 art. 4° t'),         -- ✍️
    (2026, '14_d_3_revertida', 0.2500, false,
     'Aplica si empresa no cumple condicionalidad Ley 21.735',
     'art. 14 D N°3 LIR; Ley 21.735 art. 4° t'),         -- ✍️

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
     'art. 14 D N°8 LIR');                               -- ✍️

-- AT 2027-2028: ✍️ AGREGAR cuando el contador valide que las tasas
--               siguen vigentes y que la rampa BHE / condicionalidad
--               no introducen cambios. Por defecto NO se incluyen para
--               no comprometer cifras futuras sin DOF.

commit;
