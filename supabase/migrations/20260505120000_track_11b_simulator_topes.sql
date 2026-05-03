-- =============================================================================
-- Migration: 20260505120000_track_11b_simulator_topes
-- Skills:    tax-rules-versioning (skill 11), scenario-simulator (skill 8)
-- Purpose:   Mover los últimos hardcodes del simulador a tax_params:
--              * sueldo_empresarial_tope_mensual_uf — heurística MVP (250 UF
--                por mes) para la bandera P5; el contador socio firmará el
--                rango razonable definitivo.
--              * uf_valor_clp — UF placeholder mientras no llegue feed
--                oficial. Track 11c lo reemplazará por carga diaria/mensual.
-- =============================================================================

insert into tax_params.beneficios_topes (
    key, tax_year, valor, unidad, fuente_legal, descripcion
) values
    ('sueldo_empresarial_tope_mensual_uf', 2024, 250.0000, 'uf',
     'PLACEHOLDER — heurística MVP, art. 31 N°6 inc. 3° LIR',
     'Tope mensual sugerido para sueldo empresarial al socio activo (bandera P5).'),
    ('sueldo_empresarial_tope_mensual_uf', 2025, 250.0000, 'uf',
     'PLACEHOLDER — heurística MVP, art. 31 N°6 inc. 3° LIR',
     'Tope mensual sugerido sueldo empresarial.'),
    ('sueldo_empresarial_tope_mensual_uf', 2026, 250.0000, 'uf',
     'PLACEHOLDER — heurística MVP, art. 31 N°6 inc. 3° LIR',
     'Tope mensual sugerido sueldo empresarial.'),
    ('sueldo_empresarial_tope_mensual_uf', 2027, 250.0000, 'uf',
     'PLACEHOLDER — heurística MVP, art. 31 N°6 inc. 3° LIR',
     'Tope mensual sugerido sueldo empresarial.'),
    ('sueldo_empresarial_tope_mensual_uf', 2028, 250.0000, 'uf',
     'PLACEHOLDER — heurística MVP, art. 31 N°6 inc. 3° LIR',
     'Tope mensual sugerido sueldo empresarial.'),

    ('uf_valor_clp', 2024, 38000.0000, 'clp',
     'PLACEHOLDER — UF estimada para conversiones; track 11c lleva a feed real',
     'Valor UF en pesos para conversiones del simulador / proyecciones.'),
    ('uf_valor_clp', 2025, 38000.0000, 'clp',
     'PLACEHOLDER — UF estimada',
     'Valor UF en pesos.'),
    ('uf_valor_clp', 2026, 38000.0000, 'clp',
     'PLACEHOLDER — UF estimada',
     'Valor UF en pesos.'),
    ('uf_valor_clp', 2027, 38000.0000, 'clp',
     'PLACEHOLDER — UF estimada',
     'Valor UF en pesos.'),
    ('uf_valor_clp', 2028, 38000.0000, 'clp',
     'PLACEHOLDER — UF estimada',
     'Valor UF en pesos.')
on conflict (tax_year, key) do nothing;
