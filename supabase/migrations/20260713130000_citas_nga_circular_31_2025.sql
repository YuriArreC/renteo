-- =============================================================================
-- Corrección de cita legal: NGA → Circular SII N°31 de 2025
--
-- Skills:  tax-compliance-guardrails (1), tax-rules-versioning (11).
-- Cierra:  TODO-CONTADOR #31.
--
-- PROBLEMA
-- La lista blanca de recomendaciones (`recomendacion_whitelist/global`) cita
-- como fundamento de la Norma General Antielusión la **Circular SII N°65 de
-- 2015**. Esa circular fue **DEJADA SIN EFECTO** por la **Circular SII N°31 de
-- 2025** (17-abr-2025), que instruye la NGA tras las Leyes 21.713 y 21.716.
--
-- O sea: hoy el motor cita, como fundamento de cada recomendación que emite,
-- una circular derogada. Verificado contra fuente primaria (índice oficial de
-- circulares SII 2025 + texto de la Circular 31/2025).
--
-- POR QUÉ UNA VERSIÓN NUEVA Y NO UN UPDATE
-- Las migraciones 20260506120000 y 20260514120000 ya están aplicadas y son
-- inmutables. Y `fuente_legal` es parte del contenido firmable de una regla:
-- cambiarlo in situ reescribiría la historia y rompería la reproducibilidad de
-- los snapshots ya persistidos (`rules_snapshot_hash`). El mecanismo correcto
-- de la skill 11 es **publicar una versión nueva y deprecar la anterior**.
--
-- Se publica v3 = mismos 16 items de la v2 (sin cambios de contenido) con la
-- `fuente_legal` corregida. NO se agrega ninguna palanca nueva: este cambio es
-- exclusivamente de cita legal.
--
-- ⚠️ La v3 queda con FIRMA PLACEHOLDER (c001/a001), igual que la v2 que
--    reemplaza. No introduce ni relaja ningún gate: la v2 ya corría con firma
--    placeholder. Cuando el CONTADOR_SOCIO firme de verdad, publica v4 con
--    `docs/firma-contador-2026-05/06_whitelist_palancas_v2.sql` (ya actualizado
--    a la 31/2025 y renumerado).
-- =============================================================================

begin;

-- 1) Deprecar TODA versión previa (v1 y v2). `resolve_rule` filtra
--    status='published', así que salen de circulación al instante, sin tocar
--    vigencias (que podrían violar el CHECK vigencia_hasta > vigencia_desde).
--
--    Ojo con la v1: su `vigencia_hasta` (2026-05-13) ya la sacaba de los AT
--    recientes, pero seguía siendo resoluble para AT 2024-2025 — y llevaba la
--    misma cita derogada. La v3 cubre desde 2024-01-01, así que la reemplaza en
--    todo su rango. Dejarla publicada sería dejar el bug vivo para los años
--    viejos.
update tax_rules.rule_sets
   set status = 'deprecated'
 where domain = 'recomendacion_whitelist'
   and key = 'global'
   and version in (1, 2)
   and status = 'published';

-- 2) Publicar la v3 con la cita corregida.
with new_rule as (
    insert into tax_rules.rule_sets
        (domain, key, version, vigencia_desde, vigencia_hasta,
         rules, fuente_legal,
         status, published_by_contador, published_by_admin, published_at)
    values (
        'recomendacion_whitelist',
        'global',
        3,
        '2024-01-01',
        null,
        cast($rules${"items": [
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
             "fundamento": "art. 31 N°7 LIR; art. 10 Ley 19.885"},
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
        ]}$rules$ as jsonb),
        -- 🔧 LA CORRECCIÓN: 65/2015 → 31/2025, y se explicitan 4 ter / 4 quáter.
        cast($src$[
            {"tipo": "decreto", "id": "830", "articulo": "art. 4 bis"},
            {"tipo": "decreto", "id": "830", "articulo": "art. 4 ter"},
            {"tipo": "decreto", "id": "830", "articulo": "art. 4 quáter"},
            {"tipo": "decreto", "id": "830", "articulo": "art. 100 bis"},
            {"tipo": "circular_sii", "id": "31/2025"}
        ]$src$ as jsonb),
        'published',
        '00000000-0000-0000-0000-00000000c001',
        '00000000-0000-0000-0000-00000000a001',
        now()
    )
    returning id
)
, deps as (
    insert into tax_rules.legal_dependencies
        (rule_set_id, fuente_tipo, fuente_id, articulo)
    select id, 'decreto', '830', 'art. 4 bis'   from new_rule
    union all select id, 'decreto', '830', 'art. 4 ter'    from new_rule
    union all select id, 'decreto', '830', 'art. 4 quáter' from new_rule
    union all select id, 'decreto', '830', 'art. 100 bis'  from new_rule
    union all select id, 'circular_sii', '31/2025', ''     from new_rule
    on conflict do nothing
    returning rule_set_id
)
insert into tax_rules.rule_set_changelog
    (rule_set_id, action, performed_by, comment)
select id,
       'published',
       '00000000-0000-0000-0000-00000000a001',
       'v3: corrige la cita de la NGA. La Circular SII N°65/2015 fue dejada '
       'sin efecto por la Circular SII N°31/2025 (Leyes 21.713 y 21.716). '
       'Contenido de items idéntico a la v2. Firma placeholder (sandbox). '
       'TODO-CONTADOR #31.'
  from new_rule;

commit;
