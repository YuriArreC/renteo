// Cliente HTTP para Client Components / event handlers (browser).
// La variante server-side vive en `api-server.ts` para que esta entrada
// no arrastre `next/headers` cuando un Client Component la importe.

import { createClient as createBrowserClient } from "@/lib/supabase/client";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly detail: string,
  ) {
    super(`API ${status}: ${detail}`);
    this.name = "ApiError";
  }
}

export async function _fetch<T>(
  path: string,
  token: string | null,
  init?: RequestInit,
): Promise<T> {
  const headers = new Headers(init?.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init?.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${API_URL}${path}`, { ...init, headers });

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      if (typeof body?.detail === "string") detail = body.detail;
    } catch {
      // Body no JSON; usamos statusText.
    }
    throw new ApiError(response.status, detail);
  }

  if (response.status === 204) {
    return null as T;
  }
  return (await response.json()) as T;
}

export async function fetchApiClient<T = unknown>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const supabase = createBrowserClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();
  return _fetch<T>(path, session?.access_token ?? null, init);
}

// ---------------------------------------------------------------------------
// Tipos manuales del API mientras el pipeline shared-types no esté listo
// (fase 1+). Mantener sincronizado con apps/api/src/routers/*.
// ---------------------------------------------------------------------------

export type WorkspaceType = "pyme" | "accounting_firm";

export type Role =
  | "owner"
  | "cfo"
  | "accountant_lead"
  | "accountant_staff"
  | "viewer";

export interface MeWorkspace {
  id: string;
  name: string;
  type: WorkspaceType;
  role: Role;
  empresa_ids: string[];
}

export interface MeResponse {
  user_id: string;
  workspace: MeWorkspace | null;
}

export interface CreateWorkspaceReq {
  name: string;
  type: WorkspaceType;
  consent_tratamiento_datos: true;
}

export interface CreateWorkspaceResp {
  id: string;
  name: string;
  type: WorkspaceType;
  role: Role;
}
