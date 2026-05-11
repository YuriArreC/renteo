-- =============================================================================
-- BORRADOR firma contador socio — 01_tax_year_params
-- Checklist §3 (REVISION_CONTADOR_SOCIO.md).
-- Cierra TODOS-CONTADOR.md #3.
--
-- Reemplaza la seed placeholder de
-- 20260502120000_tax_params_placeholder_seeds.sql para
-- tax_params.tax_year_params.
--
-- ✍️ CONTADOR_SOCIO: para cada fila confirmar UTM dic, UTA dic, UF dic
--    contra publicación oficial DOF / SII. Reemplazar 'fuente_legal'
--    con cita real (URL DOF + fecha). Borrar filas AT 2027/2028 si DOF
--    aún no publicó.
--
-- Cuando esté firmado, mover a:
--   supabase/migrations/YYYYMMDDHHMMSS_tax_year_params_firmado.sql
-- =============================================================================

begin;

-- 1) Limpiar placeholders existentes (atomicidad: la transacción asegura
--    que las filas firmadas reemplacen sin estado intermedio).
delete from tax_params.tax_year_params
where fuente_legal like 'PLACEHOLDER%';

-- 2) Insertar valores firmados.
--    Formato: (tax_year, iva_rate, retencion_honorarios, uta_dic, utm_dic,
--              uf_dic, fuente_legal, vigencia_inicio, vigencia_fin, obs)
insert into tax_params.tax_year_params (
    tax_year, iva_rate, retencion_honorarios,
    uta_pesos_dic, utm_pesos_dic, uf_pesos_dic,
    fuente_legal, vigencia_inicio, vigencia_fin, observaciones
) values

-- AT 2024
    (2024,
     0.1900,    -- ✍️ IVA estable 19% (confirmar)
     0.1300,    -- ✍️ retención BHE 13% (Ley 21.578 rampa 2024)
     790992,    -- ✍️ UTA dic 2023 — confirmar con DOF
     65916,     -- ✍️ UTM dic 2023 — confirmar con DOF
     37553.7800, -- ✍️ UF dic 2023 — confirmar con SII
     'Ley 21.578 art. 1° / DOF dic 2023', -- ✍️ reemplazar con cita real
     '2024-01-01', '2024-12-31',
     'Firmado por <nombre contador> <YYYY-MM-DD>'),

-- AT 2025
    (2025,
     0.1900,    -- ✍️
     0.1450,    -- ✍️ retención BHE 14,5% rampa 2025
     812096,    -- ✍️ UTA dic 2024
     67675,     -- ✍️ UTM dic 2024
     38414.0000, -- ✍️ UF dic 2024
     'Ley 21.578 art. 1° / DOF dic 2024',
     '2025-01-01', '2025-12-31',
     'Firmado por <nombre contador> <YYYY-MM-DD>'),

-- AT 2026
    (2026,
     0.1900,
     0.1525,    -- ✍️ retención BHE 15,25% rampa 2026
     834504,    -- ✍️ UTA dic 2025
     69542,     -- ✍️ UTM dic 2025
     39280.0000, -- ✍️ UF dic 2025
     'Ley 21.578 art. 1° / DOF dic 2025',
     '2026-01-01', '2026-12-31',
     'Firmado por <nombre contador> <YYYY-MM-DD>');

-- AT 2027-2028: ✍️ BORRAR ESTE BLOQUE si DOF aún no publicó.
-- Mantener solo si tenés UTM/UTA/UF dic oficiales.
--
--    (2027,
--     0.1900,
--     0.1600,
--     <UTA_DIC_2026>,
--     <UTM_DIC_2026>,
--     <UF_DIC_2026>,
--     'Ley 21.578 art. 1° / DOF dic 2026',
--     '2027-01-01', '2027-12-31',
--     'Firmado por <nombre> <YYYY-MM-DD>'),
--
--    (2028,
--     0.1900,
--     0.1700,
--     <UTA_DIC_2027>,
--     <UTM_DIC_2027>,
--     <UF_DIC_2027>,
--     'Ley 21.578 art. 1° / DOF dic 2027',
--     '2028-01-01', null,
--     'Firmado por <nombre> <YYYY-MM-DD>');

commit;
