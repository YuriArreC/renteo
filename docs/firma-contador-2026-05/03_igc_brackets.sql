-- =============================================================================
-- BORRADOR firma contador socio — 03_igc_brackets
-- Checklist §2 (REVISION_CONTADOR_SOCIO.md).
-- Cierra TODOS-CONTADOR.md #2.
--
-- ✍️ CONTADOR_SOCIO: confirmar 8 tramos en UTA de la tabla IGC.
--    Verificar si los tramos cambian entre AT 2024, 2025 y 2026 —
--    placeholder asume idéntica para los 3 AT.
--
-- Crédito 5% último tramo (art. 56 LIR) va aparte en
-- 05_beneficios_topes.sql (key='credito_5pct_ultimo_tramo_igc'); NO
-- se aplica adentro de compute_igc.
--
-- Cuando esté firmado, mover a:
--   supabase/migrations/YYYYMMDDHHMMSS_igc_brackets_firmado.sql
-- =============================================================================

begin;

-- 1) Limpiar tramos placeholder.
--    NOTA: la seed original no marca fuente_legal por tramo (la tabla
--    no tiene esa columna). Usamos un DELETE limpio sobre los AT
--    que vamos a refirmar.
delete from tax_params.igc_brackets
where tax_year in (2024, 2025, 2026);

-- 2) Insertar tramos firmados.
--    Formato: (tax_year, tramo, desde_uta, hasta_uta, tasa, rebajar_uta)
insert into tax_params.igc_brackets (
    tax_year, tramo, desde_uta, hasta_uta, tasa, rebajar_uta
) values

-- ───────────────────────────────────────────────────────────────────────
-- AT 2024 — ✍️ confirmar (¿idéntico a AT 2026 o hay rampa post Ley 21.210?)
-- ───────────────────────────────────────────────────────────────────────
    (2024, 1,    0.0000,   13.5000, 0.0000,   0.0000),
    (2024, 2,   13.5000,   30.0000, 0.0400,   0.5400),
    (2024, 3,   30.0000,   50.0000, 0.0800,   1.7400),
    (2024, 4,   50.0000,   70.0000, 0.1350,   4.4900),
    (2024, 5,   70.0000,   90.0000, 0.2300,  11.1400),
    (2024, 6,   90.0000,  120.0000, 0.3040,  17.8000),
    (2024, 7,  120.0000,  310.0000, 0.3500,  23.3200),
    (2024, 8,  310.0000,  null,     0.4000,  38.8200),

-- ───────────────────────────────────────────────────────────────────────
-- AT 2025 — ✍️ confirmar
-- ───────────────────────────────────────────────────────────────────────
    (2025, 1,    0.0000,   13.5000, 0.0000,   0.0000),
    (2025, 2,   13.5000,   30.0000, 0.0400,   0.5400),
    (2025, 3,   30.0000,   50.0000, 0.0800,   1.7400),
    (2025, 4,   50.0000,   70.0000, 0.1350,   4.4900),
    (2025, 5,   70.0000,   90.0000, 0.2300,  11.1400),
    (2025, 6,   90.0000,  120.0000, 0.3040,  17.8000),
    (2025, 7,  120.0000,  310.0000, 0.3500,  23.3200),
    (2025, 8,  310.0000,  null,     0.4000,  38.8200),

-- ───────────────────────────────────────────────────────────────────────
-- AT 2026 — ✍️ confirmar (referencia: art. 52 LIR + circular vigente)
-- ───────────────────────────────────────────────────────────────────────
    (2026, 1,    0.0000,   13.5000, 0.0000,   0.0000),
    (2026, 2,   13.5000,   30.0000, 0.0400,   0.5400),
    (2026, 3,   30.0000,   50.0000, 0.0800,   1.7400),
    (2026, 4,   50.0000,   70.0000, 0.1350,   4.4900),
    (2026, 5,   70.0000,   90.0000, 0.2300,  11.1400),
    (2026, 6,   90.0000,  120.0000, 0.3040,  17.8000),
    (2026, 7,  120.0000,  310.0000, 0.3500,  23.3200),
    (2026, 8,  310.0000,  null,     0.4000,  38.8200);

-- AT 2027-2028: ✍️ NO incluir hasta confirmar que SII / DOF mantienen
--                  la misma tabla. Una nueva versión se publica al
--                  cierre de cada AT.

commit;
