-- =============================================================================
-- Migration: 20260428120600_security_audit
-- Skills:    sii-integration (skill 4), tax-data-model (skill 6),
--            fastapi-supabase-patterns (skill 10), chilean-data-privacy (skill 5)
-- Purpose:   Certificados digitales (solo metadata + KMS ARN), mandatos
--            digitales para cliente B, log de uso del certificado y audit log
--            inmutable. El PFX y el password NUNCA se persisten — viven solo
--            en S3 cifrado (apuntado por s3_object_key) y en memoria efímera
--            durante el uso.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- security.certificados_digitales — solo metadata; jamás el binario
-- -----------------------------------------------------------------------------
create table if not exists security.certificados_digitales (
    id              uuid primary key default gen_random_uuid(),
    workspace_id    uuid not null
                    references core.workspaces(id) on delete cascade,
    empresa_id      uuid not null
                    references core.empresas(id) on delete cascade,
    rut_titular     text not null,
    kms_key_arn     text not null,
    s3_object_key   text not null,
    nombre_titular  text,
    valido_desde    date not null,
    valido_hasta    date not null,
    revocado_at     timestamptz,
    created_at      timestamptz not null default now(),
    check (valido_hasta > valido_desde)
);

comment on table security.certificados_digitales is
    'Metadatos del certificado digital. El PFX cifrado vive en S3 (s3_object_key) y la KMS key en kms_key_arn. NUNCA persistir el binario o el password en DB, logs ni env.';

create index certificados_digitales_empresa_idx
    on security.certificados_digitales (empresa_id)
    where revocado_at is null;

-- -----------------------------------------------------------------------------
-- security.mandatos_digitales — cliente B opera por mandato SII
-- -----------------------------------------------------------------------------
create table if not exists security.mandatos_digitales (
    id                  uuid primary key default gen_random_uuid(),
    workspace_id        uuid not null
                        references core.workspaces(id) on delete cascade,
    empresa_id          uuid not null
                        references core.empresas(id) on delete cascade,
    contador_user_id    uuid not null
                        references auth.users(id) on delete restrict,
    alcance             text[] not null,
    inicio              date not null,
    termino             date not null,
    revocado_at         timestamptz,
    sii_referencia      text,
    created_at          timestamptz not null default now(),
    check (termino > inicio)
);

comment on table security.mandatos_digitales is
    'Mandato digital SII para cliente B (contador). El contador opera con SU clave (Clave Tributaria o Clave Única); JAMÁS pedir credenciales del contribuyente. alcance enumera trámites autorizados (consultar_f29, declarar_f22, etc.).';

create index mandatos_digitales_empresa_idx
    on security.mandatos_digitales (empresa_id)
    where revocado_at is null;
create index mandatos_digitales_contador_idx
    on security.mandatos_digitales (contador_user_id);

-- -----------------------------------------------------------------------------
-- security.cert_usage_log — uno por uso del certificado
-- workspace_id se duplica desde el certificado para permitir RLS sin JOIN.
-- -----------------------------------------------------------------------------
create table if not exists security.cert_usage_log (
    id              uuid primary key default gen_random_uuid(),
    workspace_id    uuid not null
                    references core.workspaces(id) on delete cascade,
    certificado_id  uuid not null
                    references security.certificados_digitales(id)
                    on delete cascade,
    user_id         uuid not null references auth.users(id) on delete restrict,
    proposito       text not null,
    resultado       text not null
                    check (resultado in (
                        'success', 'auth_failed', 'sii_down',
                        'rate_limited', 'data_not_found',
                        'malformed_response', 'other'
                    )),
    at              timestamptz not null default now()
);

comment on table security.cert_usage_log is
    'Auditoría de uso del certificado digital. resultado mapea a la clasificación de errores SII de skill 4.';

create index cert_usage_log_cert_at_idx
    on security.cert_usage_log (certificado_id, at desc);

-- -----------------------------------------------------------------------------
-- security.audit_log — append-only
-- -----------------------------------------------------------------------------
create table if not exists security.audit_log (
    id              uuid primary key default gen_random_uuid(),
    workspace_id    uuid not null
                    references core.workspaces(id) on delete cascade,
    empresa_id      uuid references core.empresas(id) on delete cascade,
    user_id         uuid references auth.users(id) on delete set null,
    action          text not null,
    resource_type   text not null,
    resource_id     uuid,
    metadata        jsonb not null default '{}'::jsonb,
    at              timestamptz not null default now()
);

comment on table security.audit_log is
    'Audit log inmutable de accesos a datos tributarios (reserva tributaria art. 35 CT). Append-only por trigger; UPDATE/DELETE/TRUNCATE rechazados.';
comment on column security.audit_log.metadata is
    'Metadatos sin PII (RUTs enmascarados, sin claves, sin payloads SII completos).';

create index audit_log_workspace_at_idx
    on security.audit_log (workspace_id, at desc);
create index audit_log_user_at_idx
    on security.audit_log (user_id, at desc);

-- -----------------------------------------------------------------------------
-- Inmutabilidad del audit log: trigger que falla en UPDATE/DELETE/TRUNCATE
-- -----------------------------------------------------------------------------
create or replace function security.prevent_audit_modification()
returns trigger
language plpgsql
as $$
begin
    raise exception
        'security.audit_log es append-only; UPDATE/DELETE/TRUNCATE están prohibidos.'
        using errcode = 'check_violation';
end;
$$;
comment on function security.prevent_audit_modification() is
    'Trigger que rechaza cualquier mutación destructiva sobre security.audit_log.';

create trigger audit_log_no_update
    before update on security.audit_log
    for each row execute function security.prevent_audit_modification();

create trigger audit_log_no_delete
    before delete on security.audit_log
    for each row execute function security.prevent_audit_modification();

create trigger audit_log_no_truncate
    before truncate on security.audit_log
    for each statement execute function security.prevent_audit_modification();
