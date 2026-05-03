-- =============================================================================
-- Migration: 20260506120000_track_1_2_legal_seeds
-- Skills:    tax-compliance-guardrails (skill 1), disclaimers-and-legal (skill 2)
-- Purpose:   Tabla `privacy.legal_texts` con textos versionados (disclaimers,
--            consentimientos, T&C, política privacidad, ribbon decisiones
--            automatizadas) más seed v1 PLACEHOLDER. También seedea la lista
--            blanca de recomendaciones lícitas como rule_set declarativo.
--            🟡 v1 placeholder pendiente firma del estudio jurídico antes
--            del go-live público.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- privacy.legal_texts — textos legales versionados, immutable-by-publication.
-- key + version es PK. Mientras `effective_to` sea NULL la versión está
-- vigente. Cambios = nueva versión, nunca edición in-place.
-- -----------------------------------------------------------------------------
create table if not exists privacy.legal_texts (
    key                 text not null,
    version             text not null,
    body                text not null,
    effective_from      date not null,
    effective_to        date,
    approved_by_legal   uuid references auth.users(id) on delete restrict,
    approved_at         timestamptz,
    created_at          timestamptz not null default now(),
    primary key (key, version),
    check (effective_to is null or effective_to > effective_from)
);

comment on table privacy.legal_texts is
    'Textos legales versionados (skill 2). Cada bloque del producto que muestra texto legal lo lee de aquí; cambios = nueva versión. PLACEHOLDER hasta firma estudio jurídico.';

create index legal_texts_effective_idx
    on privacy.legal_texts (key, effective_from desc, effective_to);

-- RLS: lectura abierta a authenticated (los textos no son confidenciales);
-- escritura solo service_role (seedeo via migraciones firmadas).
alter table privacy.legal_texts enable row level security;

create policy legal_texts_read on privacy.legal_texts
    for select to authenticated using (true);

grant select on privacy.legal_texts to authenticated;

-- -----------------------------------------------------------------------------
-- Estudio jurídico placeholder — firmante de la v1 PLACEHOLDER.
-- En producción se reemplaza por el usuario real del estudio.
-- -----------------------------------------------------------------------------
insert into auth.users (id, email)
values
    ('00000000-0000-0000-0000-00000000ec01', 'estudio-juridico@renteo.local')
on conflict (id) do nothing;

-- -----------------------------------------------------------------------------
-- Seed v1 PLACEHOLDER de los 8 bloques del skill 2.
-- -----------------------------------------------------------------------------
insert into privacy.legal_texts (
    key, version, body, effective_from, approved_by_legal, approved_at
) values
('disclaimer-recomendacion', 'v1',
 'Información general, no asesoría individualizada. Esta recomendación se basa en información tributaria general vigente y en los datos que tú o tu empresa han ingresado o autorizado a consultar. No reemplaza la asesoría personalizada de un contador o abogado tributarista. La decisión final y la responsabilidad tributaria son del contribuyente. Renteo no sugiere estructuras que puedan calificar como elusivas conforme a los artículos 4 bis, 4 ter y 4 quáter del Código Tributario.',
 '2024-01-01', '00000000-0000-0000-0000-00000000ec01', now()),

('disclaimer-simulacion', 'v1',
 'Esta simulación es una proyección. Los resultados dependen de los datos ingresados y de la normativa vigente al momento del cálculo. Cambios en la ley, oficios SII o jurisprudencia pueden alterar el resultado. Verifica con tu contador antes de tomar decisiones de cierre.',
 '2024-01-01', '00000000-0000-0000-0000-00000000ec01', now()),

('consentimiento-tratamiento-datos', 'v1',
 'Autorizo a Renteo a tratar mis datos personales y los datos tributarios de mi empresa, con la finalidad de entregarme servicios de diagnóstico tributario, simulación de escenarios y alertas. El tratamiento se rige por la Ley 19.628 y, desde el 1 de diciembre de 2026, por la Ley 21.719. Puedo ejercer mis derechos ARCOP (acceso, rectificación, cancelación, oposición y portabilidad) en mi portal de privacidad. Conozco que Renteo no comparte mis datos con terceros sin mi consentimiento, salvo cuando la ley lo requiera.',
 '2024-01-01', '00000000-0000-0000-0000-00000000ec01', now()),

('consentimiento-certificado-digital', 'v1',
 'Autorizo a Renteo a usar mi certificado digital, exclusivamente para consultar mi información tributaria en el SII a través de los proveedores autorizados (SimpleAPI/BaseAPI). El certificado se almacena cifrado en infraestructura segura (AWS KMS) y nunca se comparte con terceros. Puedo revocar este permiso en cualquier momento desde la configuración de mi cuenta.',
 '2024-01-01', '00000000-0000-0000-0000-00000000ec01', now()),

('consentimiento-mandato-digital', 'v1',
 'Reconozco actuar como Mandatario Digital del contribuyente, con autorización expresa registrada en el SII para los trámites detallados. Como contador colegiado/profesional asumo la responsabilidad profesional frente al contribuyente y al SII. Renteo es una herramienta de apoyo y no asume responsabilidad por las decisiones tributarias que yo, como profesional, tome con mis clientes.',
 '2024-01-01', '00000000-0000-0000-0000-00000000ec01', now()),

('terminos-servicio', 'v1',
 'Términos de servicio versión preliminar. Renteo entrega información y simulación tributaria, no asesoría individualizada. Las decisiones tributarias y la responsabilidad asociada son del contribuyente. El servicio se rige por la legislación chilena; las controversias se intentan resolver mediante mediación previa y, subsidiariamente, por los tribunales ordinarios de Santiago de Chile. Versión final pendiente firma del estudio jurídico antes del go-live público.',
 '2024-01-01', '00000000-0000-0000-0000-00000000ec01', now()),

('politica-privacidad', 'v1',
 'Política de privacidad versión preliminar. Renteo trata datos personales y tributarios bajo Ley 19.628 y Ley 21.719 (vigente desde 1-dic-2026). Bases de licitud: contrato, consentimiento expreso (sincronización SII) y obligaciones legales. Encargados: Supabase, AWS, proveedores SII autorizados, Sentry. Plazos de retención según art. 17 CT. Derechos ARCOP via portal de privacidad. Notificación de brechas a la Agencia de Protección de Datos en 72 horas. Versión final pendiente firma del estudio jurídico.',
 '2024-01-01', '00000000-0000-0000-0000-00000000ec01', now()),

('ribbon-decisiones-automatizadas', 'v1',
 'Esta recomendación incorpora elementos de tratamiento automatizado. Tienes derecho a solicitar revisión humana antes de tomar la decisión final.',
 '2024-01-01', '00000000-0000-0000-0000-00000000ec01', now())
on conflict (key, version) do nothing;


-- -----------------------------------------------------------------------------
-- Lista blanca de recomendaciones (skill 1, items 1-12) como rule_set
-- declarativo. El motor consulta esta lista antes de aceptar una palanca o
-- emitir una recomendación de cambio de régimen. Reusamos el patrón de
-- track 11: rule_set + golden cases + doble firma.
-- -----------------------------------------------------------------------------
insert into tax_rules.rule_sets
    (id, domain, key, version, vigencia_desde, vigencia_hasta,
     rules, fuente_legal,
     status, published_by_contador, published_by_admin, published_at)
values
('00000000-0000-0000-0000-00000000a1b1',
 'recomendacion_whitelist', 'global', 1,
 '2024-01-01', null,
 '{"items": [
    {"id": "cambio_regimen", "label": "Cambio de régimen tributario",
     "fundamento": "arts. 14 A, 14 D LIR; Circular SII 53/2025"},
    {"id": "dep_instantanea", "label": "Depreciación instantánea",
     "fundamento": "art. 31 N°5 bis LIR; Oficio SII 715/2025"},
    {"id": "sence", "label": "Franquicia SENCE",
     "fundamento": "Ley 19.518"},
    {"id": "rebaja_14e", "label": "Rebaja RLI por reinversión",
     "fundamento": "art. 14 E LIR"},
    {"id": "postergacion_iva", "label": "Postergación IVA Pro PyME",
     "fundamento": "Ley 21.210"},
    {"id": "credito_id", "label": "Crédito I+D certificado",
     "fundamento": "Ley 20.241; Ley 21.755"},
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

-- 3 golden cases del whitelist (validate_rules.py exige mínimo 3).
insert into tax_rules.rule_golden_cases
    (rule_set_id, name, inputs, expected_output, fundamento)
values
('00000000-0000-0000-0000-00000000a1b1',
 'palanca_lista_blanca_acepta',
 '{"item_id": "dep_instantanea"}'::jsonb,
 '{"whitelisted": true}'::jsonb,
 'art. 31 N°5 bis LIR'),
('00000000-0000-0000-0000-00000000a1b1',
 'palanca_fuera_de_lista_rechaza',
 '{"item_id": "fusion_societaria_inversa"}'::jsonb,
 '{"whitelisted": false}'::jsonb,
 'art. 4 bis CT (lista negra estructural)'),
('00000000-0000-0000-0000-00000000a1b1',
 'cambio_regimen_aceptado',
 '{"item_id": "cambio_regimen"}'::jsonb,
 '{"whitelisted": true}'::jsonb,
 'art. 14 A LIR; libre elección entre regímenes vigentes')
on conflict do nothing;
