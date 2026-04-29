-- =============================================================================
-- Migration: 20260428120800_tax_rules
-- Skills:    tax-rules-versioning (skill 11)
-- Purpose:   Reglas declarativas versionadas con vigencia temporal. El motor
--            consume estas tablas; el código no contiene if/else por año.
--            Datos GLOBALES (no per-tenant); RLS (B12) habilita SELECT a
--            authenticated, mutaciones solo desde service_role vía migración.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- tax_rules.rule_sets — un set por (domain, key, version) con vigencia
-- -----------------------------------------------------------------------------
create table if not exists tax_rules.rule_sets (
    id                          uuid primary key default gen_random_uuid(),
    domain                      text not null,
    key                         text not null,
    version                     int not null check (version >= 1),
    vigencia_desde              date not null,
    vigencia_hasta              date,
    rules                       jsonb not null,
    fuente_legal                jsonb not null,
    status                      text not null default 'draft'
                                check (status in (
                                    'draft', 'pending_approval',
                                    'published', 'deprecated'
                                )),
    published_by_contador       uuid references auth.users(id) on delete restrict,
    published_by_admin          uuid references auth.users(id) on delete restrict,
    published_at                timestamptz,
    created_at                  timestamptz not null default now(),
    unique (domain, key, version),
    -- Doble firma obligatoria al publicar: ambos firmantes presentes,
    -- distintos entre sí, y published_at registrado.
    check (
        status <> 'published'
        or (
            published_by_contador is not null
            and published_by_admin is not null
            and published_by_contador <> published_by_admin
            and published_at is not null
        )
    ),
    check (
        vigencia_hasta is null
        or vigencia_hasta > vigencia_desde
    )
);

comment on table tax_rules.rule_sets is
    'Reglas declarativas con vigencia temporal. domain agrupa por dominio (regime_eligibility, palanca_definition, red_flag, rli_formula, credit_imputation_order, etc.). rules es JSON validado contra el JSON Schema del dominio (apps/api/src/domain/tax_engine/rule_schemas/).';
comment on column tax_rules.rule_sets.fuente_legal is
    'Array JSON de citas: [{tipo:"ley", id:"21.755"}, {tipo:"circular_sii", id:"53/2025"}]. No puede estar vacío al publicar.';
comment on column tax_rules.rule_sets.published_by_contador is
    'Doble firma — firma del contador socio. Debe ser distinta de published_by_admin.';
comment on column tax_rules.rule_sets.published_by_admin is
    'Doble firma — firma del admin técnico. Debe ser distinta de published_by_contador.';

create index rule_sets_domain_key_vigencia_idx
    on tax_rules.rule_sets (domain, key, vigencia_desde desc, vigencia_hasta nulls last);
create index rule_sets_status_idx
    on tax_rules.rule_sets (status);

-- -----------------------------------------------------------------------------
-- tax_rules.rule_set_changelog — auditoría de cambios sobre rule_sets
-- -----------------------------------------------------------------------------
create table if not exists tax_rules.rule_set_changelog (
    id              uuid primary key default gen_random_uuid(),
    rule_set_id     uuid not null
                    references tax_rules.rule_sets(id) on delete cascade,
    action          text not null
                    check (action in (
                        'created', 'submitted', 'approved',
                        'published', 'deprecated', 'updated'
                    )),
    diff            jsonb,
    performed_by    uuid references auth.users(id) on delete set null,
    performed_at    timestamptz not null default now(),
    comment         text
);

comment on table tax_rules.rule_set_changelog is
    'Historial de transiciones de estado y diffs de rule_sets. Se llena por la API de admin (fase 6); en fase 0-5 se llena vía migración SQL al insertar reglas.';

create index rule_set_changelog_rule_idx
    on tax_rules.rule_set_changelog (rule_set_id, performed_at desc);

-- -----------------------------------------------------------------------------
-- tax_rules.legal_dependencies — trazabilidad inversa ley → reglas afectadas
-- -----------------------------------------------------------------------------
create table if not exists tax_rules.legal_dependencies (
    rule_set_id     uuid not null
                    references tax_rules.rule_sets(id) on delete cascade,
    fuente_tipo     text not null
                    check (fuente_tipo in (
                        'ley', 'decreto',
                        'circular_sii', 'oficio_sii', 'resolucion_sii',
                        'jurisprudencia_tta', 'cs'
                    )),
    fuente_id       text not null,
    articulo        text not null default '',
    primary key (rule_set_id, fuente_tipo, fuente_id, articulo)
);

comment on table tax_rules.legal_dependencies is
    'Mapa regla→fuentes legales. Permite responder "Si publican Circular X, ¿qué reglas pueden quedar afectadas?" en menos de 1 minuto. Espejado en apps/api/legal-dependencies.yaml mantenido por contador socio.';

create index legal_dependencies_fuente_idx
    on tax_rules.legal_dependencies (fuente_tipo, fuente_id);

-- -----------------------------------------------------------------------------
-- tax_rules.feature_flags_by_year — flags condicionales con auditoría
-- -----------------------------------------------------------------------------
create table if not exists tax_rules.feature_flags_by_year (
    flag_key            text not null,
    effective_from      date not null,
    value               text not null,
    reason              text not null,
    changed_by          uuid references auth.users(id) on delete set null,
    changed_at          timestamptz not null default now(),
    primary key (flag_key, effective_from)
);

comment on table tax_rules.feature_flags_by_year is
    'Flags por tax_year para situaciones condicionales (ej. idpc_14d3_at2026_transitoria con valor transitoria_12_5 vs permanente_25). Cambia la realidad legislativa = nueva fila, no código nuevo.';

-- -----------------------------------------------------------------------------
-- tax_rules.rule_golden_cases — casos golden por regla
-- -----------------------------------------------------------------------------
create table if not exists tax_rules.rule_golden_cases (
    id                  uuid primary key default gen_random_uuid(),
    rule_set_id         uuid not null
                        references tax_rules.rule_sets(id) on delete cascade,
    name                text not null,
    inputs              jsonb not null,
    expected_output     jsonb not null,
    fundamento          text,
    created_by          uuid references auth.users(id) on delete set null,
    created_at          timestamptz not null default now()
);

comment on table tax_rules.rule_golden_cases is
    'Casos golden ejecutados al publicar una regla. Mínimo 3 por regla; si alguno falla, no se publica (validación CI fase 0E).';

create index rule_golden_cases_rule_idx
    on tax_rules.rule_golden_cases (rule_set_id);
