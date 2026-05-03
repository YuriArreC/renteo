-- =============================================================================
-- Migration: 20260502120000_tax_params_placeholder_seeds
-- Skills:    chilean-tax-engine (skill 3), tax-rules-versioning (skill 11)
-- Status:    🟡 PLACEHOLDER — pendiente firma del CONTADOR_SOCIO.
--
--            Los valores cargados aquí son razonables pero NO están
--            firmados. El campo `fuente_legal` deja explícito que son
--            placeholder y referencia los ítems #1-#3 de TODOS-CONTADOR.md
--            que siguen abiertos.
--
--            El motor (`compute_idpc`, `compute_igc`, `compute_ppm`)
--            consume estas filas para que el plumbing funcione end-to-end.
--            Los tests golden en apps/api/tests/golden/ están marcados
--            @pytest.mark.xfail hasta que esta migración sea reemplazada
--            por una versión FIRMADA por contador socio + admin técnico.
--
--            Cuando el contador entregue las tablas oficiales:
--              1. Crear nueva migración 2026MMDD_tax_params_at2024_2028.sql
--                 con `fuente_legal` real (Ley X, Circular Y).
--              2. Hacer DELETE + INSERT atómico para no dejar rows obsoletas.
--              3. Quitar @pytest.mark.xfail de los tests golden.
--              4. CI debería pasar: si falla, hay un bug en el motor.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- tax_year_params (UTA/UTM/UF dic, IVA, retención BHE)
-- Valores aprox basados en publicaciones SII (no firmados oficialmente).
-- -----------------------------------------------------------------------------

insert into tax_params.tax_year_params (
    tax_year, iva_rate, retencion_honorarios,
    uta_pesos_dic, utm_pesos_dic, uf_pesos_dic,
    fuente_legal, vigencia_inicio, vigencia_fin, observaciones
) values
    (2024, 0.1900, 0.1300,  790992,  65916, 37553.7800,
     'PLACEHOLDER — pendiente TODOS-CONTADOR.md #3',
     '2024-01-01', '2024-12-31', 'Valores aprox publicación SII; no firmados.'),
    (2025, 0.1900, 0.1450,  812096,  67675, 38414.0000,
     'PLACEHOLDER — pendiente TODOS-CONTADOR.md #3',
     '2025-01-01', '2025-12-31', 'Valores aprox; no firmados.'),
    (2026, 0.1900, 0.1525,  834504,  69542, 39280.0000,
     'PLACEHOLDER — pendiente TODOS-CONTADOR.md #3 (rampa BHE 15.25% Ley 21.578)',
     '2026-01-01', '2026-12-31', 'Valores aprox; no firmados.'),
    (2027, 0.1900, 0.1600,  857500,  71458, 40160.0000,
     'PLACEHOLDER — pendiente TODOS-CONTADOR.md #3 (rampa BHE 16% Ley 21.578)',
     '2027-01-01', '2027-12-31', 'Valores aprox; no firmados.'),
    (2028, 0.1900, 0.1700,  881400,  73450, 41060.0000,
     'PLACEHOLDER — pendiente TODOS-CONTADOR.md #3 (rampa BHE 17% Ley 21.578)',
     '2028-01-01', null, 'Valores aprox; no firmados.')
on conflict (tax_year) do nothing;

-- -----------------------------------------------------------------------------
-- idpc_rates (tasa IDPC por régimen y año)
-- -----------------------------------------------------------------------------

insert into tax_params.idpc_rates (
    tax_year, regimen, rate, es_transitoria, condicion_aplicacion, fuente_legal
) values
    -- 14 A — régimen general semi integrado, tasa estable 27%
    (2024, '14_a', 0.2700, false, null,
     'PLACEHOLDER — pendiente TODOS-CONTADOR.md #1 (art. 14 A LIR, 27% estable post Ley 21.210)'),
    (2025, '14_a', 0.2700, false, null,
     'PLACEHOLDER — pendiente TODOS-CONTADOR.md #1'),
    (2026, '14_a', 0.2700, false, null,
     'PLACEHOLDER — pendiente TODOS-CONTADOR.md #1'),
    (2027, '14_a', 0.2700, false, null,
     'PLACEHOLDER — pendiente TODOS-CONTADOR.md #1'),
    (2028, '14_a', 0.2700, false, null,
     'PLACEHOLDER — pendiente TODOS-CONTADOR.md #1'),

    -- 14 D N°3 — Pro Pyme General, con rampa transitoria 12.5% AT 2026-2028
    (2024, '14_d_3', 0.1000, true, 'Tasa transitoria post-pandemia (Ley 21.578)',
     'PLACEHOLDER — pendiente TODOS-CONTADOR.md #1'),
    (2025, '14_d_3', 0.2500, false, null,
     'PLACEHOLDER — pendiente TODOS-CONTADOR.md #1'),
    (2026, '14_d_3', 0.1250, true,
     'Tasa transitoria 12.5% AT 2026-2028 condicionada al art. 4° transitorio Ley 21.735',
     'PLACEHOLDER — pendiente TODOS-CONTADOR.md #1 (Ley 21.755, Circular SII 53/2025)'),
    (2027, '14_d_3', 0.1250, true,
     'Continuación tasa transitoria 12.5% (sujeta a cumplimiento Ley 21.735)',
     'PLACEHOLDER — pendiente TODOS-CONTADOR.md #1'),
    (2028, '14_d_3', 0.1250, true,
     'Continuación tasa transitoria 12.5% (sujeta a cumplimiento Ley 21.735)',
     'PLACEHOLDER — pendiente TODOS-CONTADOR.md #1'),

    -- 14 D N°8 — Pro Pyme Transparente, IDPC 0% (transparencia)
    (2024, '14_d_8', 0.0000, false, 'Régimen transparente: IDPC corre por dueños',
     'PLACEHOLDER — pendiente TODOS-CONTADOR.md #1'),
    (2025, '14_d_8', 0.0000, false, 'Régimen transparente',
     'PLACEHOLDER — pendiente TODOS-CONTADOR.md #1'),
    (2026, '14_d_8', 0.0000, false, 'Régimen transparente',
     'PLACEHOLDER — pendiente TODOS-CONTADOR.md #1'),
    (2027, '14_d_8', 0.0000, false, 'Régimen transparente',
     'PLACEHOLDER — pendiente TODOS-CONTADOR.md #1'),
    (2028, '14_d_8', 0.0000, false, 'Régimen transparente',
     'PLACEHOLDER — pendiente TODOS-CONTADOR.md #1')
on conflict (tax_year, regimen) do nothing;

-- -----------------------------------------------------------------------------
-- igc_brackets (8 tramos en UTA, art. 52 LIR)
-- Tramos para AT 2026 según publicación SII vigente (sin firma).
-- -----------------------------------------------------------------------------

insert into tax_params.igc_brackets (
    tax_year, tramo, desde_uta, hasta_uta, tasa, rebajar_uta
) values
    -- AT 2024
    (2024, 1,    0.0000,   13.5000, 0.0000,   0.0000),
    (2024, 2,   13.5000,   30.0000, 0.0400,   0.5400),
    (2024, 3,   30.0000,   50.0000, 0.0800,   1.7400),
    (2024, 4,   50.0000,   70.0000, 0.1350,   4.4900),
    (2024, 5,   70.0000,   90.0000, 0.2300,  11.1400),
    (2024, 6,   90.0000,  120.0000, 0.3040,  17.8000),
    (2024, 7,  120.0000,  310.0000, 0.3500,  23.3200),
    (2024, 8,  310.0000,  null,     0.4000,  38.8200),

    -- AT 2025 (mismos tramos, mismas tasas)
    (2025, 1,    0.0000,   13.5000, 0.0000,   0.0000),
    (2025, 2,   13.5000,   30.0000, 0.0400,   0.5400),
    (2025, 3,   30.0000,   50.0000, 0.0800,   1.7400),
    (2025, 4,   50.0000,   70.0000, 0.1350,   4.4900),
    (2025, 5,   70.0000,   90.0000, 0.2300,  11.1400),
    (2025, 6,   90.0000,  120.0000, 0.3040,  17.8000),
    (2025, 7,  120.0000,  310.0000, 0.3500,  23.3200),
    (2025, 8,  310.0000,  null,     0.4000,  38.8200),

    -- AT 2026
    (2026, 1,    0.0000,   13.5000, 0.0000,   0.0000),
    (2026, 2,   13.5000,   30.0000, 0.0400,   0.5400),
    (2026, 3,   30.0000,   50.0000, 0.0800,   1.7400),
    (2026, 4,   50.0000,   70.0000, 0.1350,   4.4900),
    (2026, 5,   70.0000,   90.0000, 0.2300,  11.1400),
    (2026, 6,   90.0000,  120.0000, 0.3040,  17.8000),
    (2026, 7,  120.0000,  310.0000, 0.3500,  23.3200),
    (2026, 8,  310.0000,  null,     0.4000,  38.8200),

    -- AT 2027
    (2027, 1,    0.0000,   13.5000, 0.0000,   0.0000),
    (2027, 2,   13.5000,   30.0000, 0.0400,   0.5400),
    (2027, 3,   30.0000,   50.0000, 0.0800,   1.7400),
    (2027, 4,   50.0000,   70.0000, 0.1350,   4.4900),
    (2027, 5,   70.0000,   90.0000, 0.2300,  11.1400),
    (2027, 6,   90.0000,  120.0000, 0.3040,  17.8000),
    (2027, 7,  120.0000,  310.0000, 0.3500,  23.3200),
    (2027, 8,  310.0000,  null,     0.4000,  38.8200),

    -- AT 2028
    (2028, 1,    0.0000,   13.5000, 0.0000,   0.0000),
    (2028, 2,   13.5000,   30.0000, 0.0400,   0.5400),
    (2028, 3,   30.0000,   50.0000, 0.0800,   1.7400),
    (2028, 4,   50.0000,   70.0000, 0.1350,   4.4900),
    (2028, 5,   70.0000,   90.0000, 0.2300,  11.1400),
    (2028, 6,   90.0000,  120.0000, 0.3040,  17.8000),
    (2028, 7,  120.0000,  310.0000, 0.3500,  23.3200),
    (2028, 8,  310.0000,  null,     0.4000,  38.8200)
on conflict (tax_year, tramo) do nothing;

-- -----------------------------------------------------------------------------
-- ppm_pyme_rates (PPM PyME por régimen y año)
-- Tasa transitoria Ley 21.755 + Circular SII 53/2025: 0.125% / 0.25%
-- -----------------------------------------------------------------------------

insert into tax_params.ppm_pyme_rates (
    tax_year, regimen, umbral_uf, tasa_bajo, tasa_alto,
    es_transitoria, fuente_legal
) values
    (2025, '14_d_3', 50000.00, 0.00125, 0.00250, true,
     'PLACEHOLDER — pendiente TODOS-CONTADOR.md (Circular SII 53/2025 transitoria)'),
    (2026, '14_d_3', 50000.00, 0.00125, 0.00250, true,
     'PLACEHOLDER — pendiente TODOS-CONTADOR.md'),
    (2027, '14_d_3', 50000.00, 0.00125, 0.00250, true,
     'PLACEHOLDER — pendiente TODOS-CONTADOR.md'),

    (2024, '14_d_8', 50000.00, 0.00000, 0.00000, false,
     'PLACEHOLDER — pendiente TODOS-CONTADOR.md (régimen transparente, sin PPM propio)'),
    (2025, '14_d_8', 50000.00, 0.00000, 0.00000, false,
     'PLACEHOLDER — pendiente TODOS-CONTADOR.md'),
    (2026, '14_d_8', 50000.00, 0.00000, 0.00000, false,
     'PLACEHOLDER — pendiente TODOS-CONTADOR.md')
on conflict (tax_year, regimen) do nothing;

-- -----------------------------------------------------------------------------
-- beneficios_topes (topes parametrizados)
-- -----------------------------------------------------------------------------

insert into tax_params.beneficios_topes (
    key, tax_year, valor, unidad, fuente_legal, descripcion
) values
    ('rebaja_14e_uf', 2024, 5000.0000, 'uf',
     'PLACEHOLDER — art. 14 E LIR; pendiente firma',
     'Tope absoluto rebaja por reinversión 14 E'),
    ('rebaja_14e_uf', 2025, 5000.0000, 'uf',
     'PLACEHOLDER — art. 14 E LIR', 'Tope rebaja 14 E'),
    ('rebaja_14e_uf', 2026, 5000.0000, 'uf',
     'PLACEHOLDER — art. 14 E LIR', 'Tope rebaja 14 E'),
    ('rebaja_14e_porcentaje', 2024, 0.5000, 'porcentaje',
     'PLACEHOLDER — art. 14 E LIR', '50% RLI máximo rebajable'),
    ('rebaja_14e_porcentaje', 2025, 0.5000, 'porcentaje',
     'PLACEHOLDER — art. 14 E LIR', '50% RLI'),
    ('rebaja_14e_porcentaje', 2026, 0.5000, 'porcentaje',
     'PLACEHOLDER — art. 14 E LIR', '50% RLI'),

    ('credito_id_tope_utm', 2024, 15000.0000, 'utm',
     'PLACEHOLDER — Ley 20.241', 'Tope crédito I+D 15.000 UTM'),
    ('credito_id_tope_utm', 2025, 15000.0000, 'utm',
     'PLACEHOLDER — Ley 20.241', 'Tope crédito I+D'),
    ('credito_id_tope_utm', 2026, 15000.0000, 'utm',
     'PLACEHOLDER — Ley 20.241 (extensión Ley 21.755)', 'Tope crédito I+D'),

    ('sence_porcentaje_planilla', 2024, 0.0100, 'porcentaje',
     'PLACEHOLDER — Ley 19.518', '1% planilla anual SENCE'),
    ('sence_porcentaje_planilla', 2025, 0.0100, 'porcentaje',
     'PLACEHOLDER — Ley 19.518', '1% planilla'),
    ('sence_porcentaje_planilla', 2026, 0.0100, 'porcentaje',
     'PLACEHOLDER — Ley 19.518', '1% planilla'),

    ('credito_5pct_ultimo_tramo_igc', 2024, 0.0500, 'porcentaje',
     'PLACEHOLDER — art. 56 LIR', 'Crédito 5% sobre fracción afecta al 40%'),
    ('credito_5pct_ultimo_tramo_igc', 2025, 0.0500, 'porcentaje',
     'PLACEHOLDER — art. 56 LIR', 'Crédito 5% último tramo IGC'),
    ('credito_5pct_ultimo_tramo_igc', 2026, 0.0500, 'porcentaje',
     'PLACEHOLDER — art. 56 LIR', 'Crédito 5% último tramo IGC')
on conflict (tax_year, key) do nothing;
