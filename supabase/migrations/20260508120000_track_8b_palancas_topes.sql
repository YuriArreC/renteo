-- =============================================================================
-- Migration: 20260508120000_track_8b_palancas_topes
-- Skills:    scenario-simulator (skill 8), tax-rules-versioning (skill 11)
-- Purpose:   Topes paramétricos para las palancas P2 (SENCE), P6 (I+D) y P9
--            (APV) del simulador. Reusa tax_params.beneficios_topes con
--            vigencia anual.
--            🟡 PLACEHOLDER pendiente firma del contador socio:
--              * credito_id_porcentaje_credito = 0,35 (Ley 20.241).
--              * credito_id_porcentaje_gasto = 0,65 (Ley 20.241).
--              * sence_tope_minimo_utm = 9 UTM (planilla pequeña).
--              * apv_tope_anual_uf = 600 UF (régimen A simplificado).
--              * utm_valor_clp = 70.000 CLP (UTM placeholder).
-- =============================================================================

insert into tax_params.beneficios_topes (
    key, tax_year, valor, unidad, fuente_legal, descripcion
) values
    -- P6 — Crédito I+D
    ('credito_id_porcentaje_credito', 2024, 0.3500, 'porcentaje',
     'PLACEHOLDER — Ley 20.241',
     '35% del desembolso certificado se imputa como crédito IDPC.'),
    ('credito_id_porcentaje_credito', 2025, 0.3500, 'porcentaje',
     'PLACEHOLDER — Ley 20.241', 'Crédito I+D 35%.'),
    ('credito_id_porcentaje_credito', 2026, 0.3500, 'porcentaje',
     'PLACEHOLDER — Ley 20.241', 'Crédito I+D 35%.'),
    ('credito_id_porcentaje_credito', 2027, 0.3500, 'porcentaje',
     'PLACEHOLDER — Ley 20.241', 'Crédito I+D 35%.'),
    ('credito_id_porcentaje_credito', 2028, 0.3500, 'porcentaje',
     'PLACEHOLDER — Ley 20.241', 'Crédito I+D 35%.'),

    ('credito_id_porcentaje_gasto', 2024, 0.6500, 'porcentaje',
     'PLACEHOLDER — Ley 20.241',
     '65% del desembolso certificado se reconoce como gasto deducible RLI.'),
    ('credito_id_porcentaje_gasto', 2025, 0.6500, 'porcentaje',
     'PLACEHOLDER — Ley 20.241', 'Gasto I+D 65%.'),
    ('credito_id_porcentaje_gasto', 2026, 0.6500, 'porcentaje',
     'PLACEHOLDER — Ley 20.241', 'Gasto I+D 65%.'),
    ('credito_id_porcentaje_gasto', 2027, 0.6500, 'porcentaje',
     'PLACEHOLDER — Ley 20.241', 'Gasto I+D 65%.'),
    ('credito_id_porcentaje_gasto', 2028, 0.6500, 'porcentaje',
     'PLACEHOLDER — Ley 20.241', 'Gasto I+D 65%.'),

    -- P2 — SENCE
    ('sence_tope_minimo_utm', 2024, 9.0000, 'utm',
     'PLACEHOLDER — Ley 19.518',
     'Piso alternativo de la franquicia SENCE para planilla pequeña.'),
    ('sence_tope_minimo_utm', 2025, 9.0000, 'utm',
     'PLACEHOLDER — Ley 19.518', 'Tope mínimo SENCE 9 UTM.'),
    ('sence_tope_minimo_utm', 2026, 9.0000, 'utm',
     'PLACEHOLDER — Ley 19.518', 'Tope mínimo SENCE 9 UTM.'),
    ('sence_tope_minimo_utm', 2027, 9.0000, 'utm',
     'PLACEHOLDER — Ley 19.518', 'Tope mínimo SENCE 9 UTM.'),
    ('sence_tope_minimo_utm', 2028, 9.0000, 'utm',
     'PLACEHOLDER — Ley 19.518', 'Tope mínimo SENCE 9 UTM.'),

    -- P9 — APV (régimen A simplificado)
    ('apv_tope_anual_uf', 2024, 600.0000, 'uf',
     'PLACEHOLDER — art. 42 bis LIR; DL 3.500',
     'Tope anual APV régimen A en UF (placeholder MVP).'),
    ('apv_tope_anual_uf', 2025, 600.0000, 'uf',
     'PLACEHOLDER — art. 42 bis LIR', 'Tope anual APV 600 UF.'),
    ('apv_tope_anual_uf', 2026, 600.0000, 'uf',
     'PLACEHOLDER — art. 42 bis LIR', 'Tope anual APV 600 UF.'),
    ('apv_tope_anual_uf', 2027, 600.0000, 'uf',
     'PLACEHOLDER — art. 42 bis LIR', 'Tope anual APV 600 UF.'),
    ('apv_tope_anual_uf', 2028, 600.0000, 'uf',
     'PLACEHOLDER — art. 42 bis LIR', 'Tope anual APV 600 UF.'),

    -- UTM (necesario para convertir tope_minimo_sence y tope I+D a CLP)
    ('utm_valor_clp', 2024, 67000.0000, 'clp',
     'PLACEHOLDER — UTM estimada; track 11c lleva a feed real',
     'Valor UTM en pesos para conversiones del simulador.'),
    ('utm_valor_clp', 2025, 68000.0000, 'clp',
     'PLACEHOLDER — UTM estimada', 'Valor UTM en pesos.'),
    ('utm_valor_clp', 2026, 70000.0000, 'clp',
     'PLACEHOLDER — UTM estimada', 'Valor UTM en pesos.'),
    ('utm_valor_clp', 2027, 71000.0000, 'clp',
     'PLACEHOLDER — UTM estimada', 'Valor UTM en pesos.'),
    ('utm_valor_clp', 2028, 73000.0000, 'clp',
     'PLACEHOLDER — UTM estimada', 'Valor UTM en pesos.')
on conflict (tax_year, key) do nothing;
