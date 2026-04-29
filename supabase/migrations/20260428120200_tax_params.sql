-- =============================================================================
-- Migration: 20260428120200_tax_params
-- Skills:    chilean-tax-engine (skill 3), tax-data-model (skill 6)
-- Purpose:   Parametrización temporal del motor tributario. Toda tasa, tramo,
--            tope o factor vive en estas tablas con vigencia por año
--            tributario; el motor las consulta. Hardcoding queda prohibido
--            por test_no_hardcoded en CI (skill 11).
--
--            Datos de referencia GLOBALES (no per-tenant). RLS (B12) habilita
--            SELECT a authenticated; mutaciones solo desde service_role vía
--            migración versionada.
--
--            Seeds AT 2024-2028 entran en fase 1 (firmados por contador socio).
-- =============================================================================

-- -----------------------------------------------------------------------------
-- tax_params.tax_year_params
-- -----------------------------------------------------------------------------
create table if not exists tax_params.tax_year_params (
    tax_year                int primary key,
    iva_rate                numeric(5, 4) not null,
    retencion_honorarios    numeric(5, 4) not null,
    uta_pesos_dic           numeric(12, 2) not null,
    utm_pesos_dic           numeric(12, 2) not null,
    uf_pesos_dic            numeric(12, 4) not null,
    fuente_legal            text not null,
    vigencia_inicio         date not null,
    vigencia_fin            date,
    observaciones           text
);

comment on table tax_params.tax_year_params is
    'Parámetros generales por año tributario (IVA, retención BHE, UTA/UTM/UF dic).';
comment on column tax_params.tax_year_params.fuente_legal is
    'Cita normativa (ley + circular/oficio) que respalda los valores de la fila.';

-- -----------------------------------------------------------------------------
-- tax_params.idpc_rates
-- -----------------------------------------------------------------------------
create table if not exists tax_params.idpc_rates (
    tax_year                int not null
                            references tax_params.tax_year_params(tax_year)
                            on delete restrict,
    regimen                 text not null
                            check (regimen in ('14_a', '14_d_3', '14_d_8')),
    rate                    numeric(5, 4) not null,
    es_transitoria          boolean not null default false,
    condicion_aplicacion    text,
    fuente_legal            text not null,
    primary key (tax_year, regimen)
);

comment on table tax_params.idpc_rates is
    'Tasa IDPC por (año tributario, régimen). Soporta tasas transitorias condicionadas (ej. 12,5% AT 2026 régimen 14 D N°3, condicionado a Ley 21.735).';
comment on column tax_params.idpc_rates.condicion_aplicacion is
    'Texto que describe condicionalidad si aplica (referencia a feature flag por tax_year cuando corresponda).';

-- -----------------------------------------------------------------------------
-- tax_params.igc_brackets
-- -----------------------------------------------------------------------------
create table if not exists tax_params.igc_brackets (
    tax_year        int not null
                    references tax_params.tax_year_params(tax_year)
                    on delete restrict,
    tramo           int not null check (tramo between 1 and 8),
    desde_uta       numeric(8, 4) not null,
    hasta_uta       numeric(8, 4),
    tasa            numeric(5, 4) not null,
    rebajar_uta     numeric(8, 4) not null,
    primary key (tax_year, tramo),
    check (
        (tramo = 8 and hasta_uta is null)
        or (tramo < 8 and hasta_uta is not null and hasta_uta > desde_uta)
    )
);

comment on table tax_params.igc_brackets is
    'Tramos del Impuesto Global Complementario (8 tramos en UTA, art. 52 LIR). Tramo 8 abierto: hasta_uta = NULL. Crédito 5% último tramo (art. 56 LIR) se aplica en código del motor.';

-- -----------------------------------------------------------------------------
-- tax_params.ppm_pyme_rates
-- -----------------------------------------------------------------------------
create table if not exists tax_params.ppm_pyme_rates (
    tax_year            int not null
                        references tax_params.tax_year_params(tax_year)
                        on delete restrict,
    regimen             text not null
                        check (regimen in ('14_d_3', '14_d_8')),
    umbral_uf           numeric(12, 2) not null,
    tasa_bajo           numeric(6, 5) not null,
    tasa_alto           numeric(6, 5) not null,
    es_transitoria      boolean not null default false,
    fuente_legal        text not null,
    primary key (tax_year, regimen)
);

comment on table tax_params.ppm_pyme_rates is
    'Tasa PPM PyME por régimen y año, con umbral de ingresos UF que separa tasa baja vs alta (Circular SII 53/2025 transitoria).';

-- -----------------------------------------------------------------------------
-- tax_params.beneficios_topes — topes específicos parametrizados
-- -----------------------------------------------------------------------------
create table if not exists tax_params.beneficios_topes (
    key             text not null,
    tax_year        int not null
                    references tax_params.tax_year_params(tax_year)
                    on delete restrict,
    valor           numeric(18, 4) not null,
    unidad          text not null
                    check (unidad in ('uf', 'utm', 'uta', 'clp', 'porcentaje')),
    fuente_legal    text not null,
    descripcion     text,
    primary key (tax_year, key)
);

comment on table tax_params.beneficios_topes is
    'Topes y factores numéricos que dependen del año tributario (ej. rebaja 14 E 5.000 UF, crédito I+D 15.000 UTM, planilla SENCE 1%).';
comment on column tax_params.beneficios_topes.key is
    'Identificador estable del tope (snake_case). Ejemplos: rebaja_14e_uf, sence_porcentaje_planilla, credito_id_topе_utm.';
