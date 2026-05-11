-- =============================================================================
-- BORRADOR firma contador socio — 06_whitelist_palancas_v2
-- Checklist §5 (REVISION_CONTADOR_SOCIO.md).
--
-- Publica `tax_rules.rule_sets` versión 2 de
-- (domain='recomendacion_whitelist', key='palancas') con doble firma.
-- Cierra v1 con vigencia_hasta = now() y abre v2 con las 12 palancas
-- P1-P12 firmadas individualmente.
--
-- 🔴 REQUISITO PREVIO: ambos UUIDs deben existir en auth.users.
--    El CHECK rule_sets_double_sig_check exige
--    published_by_contador <> published_by_admin.
--
-- ✍️ CONTADOR_SOCIO + ADMIN_TECNICO: reemplazar
--    <UUID_CONTADOR_SOCIO> y <UUID_ADMIN_TECNICO> con los UUIDs reales.
--
-- Cuando esté firmado, mover a:
--   supabase/migrations/YYYYMMDDHHMMSS_whitelist_palancas_v2_firmada.sql
-- =============================================================================

begin;

-- ─────────────────────────────────────────────────────────────────────────────
-- 1) Cerrar v1 vigente: setear vigencia_hasta = vigencia_desde de v2.
-- ─────────────────────────────────────────────────────────────────────────────

update tax_rules.rule_sets
set
    vigencia_hasta = '2026-05-18'::timestamptz,   -- ✍️ ajustar a fecha real de cutover
    status = 'deprecated'
where domain = 'recomendacion_whitelist'
  and key = 'palancas'
  and status = 'published';

-- ─────────────────────────────────────────────────────────────────────────────
-- 2) Publicar v2 con las 12 palancas P1-P12 firmadas.
--    Cada item del array "all_of.palancas" representa una palanca firmada.
-- ─────────────────────────────────────────────────────────────────────────────

with new_rule as (
    insert into tax_rules.rule_sets (
        domain, key, version,
        vigencia_desde, vigencia_hasta,
        rules, fuente_legal, status,
        published_by_contador, published_by_admin, published_at
    ) values (
        'recomendacion_whitelist',
        'palancas',
        2,
        '2026-05-18'::timestamptz,                -- ✍️ ajustar (= cierre v1)
        null,
        cast($$
            {
                "palancas": [
                    {
                        "id": "dep_instantanea",
                        "nombre": "P1 — Depreciación instantánea",
                        "regimenes_elegibles": ["14_d_3", "14_d_8"],
                        "fundamento": "art. 31 N°5 bis LIR; Oficio SII 715/2025",
                        "categoria": "economia_de_opcion"
                    },
                    {
                        "id": "sence",
                        "nombre": "P2 — Franquicia SENCE",
                        "regimenes_elegibles": ["14_a", "14_d_3", "14_d_8"],
                        "fundamento": "Ley 19.518 art. 36",
                        "categoria": "economia_de_opcion"
                    },
                    {
                        "id": "rebaja_14e",
                        "nombre": "P3 — Rebaja RLI por reinversión",
                        "regimenes_elegibles": ["14_d_3"],
                        "fundamento": "art. 14 E LIR",
                        "categoria": "economia_de_opcion"
                    },
                    {
                        "id": "retiros_adicionales",
                        "nombre": "P4 — Retiros adicionales del dueño",
                        "regimenes_elegibles": ["14_a", "14_d_3", "14_d_8"],
                        "fundamento": "arts. 14 A, 14 D LIR; Circular SII 73/2020",
                        "categoria": "economia_de_opcion"
                    },
                    {
                        "id": "sueldo_empresarial",
                        "nombre": "P5 — Sueldo empresarial al socio activo",
                        "regimenes_elegibles": ["14_a", "14_d_3", "14_d_8"],
                        "fundamento": "art. 31 N°6 inc. 3° LIR",
                        "categoria": "economia_de_opcion",
                        "depende_de_tope": "sueldo_empresarial_tope_mensual_uf"
                    },
                    {
                        "id": "credito_id",
                        "nombre": "P6 — Crédito I+D + gasto 65%",
                        "regimenes_elegibles": ["14_a", "14_d_3", "14_d_8"],
                        "fundamento": "Ley 20.241; Ley 21.755 (extensión)",
                        "categoria": "economia_de_opcion"
                    },
                    {
                        "id": "ppm_extraordinario",
                        "nombre": "P7 — PPM extraordinario",
                        "regimenes_elegibles": ["14_a", "14_d_3", "14_d_8"],
                        "fundamento": "art. 84 LIR",
                        "categoria": "economia_de_opcion"
                    },
                    {
                        "id": "postergacion_iva",
                        "nombre": "P8 — Postergación IVA Pro PyME",
                        "regimenes_elegibles": ["14_d_3", "14_d_8"],
                        "fundamento": "Ley 21.210; art. 64 N°9 CT",
                        "categoria": "economia_de_opcion"
                    },
                    {
                        "id": "apv",
                        "nombre": "P9 — APV régimen A o B",
                        "regimenes_elegibles": ["14_a", "14_d_3", "14_d_8"],
                        "fundamento": "art. 42 bis LIR; DL 3.500",
                        "categoria": "economia_de_opcion"
                    },
                    {
                        "id": "credito_reinversion",
                        "nombre": "P10 — Crédito por inversión activo fijo",
                        "regimenes_elegibles": ["14_a", "14_d_3"],
                        "fundamento": "art. 33 bis LIR",
                        "categoria": "economia_de_opcion"
                    },
                    {
                        "id": "depreciacion_acelerada",
                        "nombre": "P11 — Depreciación acelerada",
                        "regimenes_elegibles": ["14_a", "14_d_3", "14_d_8"],
                        "fundamento": "art. 31 N°5 LIR",
                        "categoria": "economia_de_opcion"
                    },
                    {
                        "id": "cambio_regimen",
                        "nombre": "P12 — Cambio de régimen tributario",
                        "regimenes_elegibles": ["14_a", "14_d_3", "14_d_8"],
                        "fundamento": "arts. 14 A, 14 D LIR",
                        "categoria": "economia_de_opcion"
                    }
                ],
                "items_complementarios": [
                    {
                        "id": "donaciones",
                        "fundamento": "Ley Valdés y leyes complementarias"
                    },
                    {
                        "id": "credito_ipe",
                        "fundamento": "arts. 41 A y 41 C LIR"
                    },
                    {
                        "id": "timing_facturacion",
                        "fundamento": "Ley IVA arts. 9 y 55"
                    }
                ]
            }
        $$ as jsonb),
        cast($$
            [
                {"tipo": "ley", "id": "21.210"},
                {"tipo": "ley", "id": "21.755"},
                {"tipo": "ley", "id": "20.241"},
                {"tipo": "ley", "id": "19.518"},
                {"tipo": "circular_sii", "id": "53/2025"},
                {"tipo": "oficio_sii", "id": "715/2025"}
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
, deps as (
    insert into tax_rules.legal_dependencies (
        rule_set_id, fuente_tipo, fuente_id, articulo
    )
    select id, 'ley', '21.210', '' from new_rule
    union all select id, 'ley', '21.755', '' from new_rule
    union all select id, 'ley', '20.241', 'art. 4°' from new_rule
    union all select id, 'ley', '19.518', 'art. 36' from new_rule
    union all select id, 'circular_sii', '53/2025', '' from new_rule
    union all select id, 'oficio_sii', '715/2025', '' from new_rule
    returning rule_set_id
)
-- 4) Goldens mínimos por palanca (≥3 casos exigidos por validate_rules.py).
--    ✍️ Acá hay 3 casos representativos. Si el contador quiere agregar
--       más por palanca específica, ampliar este bloque.
, goldens as (
    insert into tax_rules.rule_golden_cases (
        rule_set_id, name, inputs, expected_output, fundamento
    )
    select
        new_rule.id,
        'p1_dep_instantanea_no_aplica_14a',
        cast('{"palanca_id": "dep_instantanea", "regimen": "14_a"}' as jsonb),
        cast('{"elegible": false}' as jsonb),
        'P1 solo aplica a Pro PyME (14_d_3 / 14_d_8).'
    from new_rule
    union all
    select
        new_rule.id,
        'p3_rebaja_14e_solo_14d3',
        cast('{"palanca_id": "rebaja_14e", "regimen": "14_d_8"}' as jsonb),
        cast('{"elegible": false}' as jsonb),
        'P3 solo aplica a 14 D N°3.'
    from new_rule
    union all
    select
        new_rule.id,
        'p10_credito_reinversion_no_aplica_14d8',
        cast('{"palanca_id": "credito_reinversion", "regimen": "14_d_8"}' as jsonb),
        cast('{"elegible": false}' as jsonb),
        'P10 no aplica a régimen transparente (14_d_8).'
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
    'Whitelist v2 firmada: P1-P12 + 3 items complementarios. Sprint firma contador socio 2026-05.'
from new_rule;

commit;
