-- =============================================================================
-- BORRADOR firma contador socio — 06_whitelist_palancas (v3 firmada)
-- Checklist §5 (REVISION_CONTADOR_SOCIO.md).
--
-- Publica la versión 3 firmada de la lista blanca de recomendaciones bajo
-- (domain='recomendacion_whitelist', key='global') con doble firma REAL, y
-- deprecia las versiones previas (v1 a1b1 y v2 placeholder a1b2).
--
-- ⚠️ Correcciones respecto del borrador anterior (que dejaba la whitelist
--    firmada INERTE):
--    (1) key = 'global', NO 'palancas'. El motor resuelve la whitelist con
--        resolve_rule(session, 'recomendacion_whitelist', 'global', tax_year)
--        (guardrails.py:25) y el snapshot dumpea 'recomendacion_whitelist/global'
--        (snapshot.py:38). Una fila con key='palancas' nunca se consulta.
--    (2) Shape rules = {"items":[...]}, NO {"palancas":[...]}. get_whitelist_ids
--        lee rules->'items' (guardrails.py:27). Con otra clave devuelve set
--        vacío y RedFlagBlocked para toda palanca.
--    (3) version = 3, NO 2. La seed track_palancas_p7_p12 ya publicó la v2
--        placeholder bajo (recomendacion_whitelist, global, 2); reusar version
--        2 viola unique(domain,key,version).
--    (4) La v2 placeholder (a1b2) está firmada con UUIDs placeholder. Se
--        DEPRECIA acá para que resolve_rule (filtra status='published') pase a
--        usar la v3 con firmas reales.
--
-- 🔴 REQUISITO PREVIO: ambos UUIDs deben existir en auth.users.
--    El CHECK de rule_sets exige published_by_contador <> published_by_admin,
--    ambos no nulos y published_at no nulo al publicar.
--
-- ✍️ CONTADOR_SOCIO + ADMIN_TECNICO: reemplazar
--    <UUID_CONTADOR_SOCIO> y <UUID_ADMIN_TECNICO> con los UUIDs reales.
--
-- Cuando esté firmado, mover a:
--   supabase/migrations/YYYYMMDDHHMMSS_whitelist_global_v3_firmada.sql
-- =============================================================================

begin;

-- ─────────────────────────────────────────────────────────────────────────────
-- 1) Deprecar TODA versión previa publicada de la whitelist global.
--    Al pasar a 'deprecated' salen de resolve_rule / _load_rule_set_snapshot
--    (ambos filtran status='published'), sin importar fechas de vigencia.
--    Cubre v1 (a1b1) y la v2 placeholder (a1b2).
-- ─────────────────────────────────────────────────────────────────────────────

-- Solo status='deprecated': basta para sacarlas de resolve_rule /
-- _load_rule_set_snapshot (ambos filtran status='published'). NO se toca
-- vigencia_hasta: forzar una fecha fija podría violar el CHECK
-- (vigencia_hasta > vigencia_desde) si la v2 placeholder se seedeó con
-- vigencia_desde = current_date >= esa fecha. En reglas deprecadas la
-- vigencia es irrelevante (nadie las resuelve).
update tax_rules.rule_sets
set
    status = 'deprecated'
where domain = 'recomendacion_whitelist'
  and key = 'global'
  and status = 'published';

-- ─────────────────────────────────────────────────────────────────────────────
-- 2) Publicar v3 con las 12 palancas P1-P12 + 3 items complementarios firmados.
--    vigencia_desde 2024-01-01: la whitelist no es año-específica (es el set de
--    palancas lícitas bajo la NGA); v3 supersede a v1/v2 vía la deprecación de
--    arriba y gobierna todo tax_year 2024+.
-- ─────────────────────────────────────────────────────────────────────────────

with new_rule as (
    insert into tax_rules.rule_sets (
        domain, key, version,
        vigencia_desde, vigencia_hasta,
        rules, fuente_legal, status,
        published_by_contador, published_by_admin, published_at
    ) values (
        'recomendacion_whitelist',
        'global',
        3,
        date '2024-01-01',
        null,
        cast($$
            {
                "items": [
                    {"id": "cambio_regimen",
                     "label": "P12 — Cambio de régimen tributario",
                     "fundamento": "arts. 14 A, 14 D LIR; Circular SII 53/2025"},
                    {"id": "dep_instantanea",
                     "label": "P1 — Depreciación instantánea",
                     "fundamento": "art. 31 N°5 bis LIR; Oficio SII 715/2025"},
                    {"id": "depreciacion_acelerada",
                     "label": "P11 — Depreciación acelerada",
                     "fundamento": "art. 31 N°5 LIR"},
                    {"id": "sence",
                     "label": "P2 — Franquicia SENCE",
                     "fundamento": "Ley 19.518 art. 36"},
                    {"id": "rebaja_14e",
                     "label": "P3 — Rebaja RLI por reinversión",
                     "fundamento": "art. 14 E LIR"},
                    {"id": "postergacion_iva",
                     "label": "P8 — Postergación IVA Pro PyME",
                     "fundamento": "Ley 21.210; art. 64 N°9 CT"},
                    {"id": "iva_postergacion",
                     "label": "P8 — Postergación IVA Pro PyME (id alterno)",
                     "fundamento": "art. 64 N°9 CT"},
                    {"id": "credito_id",
                     "label": "P6 — Crédito I+D certificado + gasto 65%",
                     "fundamento": "Ley 20.241; Ley 21.755 (extensión)"},
                    {"id": "credito_reinversion",
                     "label": "P10 — Crédito por inversión en activo fijo",
                     "fundamento": "art. 33 bis LIR"},
                    {"id": "ppm_extraordinario",
                     "label": "P7 — PPM extraordinario",
                     "fundamento": "art. 84 LIR"},
                    {"id": "sueldo_empresarial",
                     "label": "P5 — Sueldo empresarial al socio activo",
                     "fundamento": "art. 31 N°6 inc. 3° LIR"},
                    {"id": "retiros_adicionales",
                     "label": "P4 — Retiros vs reinversión",
                     "fundamento": "arts. 14 A, 14 D LIR; Circular SII 73/2020"},
                    {"id": "apv",
                     "label": "P9 — APV régimen A o B",
                     "fundamento": "art. 42 bis LIR; DL 3.500"},
                    {"id": "donaciones",
                     "label": "Donaciones con beneficio tributario",
                     "fundamento": "Ley Valdés y leyes complementarias"},
                    {"id": "credito_ipe",
                     "label": "Crédito Impuesto Pagado Extranjero",
                     "fundamento": "arts. 41 A y 41 C LIR"},
                    {"id": "timing_facturacion",
                     "label": "Timing de facturación dentro del período",
                     "fundamento": "Ley IVA arts. 9 y 55"}
                ]
            }
        $$ as jsonb),
        cast($$
            [
                {"tipo": "ct", "articulo": "art. 4 bis"},
                {"tipo": "ct", "articulo": "art. 4 ter"},
                {"tipo": "ct", "articulo": "art. 4 quáter"},
                {"tipo": "ct", "articulo": "art. 100 bis"},
                {"tipo": "circular_sii", "id": "31/2025"}
            ]
        $$ as jsonb),
        'published',
        '<UUID_CONTADOR_SOCIO>'::uuid,   -- ✍️ reemplazar (auth.users)
        '<UUID_ADMIN_TECNICO>'::uuid,    -- ✍️ reemplazar (auth.users) — debe ser distinto
        now()
    )
    returning id
)
-- 3) Legal dependencies en formato relacional (para watchdog legislativo).
--    fuente_tipo debe estar en el dominio del CHECK de legal_dependencies
--    (ley/decreto/circular_sii/oficio_sii/resolucion_sii/jurisprudencia_tta/cs);
--    'ct' no es válido acá, va solo en el jsonb fuente_legal de arriba.
, deps as (
    insert into tax_rules.legal_dependencies (
        rule_set_id, fuente_tipo, fuente_id, articulo
    )
    select id, 'ley', '21.210', '' from new_rule
    union all select id, 'ley', '21.755', '' from new_rule
    union all select id, 'ley', '20.241', 'art. 4°' from new_rule
    union all select id, 'ley', '19.518', 'art. 36' from new_rule
    union all select id, 'circular_sii', '53/2025', '' from new_rule
    -- NGA: Circular 31/2025 (17-abr-2025), que DEJÓ SIN EFECTO la 65/2015.
    union all select id, 'circular_sii', '31/2025', '' from new_rule
    union all select id, 'oficio_sii', '715/2025', '' from new_rule
    returning rule_set_id
)
-- 4) Goldens mínimos (≥3 exigidos por validate_rules.py). Mismo shape que la
--    v2 (item_id → whitelisted), validando que las 3 palancas nuevas queden
--    autorizadas por la whitelist firmada.
, goldens as (
    insert into tax_rules.rule_golden_cases (
        rule_set_id, name, inputs, expected_output, fundamento
    )
    select
        new_rule.id,
        'p7_ppm_extraordinario_whitelisted',
        cast('{"item_id": "ppm_extraordinario"}' as jsonb),
        cast('{"whitelisted": true}' as jsonb),
        'P7 PPM extraordinario autorizado (art. 84 LIR).'
    from new_rule
    union all
    select
        new_rule.id,
        'p10_credito_reinversion_whitelisted',
        cast('{"item_id": "credito_reinversion"}' as jsonb),
        cast('{"whitelisted": true}' as jsonb),
        'P10 crédito por inversión en activo fijo autorizado (art. 33 bis LIR).'
    from new_rule
    union all
    select
        new_rule.id,
        'p11_depreciacion_acelerada_whitelisted',
        cast('{"item_id": "depreciacion_acelerada"}' as jsonb),
        cast('{"whitelisted": true}' as jsonb),
        'P11 depreciación acelerada autorizada (art. 31 N°5 LIR).'
    from new_rule
    returning id
)
-- 5) Changelog explícito.
insert into tax_rules.rule_set_changelog (
    rule_set_id, action, performed_by, comment
)
select
    new_rule.id,
    'published',
    '<UUID_ADMIN_TECNICO>'::uuid,
    'Whitelist v3 firmada (key=global, shape items): P1-P12 + 3 items complementarios. Depreca v1/v2. Sprint firma contador socio 2026-05.'
from new_rule;

commit;
