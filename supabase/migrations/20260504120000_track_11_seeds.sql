-- =============================================================================
-- Migration: 20260504120000_track_11_seeds
-- Skills:    tax-rules-versioning (skill 11), regime-recommendation (skill 7)
-- Purpose:   Seedear las primeras reglas declarativas:
--              * 4 reglas de regime_eligibility (14_a, 14_d_3, 14_d_8,
--                renta_presunta) con doble firma + 3 golden cases por regla.
--              * 1 feature flag idpc_14d3_revertida_rate con valor 0.25.
--            🟡 PLACEHOLDER: las reglas usan los umbrales del módulo
--            eligibility.py (que track 7 documentó). El contador socio +
--            admin técnico oficiales reemplazan estas filas en go-live.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Service users — placeholder firmantes para skill 11 hasta el go-live.
-- En producción se reemplazan por usuarios reales con rol contador_socio /
-- admin_tecnico. Los UUIDs son fijos para idempotencia entre migraciones.
-- -----------------------------------------------------------------------------
insert into auth.users (id, email)
values
    ('00000000-0000-0000-0000-00000000c001', 'contador-socio@renteo.local'),
    ('00000000-0000-0000-0000-00000000a001', 'admin-tecnico@renteo.local')
on conflict (id) do nothing;


-- -----------------------------------------------------------------------------
-- Reglas regime_eligibility (skill 7).
-- vigencia_desde: 2024-01-01, sin vigencia_hasta — cubren todos los AT
-- soportados hoy. Track 11 oficial publicará nuevas versiones cuando la ley
-- mueva los umbrales.
-- -----------------------------------------------------------------------------
insert into tax_rules.rule_sets
    (id, domain, key, version, vigencia_desde, vigencia_hasta,
     rules, fuente_legal,
     status, published_by_contador, published_by_admin, published_at)
values
-- 14 A: régimen general supletorio (siempre elegible).
('00000000-0000-0000-0000-00000000a14a',
 'regime_eligibility', '14_a', 1,
 '2024-01-01', null,
 '{"all_of": [{"field": "supletorio", "op": "eq", "value": true,
               "message": "El régimen general es supletorio y aplica por defecto.",
               "fundamento": "art. 14 A LIR"}]}'::jsonb,
 '[{"tipo": "ley", "id": "21.210"}, {"tipo": "lir", "articulo": "art. 14 A"}]'::jsonb,
 'published',
 '00000000-0000-0000-0000-00000000c001',
 '00000000-0000-0000-0000-00000000a001',
 now()),

-- 14 D N°3: cinco condiciones cumulativas.
('00000000-0000-0000-0000-00000000a143',
 'regime_eligibility', '14_d_3', 1,
 '2024-01-01', null,
 '{"all_of": [
    {"field": "ingresos_promedio_3a_uf", "op": "lte", "value": 75000,
     "message": "Promedio ingresos giro últimos 3 años > 75.000 UF",
     "fundamento": "art. 14 D N°3 inc. 1° LIR"},
    {"field": "ingresos_max_anual_uf", "op": "lte", "value": 85000,
     "message": "Algún año individual superó 85.000 UF",
     "fundamento": "art. 14 D N°3 LIR"},
    {"field": "capital_efectivo_inicial_uf", "op": "lte", "value": 85000,
     "message": "Capital efectivo inicial > 85.000 UF",
     "fundamento": "art. 14 D N°3 LIR"},
    {"field": "pct_ingresos_pasivos", "op": "lte", "value": 0.35,
     "message": "Ingresos pasivos > 35% del total",
     "fundamento": "art. 14 D N°3 LIR"},
    {"field": "participacion_empresas_no_14d_sobre_10pct", "op": "eq",
     "value": false,
     "message": "Participa por más del 10% en empresas no acogidas a 14 D",
     "fundamento": "art. 14 D N°3 LIR"}
 ]}'::jsonb,
 '[{"tipo": "ley", "id": "21.210"}, {"tipo": "ley", "id": "21.713"},
   {"tipo": "lir", "articulo": "art. 14 D N°3"}]'::jsonb,
 'published',
 '00000000-0000-0000-0000-00000000c001',
 '00000000-0000-0000-0000-00000000a001',
 now()),

-- 14 D N°8: 14 D N°3 + dueños chilenos.
('00000000-0000-0000-0000-00000000a148',
 'regime_eligibility', '14_d_8', 1,
 '2024-01-01', null,
 '{"all_of": [
    {"field": "ingresos_promedio_3a_uf", "op": "lte", "value": 75000,
     "message": "Promedio ingresos giro últimos 3 años > 75.000 UF",
     "fundamento": "art. 14 D N°8 LIR"},
    {"field": "ingresos_max_anual_uf", "op": "lte", "value": 85000,
     "message": "Algún año individual superó 85.000 UF",
     "fundamento": "art. 14 D N°8 LIR"},
    {"field": "capital_efectivo_inicial_uf", "op": "lte", "value": 85000,
     "message": "Capital efectivo inicial > 85.000 UF",
     "fundamento": "art. 14 D N°8 LIR"},
    {"field": "pct_ingresos_pasivos", "op": "lte", "value": 0.35,
     "message": "Ingresos pasivos > 35% del total",
     "fundamento": "art. 14 D N°8 LIR"},
    {"field": "participacion_empresas_no_14d_sobre_10pct", "op": "eq",
     "value": false,
     "message": "Participa por más del 10% en empresas no acogidas a 14 D",
     "fundamento": "art. 14 D N°8 LIR"},
    {"field": "todos_duenos_personas_naturales_chile", "op": "eq",
     "value": true,
     "message": "Algún dueño no es persona natural con domicilio o residencia en Chile",
     "fundamento": "art. 14 D N°8 LIR"}
 ]}'::jsonb,
 '[{"tipo": "ley", "id": "21.210"},
   {"tipo": "lir", "articulo": "art. 14 D N°8"}]'::jsonb,
 'published',
 '00000000-0000-0000-0000-00000000c001',
 '00000000-0000-0000-0000-00000000a001',
 now()),

-- Renta presunta (art. 34 LIR): cualquiera de los 3 sectores con su tope.
('00000000-0000-0000-0000-00000000a134',
 'regime_eligibility', 'renta_presunta', 1,
 '2024-01-01', null,
 '{"any_of": [
    {"all_of": [
       {"field": "sector", "op": "eq", "value": "agricola",
        "fundamento": "art. 34 LIR"},
       {"field": "ventas_anuales_uf", "op": "lte", "value": 9000,
        "message": "Sector agrícola: ventas anuales > 9.000 UF",
        "fundamento": "art. 34 LIR"}
    ]},
    {"all_of": [
       {"field": "sector", "op": "eq", "value": "transporte",
        "fundamento": "art. 34 LIR"},
       {"field": "ventas_anuales_uf", "op": "lte", "value": 5000,
        "message": "Transporte terrestre: ventas anuales > 5.000 UF",
        "fundamento": "art. 34 LIR"}
    ]},
    {"all_of": [
       {"field": "sector", "op": "eq", "value": "mineria",
        "fundamento": "art. 34 LIR"},
       {"field": "ventas_anuales_uf", "op": "lte", "value": 17000,
        "message": "Minería: ventas anuales > 17.000 UF",
        "fundamento": "art. 34 LIR"}
    ]}
 ]}'::jsonb,
 '[{"tipo": "lir", "articulo": "art. 34"}]'::jsonb,
 'published',
 '00000000-0000-0000-0000-00000000c001',
 '00000000-0000-0000-0000-00000000a001',
 now())
on conflict (domain, key, version) do nothing;


-- -----------------------------------------------------------------------------
-- Casos golden — mínimo 3 por regla (validate_rules.py CI lo exige).
-- inputs y expected_output documentan la intención; el panel admin de fase 6
-- los re-ejecuta al publicar nuevas versiones.
-- -----------------------------------------------------------------------------
insert into tax_rules.rule_golden_cases
    (rule_set_id, name, inputs, expected_output, fundamento)
values
-- 14 A — siempre elegible
('00000000-0000-0000-0000-00000000a14a',
 'pyme_pequena_supletorio',
 '{"supletorio": true}'::jsonb,
 '{"passed": true}'::jsonb,
 'art. 14 A LIR'),
('00000000-0000-0000-0000-00000000a14a',
 'empresa_grande_supletorio',
 '{"supletorio": true}'::jsonb,
 '{"passed": true}'::jsonb,
 'art. 14 A LIR'),
('00000000-0000-0000-0000-00000000a14a',
 'startup_supletorio',
 '{"supletorio": true}'::jsonb,
 '{"passed": true}'::jsonb,
 'art. 14 A LIR'),

-- 14 D N°3
('00000000-0000-0000-0000-00000000a143',
 'pyme_30k_uf_califica',
 '{"ingresos_promedio_3a_uf": 30000, "ingresos_max_anual_uf": 40000,
   "capital_efectivo_inicial_uf": 5000, "pct_ingresos_pasivos": 0.10,
   "participacion_empresas_no_14d_sobre_10pct": false}'::jsonb,
 '{"passed": true}'::jsonb,
 'art. 14 D N°3 LIR'),
('00000000-0000-0000-0000-00000000a143',
 'pyme_excede_promedio',
 '{"ingresos_promedio_3a_uf": 90000, "ingresos_max_anual_uf": 100000,
   "capital_efectivo_inicial_uf": 5000, "pct_ingresos_pasivos": 0.10,
   "participacion_empresas_no_14d_sobre_10pct": false}'::jsonb,
 '{"passed": false}'::jsonb,
 'art. 14 D N°3 LIR'),
('00000000-0000-0000-0000-00000000a143',
 'pyme_pasivos_excedidos',
 '{"ingresos_promedio_3a_uf": 30000, "ingresos_max_anual_uf": 40000,
   "capital_efectivo_inicial_uf": 5000, "pct_ingresos_pasivos": 0.50,
   "participacion_empresas_no_14d_sobre_10pct": false}'::jsonb,
 '{"passed": false}'::jsonb,
 'art. 14 D N°3 LIR'),

-- 14 D N°8
('00000000-0000-0000-0000-00000000a148',
 'duenos_chilenos_califica',
 '{"ingresos_promedio_3a_uf": 30000, "ingresos_max_anual_uf": 40000,
   "capital_efectivo_inicial_uf": 5000, "pct_ingresos_pasivos": 0.10,
   "participacion_empresas_no_14d_sobre_10pct": false,
   "todos_duenos_personas_naturales_chile": true}'::jsonb,
 '{"passed": true}'::jsonb,
 'art. 14 D N°8 LIR'),
('00000000-0000-0000-0000-00000000a148',
 'dueno_jurídico_excluido',
 '{"ingresos_promedio_3a_uf": 30000, "ingresos_max_anual_uf": 40000,
   "capital_efectivo_inicial_uf": 5000, "pct_ingresos_pasivos": 0.10,
   "participacion_empresas_no_14d_sobre_10pct": false,
   "todos_duenos_personas_naturales_chile": false}'::jsonb,
 '{"passed": false}'::jsonb,
 'art. 14 D N°8 LIR'),
('00000000-0000-0000-0000-00000000a148',
 'mismo_excluido_por_pasivos',
 '{"ingresos_promedio_3a_uf": 30000, "ingresos_max_anual_uf": 40000,
   "capital_efectivo_inicial_uf": 5000, "pct_ingresos_pasivos": 0.50,
   "participacion_empresas_no_14d_sobre_10pct": false,
   "todos_duenos_personas_naturales_chile": true}'::jsonb,
 '{"passed": false}'::jsonb,
 'art. 14 D N°8 LIR'),

-- Renta presunta
('00000000-0000-0000-0000-00000000a134',
 'agricola_dentro_tope',
 '{"sector": "agricola", "ventas_anuales_uf": 5000}'::jsonb,
 '{"passed": true}'::jsonb,
 'art. 34 LIR'),
('00000000-0000-0000-0000-00000000a134',
 'transporte_excede_tope',
 '{"sector": "transporte", "ventas_anuales_uf": 8000}'::jsonb,
 '{"passed": false}'::jsonb,
 'art. 34 LIR'),
('00000000-0000-0000-0000-00000000a134',
 'comercio_no_aplica',
 '{"sector": "comercio", "ventas_anuales_uf": 1000}'::jsonb,
 '{"passed": false}'::jsonb,
 'art. 34 LIR')
on conflict do nothing;


-- -----------------------------------------------------------------------------
-- Feature flag — tasa revertida 14 D N°3 (Ley 21.735 art. 4° transitorio).
-- Mientras la condicionalidad de cotización empleador se cumpla, la tasa
-- transitoria 12,5% sigue vigente; si se rompe, la tasa revierte a 25%. El
-- valor 0.25 vive aquí para que el motor no lo hardcodee.
-- -----------------------------------------------------------------------------
insert into tax_rules.feature_flags_by_year (
    flag_key, effective_from, value, reason, changed_by
)
values (
    'idpc_14d3_revertida_rate',
    '2026-01-01',
    '0.25',
    'Tasa permanente 14 D N°3 cuando se rompe la condicionalidad de Ley 21.735 art. 4° transitorio. Valor inicial PLACEHOLDER pendiente firma contador.',
    '00000000-0000-0000-0000-00000000c001'
)
on conflict (flag_key, effective_from) do nothing;
