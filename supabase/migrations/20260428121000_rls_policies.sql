-- =============================================================================
-- Migration: 20260428121000_rls_policies
-- Skills:    tax-data-model (skill 6), fastapi-supabase-patterns (skill 10),
--            chilean-data-privacy (skill 5)
-- Purpose:   Habilitar RLS y aplicar policies en TODAS las tablas con datos
--            de usuario. Helpers de B2 (app.workspace_id, app.user_role,
--            app.has_empresa_access) hacen la heavy lifting. service_role
--            sigue bypasseando RLS para jobs internos (Celery, watchdog).
--
--            Patrón aplicado:
--            - Tablas con (workspace_id, empresa_id):
--                workspace_id = app.workspace_id()
--                AND app.has_empresa_access(empresa_id)
--            - Tablas solo con workspace_id: workspace_id = app.workspace_id()
--            - core.workspaces: id = app.workspace_id()
--            - tax_params.*, tax_rules.*: SELECT abierto a authenticated;
--              mutaciones solo desde service_role (vía migración versionada).
-- =============================================================================

-- =============================================================================
-- core
-- =============================================================================

-- core.workspaces — el usuario solo ve SU workspace activo.
alter table core.workspaces enable row level security;

create policy workspaces_self_select on core.workspaces
    for select to authenticated
    using (id = app.workspace_id());

create policy workspaces_self_update on core.workspaces
    for update to authenticated
    using (
        id = app.workspace_id()
        and app.user_role() in ('owner', 'accountant_lead')
    )
    with check (
        id = app.workspace_id()
        and app.user_role() in ('owner', 'accountant_lead')
    );

-- INSERT/DELETE de workspaces solo desde service_role (alta de tenant
-- gestionada por backend en onboarding).

-- core.workspace_members
alter table core.workspace_members enable row level security;

create policy workspace_members_select on core.workspace_members
    for select to authenticated
    using (workspace_id = app.workspace_id());

create policy workspace_members_modify on core.workspace_members
    for all to authenticated
    using (
        workspace_id = app.workspace_id()
        and app.user_role() in ('owner', 'accountant_lead')
    )
    with check (
        workspace_id = app.workspace_id()
        and app.user_role() in ('owner', 'accountant_lead')
    );

-- core.empresas
alter table core.empresas enable row level security;

create policy empresas_select on core.empresas
    for select to authenticated
    using (
        workspace_id = app.workspace_id()
        and app.has_empresa_access(id)
    );

create policy empresas_insert on core.empresas
    for insert to authenticated
    with check (
        workspace_id = app.workspace_id()
        and app.user_role() in ('owner', 'accountant_lead')
    );

create policy empresas_update on core.empresas
    for update to authenticated
    using (
        workspace_id = app.workspace_id()
        and app.has_empresa_access(id)
        and app.user_role() in ('owner', 'cfo', 'accountant_lead', 'accountant_staff')
    )
    with check (workspace_id = app.workspace_id());

create policy empresas_delete on core.empresas
    for delete to authenticated
    using (
        workspace_id = app.workspace_id()
        and app.user_role() in ('owner', 'accountant_lead')
    );

-- core.accountant_assignments — solo lead/owner del workspace lo gestiona.
alter table core.accountant_assignments enable row level security;

create policy accountant_assignments_select on core.accountant_assignments
    for select to authenticated
    using (workspace_id = app.workspace_id());

create policy accountant_assignments_modify on core.accountant_assignments
    for all to authenticated
    using (
        workspace_id = app.workspace_id()
        and app.user_role() in ('owner', 'accountant_lead')
    )
    with check (
        workspace_id = app.workspace_id()
        and app.user_role() in ('owner', 'accountant_lead')
    );

-- core.escenarios_simulacion / recomendaciones / alertas — patrón estándar.
alter table core.escenarios_simulacion enable row level security;

create policy escenarios_select on core.escenarios_simulacion
    for select to authenticated
    using (
        workspace_id = app.workspace_id()
        and app.has_empresa_access(empresa_id)
    );
create policy escenarios_insert on core.escenarios_simulacion
    for insert to authenticated
    with check (
        workspace_id = app.workspace_id()
        and app.has_empresa_access(empresa_id)
    );
create policy escenarios_update on core.escenarios_simulacion
    for update to authenticated
    using (
        workspace_id = app.workspace_id()
        and app.has_empresa_access(empresa_id)
    )
    with check (workspace_id = app.workspace_id());
create policy escenarios_delete on core.escenarios_simulacion
    for delete to authenticated
    using (
        workspace_id = app.workspace_id()
        and app.has_empresa_access(empresa_id)
    );

alter table core.recomendaciones enable row level security;

create policy recomendaciones_select on core.recomendaciones
    for select to authenticated
    using (
        workspace_id = app.workspace_id()
        and app.has_empresa_access(empresa_id)
    );
create policy recomendaciones_update on core.recomendaciones
    for update to authenticated
    using (
        workspace_id = app.workspace_id()
        and app.has_empresa_access(empresa_id)
    )
    with check (workspace_id = app.workspace_id());
-- INSERT/DELETE de recomendaciones solo desde service_role (motor backend).

alter table core.alertas enable row level security;

create policy alertas_select on core.alertas
    for select to authenticated
    using (
        workspace_id = app.workspace_id()
        and app.has_empresa_access(empresa_id)
    );
create policy alertas_update on core.alertas
    for update to authenticated
    using (
        workspace_id = app.workspace_id()
        and app.has_empresa_access(empresa_id)
    )
    with check (workspace_id = app.workspace_id());
-- INSERT/DELETE de alertas solo desde service_role (worker compute_alerts_daily).

-- =============================================================================
-- tax_data — patrón uniforme (read-only desde la UI; los workers escriben).
-- =============================================================================

alter table tax_data.dtes enable row level security;
create policy dtes_select on tax_data.dtes
    for select to authenticated
    using (
        workspace_id = app.workspace_id()
        and app.has_empresa_access(empresa_id)
    );

alter table tax_data.rcv_lines enable row level security;
create policy rcv_lines_select on tax_data.rcv_lines
    for select to authenticated
    using (
        workspace_id = app.workspace_id()
        and app.has_empresa_access(empresa_id)
    );

alter table tax_data.f29_periodos enable row level security;
create policy f29_periodos_select on tax_data.f29_periodos
    for select to authenticated
    using (
        workspace_id = app.workspace_id()
        and app.has_empresa_access(empresa_id)
    );

alter table tax_data.f22_anios enable row level security;
create policy f22_anios_select on tax_data.f22_anios
    for select to authenticated
    using (
        workspace_id = app.workspace_id()
        and app.has_empresa_access(empresa_id)
    );

alter table tax_data.boletas_honorarios enable row level security;
create policy boletas_honorarios_select on tax_data.boletas_honorarios
    for select to authenticated
    using (
        workspace_id = app.workspace_id()
        and app.has_empresa_access(empresa_id)
    );

-- =============================================================================
-- tax_calc — read-only desde UI; el motor (service_role) escribe.
-- =============================================================================

alter table tax_calc.rli_calculations enable row level security;
create policy rli_calculations_select on tax_calc.rli_calculations
    for select to authenticated
    using (
        workspace_id = app.workspace_id()
        and app.has_empresa_access(empresa_id)
    );

alter table tax_calc.registros_tributarios enable row level security;
create policy registros_tributarios_select on tax_calc.registros_tributarios
    for select to authenticated
    using (
        workspace_id = app.workspace_id()
        and app.has_empresa_access(empresa_id)
    );

alter table tax_calc.retiros_y_distribuciones enable row level security;
create policy retiros_select on tax_calc.retiros_y_distribuciones
    for select to authenticated
    using (
        workspace_id = app.workspace_id()
        and app.has_empresa_access(empresa_id)
    );
create policy retiros_modify on tax_calc.retiros_y_distribuciones
    for all to authenticated
    using (
        workspace_id = app.workspace_id()
        and app.has_empresa_access(empresa_id)
        and app.user_role() in ('owner', 'cfo', 'accountant_lead', 'accountant_staff')
    )
    with check (
        workspace_id = app.workspace_id()
        and app.has_empresa_access(empresa_id)
    );

-- =============================================================================
-- security
-- =============================================================================

-- certificados_digitales — solo metadata; subida/borrado por backend.
alter table security.certificados_digitales enable row level security;
create policy certificados_select on security.certificados_digitales
    for select to authenticated
    using (
        workspace_id = app.workspace_id()
        and app.has_empresa_access(empresa_id)
    );
-- INSERT/UPDATE/DELETE solo service_role (flujo KMS).

-- mandatos_digitales — gestión por accountant_lead (cliente B).
alter table security.mandatos_digitales enable row level security;
create policy mandatos_select on security.mandatos_digitales
    for select to authenticated
    using (
        workspace_id = app.workspace_id()
        and app.has_empresa_access(empresa_id)
    );
create policy mandatos_modify on security.mandatos_digitales
    for all to authenticated
    using (
        workspace_id = app.workspace_id()
        and app.user_role() = 'accountant_lead'
    )
    with check (
        workspace_id = app.workspace_id()
        and app.user_role() = 'accountant_lead'
    );

-- cert_usage_log — append-only de hecho (no UPDATE/DELETE permitidos).
alter table security.cert_usage_log enable row level security;
create policy cert_usage_log_select on security.cert_usage_log
    for select to authenticated
    using (
        workspace_id = app.workspace_id()
        and app.user_role() in ('owner', 'accountant_lead', 'cfo')
    );
-- INSERT solo service_role (lo escribe el adapter SII al usar el cert).

-- audit_log — lectura restringida a roles administrativos del workspace.
-- INSERT permitido a authenticated (el backend lo hace en nombre del user);
-- UPDATE/DELETE/TRUNCATE bloqueados por trigger (B8).
alter table security.audit_log enable row level security;
create policy audit_log_select on security.audit_log
    for select to authenticated
    using (
        workspace_id = app.workspace_id()
        and app.user_role() in ('owner', 'accountant_lead')
    );
create policy audit_log_insert on security.audit_log
    for insert to authenticated
    with check (workspace_id = app.workspace_id());

-- =============================================================================
-- privacy
-- =============================================================================

-- arcop_requests — el titular ve las suyas; owner/lead del workspace ve todas.
alter table privacy.arcop_requests enable row level security;
create policy arcop_select on privacy.arcop_requests
    for select to authenticated
    using (
        user_id = auth.uid()
        or (
            workspace_id = app.workspace_id()
            and app.user_role() in ('owner', 'accountant_lead')
        )
    );
create policy arcop_insert on privacy.arcop_requests
    for insert to authenticated
    with check (
        user_id = auth.uid()
        and workspace_id = app.workspace_id()
    );
create policy arcop_update on privacy.arcop_requests
    for update to authenticated
    using (
        workspace_id = app.workspace_id()
        and app.user_role() in ('owner', 'accountant_lead')
    )
    with check (workspace_id = app.workspace_id());

-- consentimientos — el usuario ve los suyos; owner/lead ve los del workspace.
alter table privacy.consentimientos enable row level security;
create policy consentimientos_select on privacy.consentimientos
    for select to authenticated
    using (
        user_id = auth.uid()
        or (
            workspace_id = app.workspace_id()
            and app.user_role() in ('owner', 'accountant_lead')
        )
    );
create policy consentimientos_insert on privacy.consentimientos
    for insert to authenticated
    with check (user_id = auth.uid());
-- UPDATE/DELETE solo service_role (revocación pasa por backend).

-- incidentes_brecha — gestión interna; ningún usuario lo ve por RLS.
-- service_role (DPO/equipo) trabaja con bypass.
alter table privacy.incidentes_brecha enable row level security;
-- intencionalmente sin policies para authenticated.

-- =============================================================================
-- tax_params — datos GLOBALES, lectura abierta a authenticated.
-- =============================================================================

alter table tax_params.tax_year_params enable row level security;
create policy tax_year_params_read on tax_params.tax_year_params
    for select to authenticated using (true);

alter table tax_params.idpc_rates enable row level security;
create policy idpc_rates_read on tax_params.idpc_rates
    for select to authenticated using (true);

alter table tax_params.igc_brackets enable row level security;
create policy igc_brackets_read on tax_params.igc_brackets
    for select to authenticated using (true);

alter table tax_params.ppm_pyme_rates enable row level security;
create policy ppm_pyme_rates_read on tax_params.ppm_pyme_rates
    for select to authenticated using (true);

alter table tax_params.beneficios_topes enable row level security;
create policy beneficios_topes_read on tax_params.beneficios_topes
    for select to authenticated using (true);

-- =============================================================================
-- tax_rules — datos GLOBALES, lectura abierta solo de reglas publicadas.
-- =============================================================================

alter table tax_rules.rule_sets enable row level security;
create policy rule_sets_read_published on tax_rules.rule_sets
    for select to authenticated using (status = 'published');

alter table tax_rules.rule_set_changelog enable row level security;
-- changelog visible solo a service_role (auditoría interna por ahora;
-- el panel admin de fase 6 expone via endpoint dedicado).

alter table tax_rules.legal_dependencies enable row level security;
create policy legal_dependencies_read on tax_rules.legal_dependencies
    for select to authenticated using (true);

alter table tax_rules.feature_flags_by_year enable row level security;
create policy feature_flags_read on tax_rules.feature_flags_by_year
    for select to authenticated using (true);

alter table tax_rules.rule_golden_cases enable row level security;
-- golden cases visibles solo a service_role (uso interno del motor).

-- =============================================================================
-- GRANTs — RLS evalúa policies solo si el role tiene GRANT base. service_role
-- bypassa RLS y mantiene full access por default; aquí explicitamos los
-- mínimos necesarios para `authenticated`.
-- =============================================================================

grant select, insert, update, delete on all tables in schema core, tax_data,
                                                       tax_calc, security,
                                                       privacy
    to authenticated;

grant select on all tables in schema tax_params, tax_rules to authenticated;

-- Para tablas que se creen en migraciones posteriores dentro de estos schemas.
alter default privileges in schema core, tax_data, tax_calc, security, privacy
    grant select, insert, update, delete on tables to authenticated;

alter default privileges in schema tax_params, tax_rules
    grant select on tables to authenticated;
