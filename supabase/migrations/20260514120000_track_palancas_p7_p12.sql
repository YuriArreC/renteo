-- =============================================================================
-- Migration: 20260514120000_track_palancas_p7_p12
-- Skills:    scenario-simulator (skill 8), tax-rules-versioning (skill 11)
-- Purpose:   Topes paramétricos para las 5 palancas restantes (skill 8 §"12
--            palancas lícitas"):
--              * P7  PPM extraordinario (art. 84 LIR)
--              * P8  Postergación IVA Pro PyME (Ley 21.578 art. 64 N°9 CT)
--              * P10 Crédito por reinversión / Crédito Fomento Mercado (CFM)
--              * P11 Depreciación acelerada art. 31 N°5 LIR
--              * P12 Cambio de régimen (sin parámetro monetario; flag puro)
--            🟡 PLACEHOLDER pendiente firma del contador socio. Cualquier
--            cambio de tasa / tope se resuelve con nueva fila por tax_year,
--            no edición de código (skill 11).
-- =============================================================================

insert into tax_params.beneficios_topes (
    key, tax_year, valor, unidad, fuente_legal, descripcion
) values
    -- P7 — PPM extraordinario.
    -- "Pago Provisional Mensual extraordinario" reduce el saldo a pagar
    -- en F22 al imputarse contra IDPC e IGC. Tope: el contribuyente
    -- puede aumentar la tasa habitual sin máximo legal directo, pero
    -- bandera roja si supera 2x la tasa habitual del régimen.
    ('ppm_extraordinario_max_factor', 2024, 2.0000, 'factor',
     'PLACEHOLDER — art. 84 LIR + Circular SII 6/2025',
     'Múltiplo máximo razonable sobre la tasa PPM habitual; sobre eso bandera amarilla.'),
    ('ppm_extraordinario_max_factor', 2025, 2.0000, 'factor',
     'PLACEHOLDER — art. 84 LIR', 'Múltiplo máximo PPM extraordinario.'),
    ('ppm_extraordinario_max_factor', 2026, 2.0000, 'factor',
     'PLACEHOLDER — art. 84 LIR', 'Múltiplo máximo PPM extraordinario.'),
    ('ppm_extraordinario_max_factor', 2027, 2.0000, 'factor',
     'PLACEHOLDER — art. 84 LIR', 'Múltiplo máximo PPM extraordinario.'),
    ('ppm_extraordinario_max_factor', 2028, 2.0000, 'factor',
     'PLACEHOLDER — art. 84 LIR', 'Múltiplo máximo PPM extraordinario.'),

    -- P8 — Postergación IVA Pro PyME.
    -- Permite posponer el pago del débito IVA del mes hasta 60 días
    -- (art. 64 N°9 CT). Solo afecta caja, no carga tributaria anual,
    -- pero cuenta como palanca de cierre y suma score de oportunidad.
    ('iva_postergacion_dias', 2024, 60.0000, 'dias',
     'PLACEHOLDER — art. 64 N°9 CT; Ley 21.578',
     'Días máximos de postergación IVA Pro PyME.'),
    ('iva_postergacion_dias', 2025, 60.0000, 'dias',
     'PLACEHOLDER — art. 64 N°9 CT', 'Días postergación IVA.'),
    ('iva_postergacion_dias', 2026, 60.0000, 'dias',
     'PLACEHOLDER — art. 64 N°9 CT', 'Días postergación IVA.'),
    ('iva_postergacion_dias', 2027, 60.0000, 'dias',
     'PLACEHOLDER — art. 64 N°9 CT', 'Días postergación IVA.'),
    ('iva_postergacion_dias', 2028, 60.0000, 'dias',
     'PLACEHOLDER — art. 64 N°9 CT', 'Días postergación IVA.'),

    -- P10 — Crédito por reinversión (Crédito Fomento Mercado / CFM).
    -- Inversión en activos fijos que da derecho a crédito contra IDPC
    -- (art. 33 bis LIR). Tasa 4-6% según vida útil; cap en UTM.
    ('credito_reinversion_porcentaje', 2024, 0.0600, 'porcentaje',
     'PLACEHOLDER — art. 33 bis LIR',
     'Crédito IDPC por inversión en activo fijo nuevo (PYME).'),
    ('credito_reinversion_porcentaje', 2025, 0.0600, 'porcentaje',
     'PLACEHOLDER — art. 33 bis LIR', 'Crédito reinversión PYME 6%.'),
    ('credito_reinversion_porcentaje', 2026, 0.0600, 'porcentaje',
     'PLACEHOLDER — art. 33 bis LIR', 'Crédito reinversión PYME 6%.'),
    ('credito_reinversion_porcentaje', 2027, 0.0600, 'porcentaje',
     'PLACEHOLDER — art. 33 bis LIR', 'Crédito reinversión PYME 6%.'),
    ('credito_reinversion_porcentaje', 2028, 0.0600, 'porcentaje',
     'PLACEHOLDER — art. 33 bis LIR', 'Crédito reinversión PYME 6%.'),

    ('credito_reinversion_tope_utm', 2024, 500.0000, 'utm',
     'PLACEHOLDER — art. 33 bis LIR',
     'Tope anual del crédito por inversión en activo fijo (PYME).'),
    ('credito_reinversion_tope_utm', 2025, 500.0000, 'utm',
     'PLACEHOLDER — art. 33 bis LIR', 'Tope crédito reinversión 500 UTM.'),
    ('credito_reinversion_tope_utm', 2026, 500.0000, 'utm',
     'PLACEHOLDER — art. 33 bis LIR', 'Tope crédito reinversión 500 UTM.'),
    ('credito_reinversion_tope_utm', 2027, 500.0000, 'utm',
     'PLACEHOLDER — art. 33 bis LIR', 'Tope crédito reinversión 500 UTM.'),
    ('credito_reinversion_tope_utm', 2028, 500.0000, 'utm',
     'PLACEHOLDER — art. 33 bis LIR', 'Tope crédito reinversión 500 UTM.'),

    -- P11 — Depreciación acelerada art. 31 N°5 LIR.
    -- Permite usar 1/3 de la vida útil normal, asignando un cargo a
    -- gasto mayor en cada ejercicio. El factor es la fracción de la
    -- vida útil que efectivamente se deprecia en el año.
    ('depreciacion_acelerada_factor', 2024, 3.0000, 'factor',
     'PLACEHOLDER — art. 31 N°5 LIR',
     'Múltiplo del cargo anual cuando se opta por dep. acelerada vs normal.'),
    ('depreciacion_acelerada_factor', 2025, 3.0000, 'factor',
     'PLACEHOLDER — art. 31 N°5 LIR', 'Factor dep. acelerada 3x.'),
    ('depreciacion_acelerada_factor', 2026, 3.0000, 'factor',
     'PLACEHOLDER — art. 31 N°5 LIR', 'Factor dep. acelerada 3x.'),
    ('depreciacion_acelerada_factor', 2027, 3.0000, 'factor',
     'PLACEHOLDER — art. 31 N°5 LIR', 'Factor dep. acelerada 3x.'),
    ('depreciacion_acelerada_factor', 2028, 3.0000, 'factor',
     'PLACEHOLDER — art. 31 N°5 LIR', 'Factor dep. acelerada 3x.')

on conflict (tax_year, key) do nothing;

-- -----------------------------------------------------------------------------
-- Lista blanca de recomendaciones — v2.
-- Agrega palanca_id de las 3 palancas nuevas que no estaban en v1
-- (`ppm_extraordinario`, `credito_reinversion`, `depreciacion_acelerada`).
-- v1 sigue vigente para escenarios persistidos previamente; v2 cubre los
-- nuevos cálculos sin redeploy de código (skill 11). Doble firma de
-- contador-socio + admin-tecnico se hereda del seed track 11.
-- -----------------------------------------------------------------------------

update tax_rules.rule_sets
   set vigencia_hasta = current_date
 where id = '00000000-0000-0000-0000-00000000a1b1'
   and vigencia_hasta is null;

insert into tax_rules.rule_sets
    (id, domain, key, version, vigencia_desde, vigencia_hasta,
     rules, fuente_legal,
     status, published_by_contador, published_by_admin, published_at)
values
('00000000-0000-0000-0000-00000000a1b2',
 'recomendacion_whitelist', 'global', 2,
 current_date, null,
 '{"items": [
    {"id": "cambio_regimen", "label": "Cambio de régimen tributario",
     "fundamento": "arts. 14 A, 14 D LIR; Circular SII 53/2025"},
    {"id": "dep_instantanea", "label": "Depreciación instantánea",
     "fundamento": "art. 31 N°5 bis LIR; Oficio SII 715/2025"},
    {"id": "depreciacion_acelerada", "label": "Depreciación acelerada",
     "fundamento": "art. 31 N°5 LIR"},
    {"id": "sence", "label": "Franquicia SENCE",
     "fundamento": "Ley 19.518"},
    {"id": "rebaja_14e", "label": "Rebaja RLI por reinversión",
     "fundamento": "art. 14 E LIR"},
    {"id": "postergacion_iva", "label": "Postergación IVA Pro PyME",
     "fundamento": "Ley 21.210; art. 64 N°9 CT"},
    {"id": "iva_postergacion", "label": "Postergación IVA Pro PyME (id alterno)",
     "fundamento": "art. 64 N°9 CT"},
    {"id": "credito_id", "label": "Crédito I+D certificado",
     "fundamento": "Ley 20.241; Ley 21.755"},
    {"id": "credito_reinversion", "label": "Crédito por inversión en activo fijo",
     "fundamento": "art. 33 bis LIR"},
    {"id": "ppm_extraordinario", "label": "PPM extraordinario",
     "fundamento": "art. 84 LIR"},
    {"id": "donaciones", "label": "Donaciones con beneficio tributario",
     "fundamento": "Ley Valdés y leyes complementarias"},
    {"id": "credito_ipe", "label": "Crédito Impuesto Pagado Extranjero",
     "fundamento": "arts. 41 A y 41 C LIR"},
    {"id": "sueldo_empresarial", "label": "Sueldo empresarial al socio activo",
     "fundamento": "art. 31 N°6 inc. 3° LIR"},
    {"id": "retiros_adicionales", "label": "Retiros vs reinversión",
     "fundamento": "arts. 14 A, 14 D LIR; Circular SII 73/2020"},
    {"id": "timing_facturacion", "label": "Timing de facturación dentro del período",
     "fundamento": "Ley IVA arts. 9 y 55"},
    {"id": "apv", "label": "APV régimen A o B",
     "fundamento": "art. 42 bis LIR; DL 3.500"}
 ]}'::jsonb,
 '[{"tipo": "ct", "articulo": "art. 4 bis"},
   {"tipo": "ct", "articulo": "art. 100 bis"},
   {"tipo": "circular_sii", "id": "65/2015"}]'::jsonb,
 'published',
 '00000000-0000-0000-0000-00000000c001',
 '00000000-0000-0000-0000-00000000a001',
 now())
on conflict (domain, key, version) do nothing;

-- Golden cases para v2: validamos que las 3 nuevas palancas pasen.
insert into tax_rules.rule_golden_cases
    (rule_set_id, name, inputs, expected_output, fundamento)
values
('00000000-0000-0000-0000-00000000a1b2',
 'palanca_ppm_extraordinario_aceptada',
 '{"item_id": "ppm_extraordinario"}'::jsonb,
 '{"whitelisted": true}'::jsonb,
 'art. 84 LIR'),
('00000000-0000-0000-0000-00000000a1b2',
 'palanca_credito_reinversion_aceptada',
 '{"item_id": "credito_reinversion"}'::jsonb,
 '{"whitelisted": true}'::jsonb,
 'art. 33 bis LIR'),
('00000000-0000-0000-0000-00000000a1b2',
 'palanca_depreciacion_acelerada_aceptada',
 '{"item_id": "depreciacion_acelerada"}'::jsonb,
 '{"whitelisted": true}'::jsonb,
 'art. 31 N°5 LIR')
on conflict do nothing;
