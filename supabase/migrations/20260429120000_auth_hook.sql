-- =============================================================================
-- Migration: 20260429120000_auth_hook
-- Skills:    fastapi-supabase-patterns (skill 10), tax-data-model (skill 6),
--            dual-ux-patterns (skill 9)
-- Purpose:   Custom Access Token Hook que puebla el JWT con tenancy:
--              app_metadata.workspace_id     uuid del workspace activo
--              app_metadata.workspace_type   pyme | accounting_firm
--              app_metadata.role             owner | cfo | accountant_lead |
--                                            accountant_staff | viewer
--              app_metadata.empresa_ids      uuid[] (cliente B asignaciones)
--
--            Sin este hook, `current_tenancy()` falla con 403 "missing tenancy
--            claims" porque la helper SQL `app.has_empresa_access()` y la
--            política RLS leen exclusivamente de `auth.jwt()`.
--
--            La función corre como SECURITY DEFINER con search_path vacío
--            para que `supabase_auth_admin` pueda leer `core.*` sin GRANTs
--            adicionales y sin riesgo de hijack vía search_path.
-- =============================================================================

create or replace function public.custom_access_token_hook(event jsonb)
returns jsonb
language plpgsql
stable
security definer
set search_path = ''
as $$
declare
    target_user_id uuid := (event->>'user_id')::uuid;
    claims jsonb := coalesce(event->'claims', '{}'::jsonb);
    membership record;
    empresa_ids jsonb := '[]'::jsonb;
    app_metadata jsonb;
begin
    -- Workspace activo: el miembro aceptado más reciente, sin workspace
    -- borrado. Si el usuario tiene múltiples, gana el más reciente; el
    -- selector explícito multi-workspace queda para fase 6+.
    select
        wm.workspace_id,
        wm.role,
        w.type as workspace_type
      into membership
      from core.workspace_members wm
      join core.workspaces w on w.id = wm.workspace_id
     where wm.user_id = target_user_id
       and wm.accepted_at is not null
       and w.deleted_at is null
     order by wm.invited_at desc
     limit 1;

    if membership.workspace_id is null then
        -- Sin membership activa: dejamos los claims base. El backend
        -- responderá 403 "missing tenancy claims" cuando el usuario intente
        -- llegar a una ruta autenticada.
        return jsonb_build_object('claims', claims);
    end if;

    -- Cliente B accountant_staff: poblar empresa_ids[] desde
    -- accountant_assignments. Otros roles ven todas las empresas del
    -- workspace por la helper SQL `app.has_empresa_access`, así que la
    -- lista se entrega vacía.
    if membership.role = 'accountant_staff' then
        select coalesce(jsonb_agg(empresa_id), '[]'::jsonb)
          into empresa_ids
          from core.accountant_assignments
         where workspace_id = membership.workspace_id
           and user_id = target_user_id;
    end if;

    app_metadata := jsonb_build_object(
        'workspace_id', membership.workspace_id,
        'workspace_type', membership.workspace_type,
        'role', membership.role,
        'empresa_ids', empresa_ids
    );

    -- Mergear sobre app_metadata existente (Supabase puede haber inyectado
    -- otros claims como `provider`).
    claims := jsonb_set(
        claims,
        '{app_metadata}',
        coalesce(claims->'app_metadata', '{}'::jsonb) || app_metadata
    );

    return jsonb_build_object('claims', claims);
end;
$$;

comment on function public.custom_access_token_hook(jsonb) is
    'Inyecta tenancy en el JWT al firmar/refrescar tokens. Solo supabase_auth_admin puede invocarla.';

-- Solo supabase_auth_admin puede llamar al hook. Bloqueamos a authenticated
-- y anon para evitar que usuarios finales lo invoquen directo.
revoke execute on function public.custom_access_token_hook(jsonb)
    from authenticated, anon, public;

-- supabase_auth_admin sólo existe en proyectos Supabase (local o cloud).
-- En un Postgres pelado el rol no está, así que los grants se ejecutan
-- condicionalmente para que la migración siga siendo aplicable allí.
do $$
begin
    if exists (select 1 from pg_roles where rolname = 'supabase_auth_admin') then
        execute 'grant execute on function public.custom_access_token_hook(jsonb) to supabase_auth_admin';
        execute 'grant usage on schema core to supabase_auth_admin';
        execute 'grant select on core.workspace_members, core.workspaces, core.accountant_assignments to supabase_auth_admin';
    end if;
end$$;
