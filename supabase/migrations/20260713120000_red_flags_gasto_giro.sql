-- =============================================================================
-- red_flags del optimizador "gasto asociado al giro" (art. 31 LIR)
--
-- Skills:   tax-compliance-guardrails (1), tax-rules-versioning (11).
-- Diseño:   docs/optimizadores/01-gasto-del-giro.md §1.6, §1.7 y §3.4.
-- Dominio:  red_flag (ya definido en 20260428120800_tax_rules.sql y con JSON
--           Schema en rule_schemas/red_flag.schema.json — hasta ahora sin
--           ninguna regla publicada).
--
-- Publica 13 banderas, UNA POR KEY, sobre el gasto candidato:
--   6 de bloqueo (severidad='block')
--   7 de aviso   (severidad='warn')
--
-- ⚠️ ESTA MIGRACIÓN SOLO PUEDE BLOQUEAR O ADVERTIR. No habilita ninguna
--    recomendación, no agrega palancas a `recomendacion_whitelist` y no
--    cuantifica ningún tope. Su único modo de falla es ser DEMASIADO
--    conservadora — la dirección segura. Por eso se publica en sandbox antes
--    de la firma: un guardrail de más no puede producir una recomendación
--    incorrecta; su ausencia sí.
--
-- ✍️ FIRMA PLACEHOLDER (c001 / a001), igual que el resto del sandbox
--    (track_11, track_palancas_p7_p12). El CONTADOR_SOCIO debe re-publicar con
--    UUIDs reales antes de exponer el optimizador a un usuario. El CONTENIDO
--    de las banderas sí está verificado contra fuente primaria (BCN/Ley Chile
--    + circulares SII) — ver el doc de diseño §1.6-§1.7.
--
-- 🚫 Deliberadamente NO se seedea:
--    - Ningún umbral de gastos en supermercados: fue DEROGADO por la Ley
--      21.210 (la obligación de informar al SII dejó de aplicar el 1-ene-2020).
--      Si alguna vez aparece un tope de supermercados en tax_params, es un bug.
--    - El tope del art. 31 N°12 (pagos al exterior) ni los topes de donaciones
--      del art. 31 N°7 / Ley 19.885: son NÚMEROS y requieren firma
--      (TODO-CONTADOR #32). Las banderas los mencionan y derivan al contador,
--      pero el motor no los cuantifica.
--
-- Vigencia: 2020-01-01 — el art. 31 en su redacción de la Ley 21.210 rige desde el
-- 1-ene-2020 y la Ley 21.713 NO lo modificó (verificado: el bloque del art. 31
-- en el DL 824 consolidado conserva fechaVersion 2020-02-24).
-- =============================================================================

begin;

-- ── gasto_personal  [block] ───────────────────────────────────────────────
insert into tax_rules.rule_sets
    (domain, key, version, vigencia_desde, vigencia_hasta,
     rules, fuente_legal,
     status, published_by_contador, published_by_admin, published_at)
values (
    'red_flag',
    'gasto_personal',
    1,
    '2020-01-01',
    null,
    cast($rule${
        "id": "gasto_personal",
        "severidad": "block",
        "condicion": {
                "field": "es_personal",
                "op": "eq",
                "value": true
        },
        "mensaje": "El gasto está marcado como personal: no tiene nexo con el giro y no es deducible. Si además beneficia a un propietario o a un relacionado, puede quedar afecto al impuesto único del art. 21 LIR.",
        "fundamento": "art. 31 inc. 1° LIR; art. 21 LIR; Circular SII N°53 de 2020"
}$rule$ as jsonb),
    cast($src$[{"tipo": "ley", "id": "21.210", "articulo": "art. 31 inc. 1°"}, {"tipo": "circular_sii", "id": "53/2020", "articulo": ""}]$src$ as jsonb),
    'published',
    '00000000-0000-0000-0000-00000000c001',
    '00000000-0000-0000-0000-00000000a001',
    now()
)
on conflict (domain, key, version) do nothing;
-- ── sin_nexo_giro  [block] ───────────────────────────────────────────────
insert into tax_rules.rule_sets
    (domain, key, version, vigencia_desde, vigencia_hasta,
     rules, fuente_legal,
     status, published_by_contador, published_by_admin, published_at)
values (
    'red_flag',
    'sin_nexo_giro',
    1,
    '2020-01-01',
    null,
    cast($rule${
        "id": "sin_nexo_giro",
        "severidad": "block",
        "condicion": {
                "field": "nexo_giro_declarado",
                "op": "eq",
                "value": false
        },
        "mensaje": "No se declaró nexo con el giro. El art. 31 exige que el gasto tenga aptitud de generar renta y esté asociado al interés, desarrollo o mantención del giro del negocio.",
        "fundamento": "art. 31 inc. 1° LIR; Circular SII N°53 de 2020"
}$rule$ as jsonb),
    cast($src$[{"tipo": "ley", "id": "21.210", "articulo": "art. 31 inc. 1°"}, {"tipo": "circular_sii", "id": "53/2020", "articulo": ""}]$src$ as jsonb),
    'published',
    '00000000-0000-0000-0000-00000000c001',
    '00000000-0000-0000-0000-00000000a001',
    now()
)
on conflict (domain, key, version) do nothing;
-- ── vehiculo_automovil_fuera_de_giro  [block] ───────────────────────────────────────────────
insert into tax_rules.rule_sets
    (domain, key, version, vigencia_desde, vigencia_hasta,
     rules, fuente_legal,
     status, published_by_contador, published_by_admin, published_at)
values (
    'red_flag',
    'vehiculo_automovil_fuera_de_giro',
    1,
    '2020-01-01',
    null,
    cast($rule${
        "id": "vehiculo_automovil_fuera_de_giro",
        "severidad": "block",
        "condicion": {
                "all_of": [
                        {
                                "field": "es_vehiculo_automovil",
                                "op": "eq",
                                "value": true
                        },
                        {
                                "field": "giro_habitual_vehiculos",
                                "op": "eq",
                                "value": false
                        },
                        {
                                "field": "tiene_resolucion_director",
                                "op": "eq",
                                "value": false
                        }
                ]
        },
        "mensaje": "Automóviles, station wagons y similares: no son deducibles su adquisición ni su arrendamiento, ni el combustible, lubricantes, reparaciones, seguros y demás gastos de mantención y funcionamiento, cuando ese no es el giro habitual. El LEASING no es una excepción: la prohibición lo incluye expresamente. La única salida es una resolución fundada del Director del SII.",
        "fundamento": "art. 31 inc. 1° LIR; Circular SII N°53 de 2020"
}$rule$ as jsonb),
    cast($src$[{"tipo": "ley", "id": "21.210", "articulo": "art. 31 inc. 1°"}, {"tipo": "circular_sii", "id": "53/2020", "articulo": ""}]$src$ as jsonb),
    'published',
    '00000000-0000-0000-0000-00000000c001',
    '00000000-0000-0000-0000-00000000a001',
    now()
)
on conflict (domain, key, version) do nothing;
-- ── transaccion_o_clausula_penal_con_relacionado  [block] ───────────────────────────────────────────────
insert into tax_rules.rule_sets
    (domain, key, version, vigencia_desde, vigencia_hasta,
     rules, fuente_legal,
     status, published_by_contador, published_by_admin, published_at)
values (
    'red_flag',
    'transaccion_o_clausula_penal_con_relacionado',
    1,
    '2020-01-01',
    null,
    cast($rule${
        "id": "transaccion_o_clausula_penal_con_relacionado",
        "severidad": "block",
        "condicion": {
                "all_of": [
                        {
                                "field": "tipo_desembolso",
                                "op": "in",
                                "value": [
                                        "transaccion",
                                        "clausula_penal"
                                ]
                        },
                        {
                                "field": "contraparte_relacionada",
                                "op": "eq",
                                "value": true
                        }
                ]
        },
        "mensaje": "Los desembolsos que tienen como causa el cumplimiento de una transacción (judicial o extrajudicial) o de una cláusula penal solo constituyen gasto cuando se acuerdan entre partes NO relacionadas. Entre relacionados no son gasto.",
        "fundamento": "art. 31 inciso final LIR"
}$rule$ as jsonb),
    cast($src$[{"tipo": "ley", "id": "21.210", "articulo": "art. 31 inciso final"}]$src$ as jsonb),
    'published',
    '00000000-0000-0000-0000-00000000c001',
    '00000000-0000-0000-0000-00000000a001',
    now()
)
on conflict (domain, key, version) do nothing;
-- ── pago_exterior_art59_relacionado_sin_impuesto_adicional  [block] ───────────────────────────────────────────────
insert into tax_rules.rule_sets
    (domain, key, version, vigencia_desde, vigencia_hasta,
     rules, fuente_legal,
     status, published_by_contador, published_by_admin, published_at)
values (
    'red_flag',
    'pago_exterior_art59_relacionado_sin_impuesto_adicional',
    1,
    '2020-01-01',
    null,
    cast($rule${
        "id": "pago_exterior_art59_relacionado_sin_impuesto_adicional",
        "severidad": "block",
        "condicion": {
                "all_of": [
                        {
                                "field": "tipo_desembolso",
                                "op": "eq",
                                "value": "pago_exterior_art59"
                        },
                        {
                                "field": "contraparte_relacionada",
                                "op": "eq",
                                "value": true
                        },
                        {
                                "field": "ia_declarado_y_pagado",
                                "op": "eq",
                                "value": false
                        },
                        {
                                "field": "exento_o_no_gravado_ia",
                                "op": "eq",
                                "value": false
                        }
                ]
        },
        "mensaje": "Cantidades del art. 59 pagadas a una parte relacionada: para deducirlas se requiere haber declarado y pagado el Impuesto Adicional respectivo, salvo que estén exentas o no gravadas por ley o por un convenio para evitar la doble tributación. Además, se deducen solo en el año de su pago, abono en cuenta o puesta a disposición.",
        "fundamento": "art. 31 inc. 3° LIR; art. 41 E LIR"
}$rule$ as jsonb),
    cast($src$[{"tipo": "ley", "id": "21.210", "articulo": "art. 31 inc. 3°"}]$src$ as jsonb),
    'published',
    '00000000-0000-0000-0000-00000000c001',
    '00000000-0000-0000-0000-00000000a001',
    now()
)
on conflict (domain, key, version) do nothing;
-- ── fraccionamiento_para_eludir_umbral  [block] ───────────────────────────────────────────────
insert into tax_rules.rule_sets
    (domain, key, version, vigencia_desde, vigencia_hasta,
     rules, fuente_legal,
     status, published_by_contador, published_by_admin, published_at)
values (
    'red_flag',
    'fraccionamiento_para_eludir_umbral',
    1,
    '2020-01-01',
    null,
    cast($rule${
        "id": "fraccionamiento_para_eludir_umbral",
        "severidad": "block",
        "condicion": {
                "field": "fraccionado_para_umbral",
                "op": "eq",
                "value": true
        },
        "mensaje": "Fraccionar un gasto para caer bajo un umbral es una conducta de la lista negra: no se sugiere ni se simula. Nota: el antiguo umbral de gastos en supermercados fue DEROGADO por la Ley 21.210, de modo que no existe umbral alguno que evitar.",
        "fundamento": "arts. 4 bis y 4 ter CT; Circular SII N°31 de 2025"
}$rule$ as jsonb),
    cast($src$[{"tipo": "decreto", "id": "830", "articulo": "art. 4 bis"}, {"tipo": "decreto", "id": "830", "articulo": "art. 4 ter"}, {"tipo": "circular_sii", "id": "31/2025", "articulo": ""}]$src$ as jsonb),
    'published',
    '00000000-0000-0000-0000-00000000c001',
    '00000000-0000-0000-0000-00000000a001',
    now()
)
on conflict (domain, key, version) do nothing;
-- ── sin_documento_tributario  [warn] ───────────────────────────────────────────────
insert into tax_rules.rule_sets
    (domain, key, version, vigencia_desde, vigencia_hasta,
     rules, fuente_legal,
     status, published_by_contador, published_by_admin, published_at)
values (
    'red_flag',
    'sin_documento_tributario',
    1,
    '2020-01-01',
    null,
    cast($rule${
        "id": "sin_documento_tributario",
        "severidad": "warn",
        "condicion": {
                "field": "tiene_documento_tributario",
                "op": "eq",
                "value": false
        },
        "mensaje": "Falta el documento tributario a nombre de la empresa. El gasto queda PENDIENTE de documentación, no deducible: sin acreditación fehaciente no hay gasto en renta ni crédito fiscal IVA.",
        "fundamento": "art. 31 inc. 1° LIR; art. 21 CT; art. 23 N°1 y N°5 DL 825"
}$rule$ as jsonb),
    cast($src$[{"tipo": "ley", "id": "21.210", "articulo": "art. 31 inc. 1°"}, {"tipo": "decreto", "id": "830", "articulo": "art. 21"}, {"tipo": "decreto", "id": "825", "articulo": "art. 23"}]$src$ as jsonb),
    'published',
    '00000000-0000-0000-0000-00000000c001',
    '00000000-0000-0000-0000-00000000a001',
    now()
)
on conflict (domain, key, version) do nothing;
-- ── gasto_extranjero_documento_incompleto  [warn] ───────────────────────────────────────────────
insert into tax_rules.rule_sets
    (domain, key, version, vigencia_desde, vigencia_hasta,
     rules, fuente_legal,
     status, published_by_contador, published_by_admin, published_at)
values (
    'red_flag',
    'gasto_extranjero_documento_incompleto',
    1,
    '2020-01-01',
    null,
    cast($rule${
        "id": "gasto_extranjero_documento_incompleto",
        "severidad": "warn",
        "condicion": {
                "all_of": [
                        {
                                "field": "es_gasto_extranjero",
                                "op": "eq",
                                "value": true
                        },
                        {
                                "field": "doc_extranjero_datos_completos",
                                "op": "eq",
                                "value": false
                        }
                ]
        },
        "mensaje": "Gasto en el extranjero sin los datos mínimos del documento: individualización y domicilio del prestador o vendedor, naturaleza u objeto de la operación, monto y fecha. Sin ellos, la aceptación queda a criterio de la Dirección Regional: es discrecional, no un derecho. Deriva al contador.",
        "fundamento": "art. 31 inc. 2° LIR; Circular SII N°53 de 2020"
}$rule$ as jsonb),
    cast($src$[{"tipo": "ley", "id": "21.210", "articulo": "art. 31 inc. 2°"}, {"tipo": "circular_sii", "id": "53/2020", "articulo": ""}]$src$ as jsonb),
    'published',
    '00000000-0000-0000-0000-00000000c001',
    '00000000-0000-0000-0000-00000000a001',
    now()
)
on conflict (domain, key, version) do nothing;
-- ── pago_exterior_art59_relacionado_tope  [warn] ───────────────────────────────────────────────
insert into tax_rules.rule_sets
    (domain, key, version, vigencia_desde, vigencia_hasta,
     rules, fuente_legal,
     status, published_by_contador, published_by_admin, published_at)
values (
    'red_flag',
    'pago_exterior_art59_relacionado_tope',
    1,
    '2020-01-01',
    null,
    cast($rule${
        "id": "pago_exterior_art59_relacionado_tope",
        "severidad": "warn",
        "condicion": {
                "all_of": [
                        {
                                "field": "tipo_desembolso",
                                "op": "eq",
                                "value": "pago_exterior_art59"
                        },
                        {
                                "field": "contraparte_relacionada",
                                "op": "eq",
                                "value": true
                        }
                ]
        },
        "mensaje": "Pagos al exterior del art. 59 inc. 1° con parte relacionada: la deducción tiene un tope legal calculado sobre los ingresos por ventas o servicios del giro del ejercicio. El tope aún no está firmado por el contador socio, de modo que el motor NO lo cuantifica. Deriva al contador.",
        "fundamento": "art. 31 N°12 LIR"
}$rule$ as jsonb),
    cast($src$[{"tipo": "ley", "id": "21.210", "articulo": "art. 31 N°12"}]$src$ as jsonb),
    'published',
    '00000000-0000-0000-0000-00000000c001',
    '00000000-0000-0000-0000-00000000a001',
    now()
)
on conflict (domain, key, version) do nothing;
-- ── credito_incobrable_con_relacionado  [warn] ───────────────────────────────────────────────
insert into tax_rules.rule_sets
    (domain, key, version, vigencia_desde, vigencia_hasta,
     rules, fuente_legal,
     status, published_by_contador, published_by_admin, published_at)
values (
    'red_flag',
    'credito_incobrable_con_relacionado',
    1,
    '2020-01-01',
    null,
    cast($rule${
        "id": "credito_incobrable_con_relacionado",
        "severidad": "warn",
        "condicion": {
                "all_of": [
                        {
                                "field": "tipo_desembolso",
                                "op": "eq",
                                "value": "credito_incobrable"
                        },
                        {
                                "field": "contraparte_relacionada",
                                "op": "eq",
                                "value": true
                        }
                ]
        },
        "mensaje": "Castigo de créditos incobrables entre empresas relacionadas: no procede la regla general de deducción, salvo que se trate de sociedades de apoyo al giro. Deriva al contador.",
        "fundamento": "art. 31 N°4 LIR; art. 8 N°17 CT"
}$rule$ as jsonb),
    cast($src$[{"tipo": "ley", "id": "21.210", "articulo": "art. 31 N°4"}, {"tipo": "decreto", "id": "830", "articulo": "art. 8 N°17"}]$src$ as jsonb),
    'published',
    '00000000-0000-0000-0000-00000000c001',
    '00000000-0000-0000-0000-00000000a001',
    now()
)
on conflict (domain, key, version) do nothing;
-- ── compra_en_supermercado_caso_a_caso  [warn] ───────────────────────────────────────────────
insert into tax_rules.rule_sets
    (domain, key, version, vigencia_desde, vigencia_hasta,
     rules, fuente_legal,
     status, published_by_contador, published_by_admin, published_at)
values (
    'red_flag',
    'compra_en_supermercado_caso_a_caso',
    1,
    '2020-01-01',
    null,
    cast($rule${
        "id": "compra_en_supermercado_caso_a_caso",
        "severidad": "warn",
        "condicion": {
                "field": "categoria",
                "op": "eq",
                "value": "supermercado"
        },
        "mensaje": "Compras en supermercados y comercios similares: NO existe un umbral especial. La Ley 21.210 derogó el antiguo tope de 5 UTA anuales y la obligación de informar al SII (sin aplicación desde el 1-ene-2020). Se evalúan caso a caso bajo la regla general del inciso primero, y la probabilidad de gasto personal es alta: exige nexo explícito con el giro.",
        "fundamento": "art. 31 inc. 1° LIR; Circular SII N°53 de 2020 §2.4"
}$rule$ as jsonb),
    cast($src$[{"tipo": "ley", "id": "21.210", "articulo": "art. 31 inc. 1°"}, {"tipo": "circular_sii", "id": "53/2020", "articulo": "§2.4"}]$src$ as jsonb),
    'published',
    '00000000-0000-0000-0000-00000000c001',
    '00000000-0000-0000-0000-00000000a001',
    now()
)
on conflict (domain, key, version) do nothing;
-- ── donacion_limites_en_cascada  [warn] ───────────────────────────────────────────────
insert into tax_rules.rule_sets
    (domain, key, version, vigencia_desde, vigencia_hasta,
     rules, fuente_legal,
     status, published_by_contador, published_by_admin, published_at)
values (
    'red_flag',
    'donacion_limites_en_cascada',
    1,
    '2020-01-01',
    null,
    cast($rule${
        "id": "donacion_limites_en_cascada",
        "severidad": "warn",
        "condicion": {
                "field": "tipo_desembolso",
                "op": "eq",
                "value": "donacion"
        },
        "mensaje": "Las donaciones deducibles tienen DOS límites en cascada: el tope propio del art. 31 N°7 y, sobre el conjunto de donaciones con beneficio tributario, el límite global absoluto de la Ley 19.885. Los topes aún no están firmados por el contador socio, de modo que el motor NO los cuantifica. Deriva al contador.",
        "fundamento": "art. 31 N°7 LIR; art. 10 Ley 19.885"
}$rule$ as jsonb),
    cast($src$[{"tipo": "ley", "id": "21.210", "articulo": "art. 31 N°7"}, {"tipo": "ley", "id": "19.885", "articulo": "art. 10"}]$src$ as jsonb),
    'published',
    '00000000-0000-0000-0000-00000000c001',
    '00000000-0000-0000-0000-00000000a001',
    now()
)
on conflict (domain, key, version) do nothing;
-- ── egreso_no_pagado_en_base_caja  [warn] ───────────────────────────────────────────────
insert into tax_rules.rule_sets
    (domain, key, version, vigencia_desde, vigencia_hasta,
     rules, fuente_legal,
     status, published_by_contador, published_by_admin, published_at)
values (
    'red_flag',
    'egreso_no_pagado_en_base_caja',
    1,
    '2020-01-01',
    null,
    cast($rule${
        "id": "egreso_no_pagado_en_base_caja",
        "severidad": "warn",
        "condicion": {
                "all_of": [
                        {
                                "field": "regimen",
                                "op": "eq",
                                "value": "14_d_3"
                        },
                        {
                                "field": "pagado",
                                "op": "eq",
                                "value": false
                        }
                ]
        },
        "mensaje": "Régimen Pro PyME 14 D N°3: la base imponible se determina por caja. Un egreso solo se rebaja cuando está EFECTIVAMENTE PAGADO. Este gasto todavía no lo está, así que no se reconoce en este ejercicio.",
        "fundamento": "art. 14 D N°3 LIR; Circular SII N°62 de 2020"
}$rule$ as jsonb),
    cast($src$[{"tipo": "ley", "id": "21.210", "articulo": "art. 14 D N°3"}, {"tipo": "circular_sii", "id": "62/2020", "articulo": ""}]$src$ as jsonb),
    'published',
    '00000000-0000-0000-0000-00000000c001',
    '00000000-0000-0000-0000-00000000a001',
    now()
)
on conflict (domain, key, version) do nothing;

-- ─────────────────────────────────────────────────────────────────────────────
-- Dependencias legales en formato relacional (alimenta el watchdog, skill 11).
-- Derivadas del fuente_legal de cada bandera, sin duplicar.
-- ─────────────────────────────────────────────────────────────────────────────
insert into tax_rules.legal_dependencies
    (rule_set_id, fuente_tipo, fuente_id, articulo)
select rs.id,
       src->>'tipo',
       coalesce(src->>'id', ''),
       coalesce(src->>'articulo', '')
  from tax_rules.rule_sets rs
 cross join lateral jsonb_array_elements(rs.fuente_legal) as src
 where rs.domain = 'red_flag'
   and rs.version = 1
   and rs.key in ('gasto_personal', 'sin_nexo_giro', 'vehiculo_automovil_fuera_de_giro', 'transaccion_o_clausula_penal_con_relacionado', 'pago_exterior_art59_relacionado_sin_impuesto_adicional', 'fraccionamiento_para_eludir_umbral', 'sin_documento_tributario', 'gasto_extranjero_documento_incompleto', 'pago_exterior_art59_relacionado_tope', 'credito_incobrable_con_relacionado', 'compra_en_supermercado_caso_a_caso', 'donacion_limites_en_cascada', 'egreso_no_pagado_en_base_caja')
on conflict do nothing;

-- ─────────────────────────────────────────────────────────────────────────────
-- Changelog: deja constancia de que la firma es PLACEHOLDER.
-- ─────────────────────────────────────────────────────────────────────────────
insert into tax_rules.rule_set_changelog
    (rule_set_id, action, performed_by, comment)
select rs.id,
       'published',
       '00000000-0000-0000-0000-00000000a001',
       'Publicación inicial de red_flag/' || rs.key || ' v1 (sandbox pre-firma). '
       || 'Contenido verificado contra fuente primaria (BCN + circulares SII); '
       || 'FIRMA PLACEHOLDER: requiere re-publicación por CONTADOR_SOCIO. '
       || 'Solo bloquea/advierte: no habilita ninguna recomendación.'
  from tax_rules.rule_sets rs
 where rs.domain = 'red_flag'
   and rs.version = 1
   and rs.key in ('gasto_personal', 'sin_nexo_giro', 'vehiculo_automovil_fuera_de_giro', 'transaccion_o_clausula_penal_con_relacionado', 'pago_exterior_art59_relacionado_sin_impuesto_adicional', 'fraccionamiento_para_eludir_umbral', 'sin_documento_tributario', 'gasto_extranjero_documento_incompleto', 'pago_exterior_art59_relacionado_tope', 'credito_incobrable_con_relacionado', 'compra_en_supermercado_caso_a_caso', 'donacion_limites_en_cascada', 'egreso_no_pagado_en_base_caja')
on conflict do nothing;

commit;
