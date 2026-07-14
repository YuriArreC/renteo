-- =============================================================================
-- Demo cerrado en producción: tenant ficticio + banner "motor no validado"
--
-- Skills: disclaimers-and-legal (2), chilean-data-privacy (5), tax-data-model (6).
--
-- CONTEXTO
-- Renteo sale a producción como DEMO CERRADO: infraestructura real, pero el
-- único usuario es ficticio y el signup público está cerrado. El motor
-- tributario TODAVÍA NO está validado por el CONTADOR_SOCIO (firma diferida
-- hasta el primer cliente), y esa es exactamente la razón del encierro:
--
--   El art. 100 bis CT (texto vigente, Leyes 21.713 y 21.755) sanciona a quien
--   DISEÑA O PLANIFICA con 100-250 UTA, y la exención del art. 14 letra D
--   ampara al CONTRIBUYENTE, no al ASESOR. Renteo, al recomendar, actúa como
--   diseñador. Con un contribuyente ficticio no hay exposición: nadie real
--   actúa sobre la recomendación. Con signup abierto, sí la habría.
--
-- Defensa en profundidad (tres capas, ninguna suficiente sola):
--   1. Supabase: `enable_signup = false` (supabase/config.toml + dashboard).
--   2. API: allowlist `ALLOWED_USER_EMAILS`, aplicada en `verify_jwt`.
--   3. UI: banner permanente de demo + banner "motor no validado por contador".
--
-- 🔑 CONTRASEÑA: esta migración NO setea password (no se commitean credenciales).
--    El usuario queda creado y confirmado, pero SIN poder loguearse hasta correr:
--        python scripts/set_demo_password.py
--    que la setea vía Admin API de Supabase leyendo DEMO_USER_PASSWORD del env.
--    Ver docs/DEMO-PROD.md.
-- =============================================================================

begin;

-- -----------------------------------------------------------------------------
-- 1) Usuario ficticio.
--    UUID fijo para idempotencia. `email_confirmed_at` seteado para saltar el
--    doble opt-in (no hay casilla real que confirmar). Sin `encrypted_password`:
--    la setea el script de deploy.
-- -----------------------------------------------------------------------------
insert into auth.users (
    id, instance_id, aud, role, email, email_confirmed_at,
    raw_app_meta_data, raw_user_meta_data, created_at, updated_at
) values (
    '00000000-0000-0000-0000-00000000de01',
    '00000000-0000-0000-0000-000000000000',
    'authenticated',
    'authenticated',
    'demo@renteo.cl',
    now(),
    '{"provider": "email", "providers": ["email"]}'::jsonb,
    '{"demo": true}'::jsonb,
    now(),
    now()
)
on conflict (id) do nothing;

-- -----------------------------------------------------------------------------
-- 2) Workspace del demo (cliente A: PYME).
-- -----------------------------------------------------------------------------
insert into core.workspaces (id, name, type, billing_plan)
values (
    '00000000-0000-0000-0000-00000000de02',
    'Demo Renteo (datos ficticios)',
    'pyme',
    'free'
)
on conflict (id) do nothing;

-- -----------------------------------------------------------------------------
-- 3) Membresía.
--    ⚠️ `accepted_at` NO puede quedar NULL: el custom_access_token_hook solo
--    emite claims de tenancy para membresías ACEPTADAS. Con NULL, el usuario
--    loguea pero recibe 403 "missing tenancy claims" en toda la app.
-- -----------------------------------------------------------------------------
insert into core.workspace_members
    (workspace_id, user_id, role, invited_at, accepted_at)
values (
    '00000000-0000-0000-0000-00000000de02',
    '00000000-0000-0000-0000-00000000de01',
    'owner',
    now(),
    now()
)
on conflict (workspace_id, user_id) do nothing;

-- -----------------------------------------------------------------------------
-- 4) Empresa ficticia.
--    Ferretería PYME en 14 D N°3 — el mismo perfil del caso de estudio 01, así
--    que el demo recorre el camino que ya tiene golden tests.
--    RUT ficticio, válido según el regex de core.empresas (^[0-9]{1,8}-[0-9Kk]$).
-- -----------------------------------------------------------------------------
insert into core.empresas (
    id, workspace_id, rut, razon_social, giro,
    regimen_actual, fecha_inicio_actividades, capital_inicial_uf,
    es_grupo_empresarial
) values (
    '00000000-0000-0000-0000-00000000de03',
    '00000000-0000-0000-0000-00000000de02',
    '76543210-5',
    'Ferretería Demo SpA (ficticia)',
    'Venta al por menor de artículos de ferretería',
    '14_d_3',
    '2021-03-01',
    2000.0000,
    false
)
on conflict (workspace_id, rut) do nothing;

-- -----------------------------------------------------------------------------
-- 5) Consentimiento de tratamiento de datos.
--    Lo inserta POST /api/workspaces en el flujo real; acá se replica para que
--    el tenant demo quede en el mismo estado que uno creado por la app y el
--    portal de privacidad (ARCOP) no muestre un hueco.
-- -----------------------------------------------------------------------------
insert into privacy.consentimientos
    (user_id, workspace_id, tipo_consentimiento, version_texto)
values (
    '00000000-0000-0000-0000-00000000de01',
    '00000000-0000-0000-0000-00000000de02',
    'tratamiento_datos',
    'consentimiento-tratamiento-datos-v1'
)
on conflict do nothing;

-- -----------------------------------------------------------------------------
-- 6) Banner "motor no validado por contador socio".
--
--    Texto legal versionado (skill 2): la UI NO puede inventar copy legal, así
--    que el banner vive acá y el front lo lee por /api/legal/<key>, igual que el
--    ribbon de decisiones automatizadas.
--
--    `approved_by_legal` queda NULL a propósito: ningún abogado lo firmó. Es una
--    constatación de hecho sobre el estado del motor, no un texto legal
--    negociado. Cuando el CONTADOR_SOCIO firme las reglas, este banner se retira
--    publicando una v2 con `effective_to` en la v1.
-- -----------------------------------------------------------------------------
insert into privacy.legal_texts (key, version, body, effective_from)
values (
    'banner-motor-no-validado',
    'v1',
    'Versión de demostración. Los cálculos y recomendaciones que ves provienen '
    'de un motor tributario cuyas reglas y parámetros AÚN NO han sido validados '
    'ni firmados por un contador socio. Los datos de esta cuenta son ficticios. '
    'No uses estos resultados para tomar decisiones tributarias reales ni para '
    'presentar declaraciones ante el SII.',
    '2024-01-01'
)
on conflict (key, version) do nothing;

commit;
