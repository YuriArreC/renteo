-- =============================================================================
-- BORRADOR firma contador socio — 01_tax_year_params
-- Checklist §3 (REVISION_CONTADOR_SOCIO.md).
-- Cierra TODOS-CONTADOR.md #3.
--
-- Firma EN SITIO (UPSERT) de la seed placeholder
-- 20260502120000_tax_params_placeholder_seeds.sql para
-- tax_params.tax_year_params.
--
-- ⚠️ Por qué UPSERT y NO delete+insert:
--    tax_year_params es tabla PADRE de idpc_rates / igc_brackets /
--    ppm_pyme_rates / beneficios_topes, todas con FK ON DELETE RESTRICT.
--    Un `delete from tax_year_params` aborta con violación de FK mientras
--    existan filas hijas (siempre existen). El UPSERT actualiza los valores
--    firmados sin borrar la fila, así la integridad referencial queda intacta.
--
-- ✍️ CONTADOR_SOCIO: para cada fila confirmar UTM dic, UTA dic, UF dic
--    contra publicación oficial DOF / SII. Reemplazar 'fuente_legal'
--    con cita real (URL DOF + fecha).
--
-- Cuando esté firmado, mover a:
--   supabase/migrations/YYYYMMDDHHMMSS_tax_year_params_firmado.sql
-- =============================================================================

begin;

-- 1) UPSERT de los años firmados por el contador (AT 2024-2026).
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
     'Firmado por <nombre contador> <YYYY-MM-DD>')

on conflict (tax_year) do update set
    iva_rate             = excluded.iva_rate,
    retencion_honorarios = excluded.retencion_honorarios,
    uta_pesos_dic        = excluded.uta_pesos_dic,
    utm_pesos_dic        = excluded.utm_pesos_dic,
    uf_pesos_dic         = excluded.uf_pesos_dic,
    fuente_legal         = excluded.fuente_legal,
    vigencia_inicio      = excluded.vigencia_inicio,
    vigencia_fin         = excluded.vigencia_fin,
    observaciones        = excluded.observaciones;

-- 2) AT 2027-2028: NO se firman todavía (DOF aún no publica UTM/UTA/UF dic).
--    Las filas placeholder se CONSERVAN a propósito: el recomendador arma
--    una proyección a 3 años (regime.py _HORIZONTE_AÑOS=3) y necesita que
--    exista fila para AT 2027/2028 o compute_idpc/igc levantan
--    MissingTaxYearParams. Quedan como proyección no firmada.
--
-- ✍️ CONTADOR_SOCIO: al cierre de cada AT, refirmar con UPSERT (mismo patrón
--    de arriba) reemplazando la cita PLACEHOLDER por la publicación oficial.

commit;
