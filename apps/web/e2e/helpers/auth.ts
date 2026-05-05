import type { BrowserContext, Page } from "@playwright/test";

/**
 * Helpers de autenticación para Playwright (skill 9 e2e).
 *
 * Estrategia: en lugar de hacer signup real contra Supabase, sembramos
 * el localStorage que el SDK de @supabase/ssr lee al hidratar. El
 * formato del token es JSON con `access_token`, `refresh_token` y
 * `expires_at`. Cualquier llamada subsecuente al API se mockea con
 * `page.route()` desde el test individual.
 *
 * Si en el futuro queremos correr e2e contra un Supabase real (smoke
 * pre-deploy), basta con reemplazar este helper por una secuencia
 * `signInWithPassword` real.
 */

const FAKE_USER_ID = "00000000-0000-0000-0000-00000000e2e0";
const FAKE_WORKSPACE_ID_PYME = "00000000-0000-0000-0000-00000000e2ea";
const FAKE_WORKSPACE_ID_FIRM = "00000000-0000-0000-0000-00000000e2eb";
const FAKE_EMPRESA_ID = "00000000-0000-0000-0000-00000000e2e1";

export const E2E_IDS = {
  user: FAKE_USER_ID,
  workspacePyme: FAKE_WORKSPACE_ID_PYME,
  workspaceFirm: FAKE_WORKSPACE_ID_FIRM,
  empresa: FAKE_EMPRESA_ID,
};

function _projectRefFromUrl(url: string): string {
  const match = url.match(/^https?:\/\/([^.]+)\./);
  return match ? match[1] : "e2e";
}

export async function seedAuthSession(
  contextOrPage: BrowserContext | Page,
  options: {
    workspaceType?: "pyme" | "accounting_firm";
    role?: string;
  } = {},
): Promise<void> {
  const supabaseUrl =
    process.env.NEXT_PUBLIC_SUPABASE_URL ??
    "https://e2e.example.supabase.co";
  const projectRef = _projectRefFromUrl(supabaseUrl);
  const storageKey = `sb-${projectRef}-auth-token`;
  const workspaceType = options.workspaceType ?? "pyme";
  const role = options.role ?? "owner";
  const workspaceId =
    workspaceType === "accounting_firm"
      ? FAKE_WORKSPACE_ID_FIRM
      : FAKE_WORKSPACE_ID_PYME;

  const session = {
    access_token: "e2e-fake-jwt",
    refresh_token: "e2e-fake-refresh",
    expires_at: Math.floor(Date.now() / 1000) + 60 * 60,
    expires_in: 3600,
    token_type: "bearer",
    user: {
      id: FAKE_USER_ID,
      email: "e2e@renteo.local",
      aud: "authenticated",
      role: "authenticated",
      app_metadata: {
        provider: "email",
        workspace_id: workspaceId,
        workspace_type: workspaceType,
        role,
        empresa_ids: [FAKE_EMPRESA_ID],
      },
    },
  };

  const context =
    "newPage" in contextOrPage ? contextOrPage : contextOrPage.context();
  await context.addInitScript(
    ({ key, value }: { key: string; value: string }) => {
      window.localStorage.setItem(key, value);
    },
    { key: storageKey, value: JSON.stringify(session) },
  );
}
