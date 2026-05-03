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

// Endpoints de cálculo (placeholder, valores no firmados).

export type IdpcRegimen = "14_a" | "14_d_3" | "14_d_8";
export type PpmRegimen = "14_d_3" | "14_d_8";

export interface CalcResponse {
  value: string;
  currency: "CLP";
  tax_year: number;
  fuente_legal: string;
  disclaimer: string;
}

export interface IdpcRequest {
  regimen: IdpcRegimen;
  tax_year: number;
  rli: string;
}

export interface IgcRequest {
  tax_year: number;
  base_pesos: string;
}

export interface PpmRequest {
  regimen: PpmRegimen;
  tax_year: number;
  ingresos_mes_pesos: string;
  ingresos_anio_anterior_uf: string;
}

// Comparador multi-régimen.

export type ComparadorRegimenKey =
  | "14_a"
  | "14_d_3"
  | "14_d_3_revertido"
  | "14_d_8";

export interface ComparadorRequest {
  tax_year: number;
  rli: string;
  retiros_pesos: string;
}

export interface RegimenScenario {
  regimen: ComparadorRegimenKey;
  label: string;
  idpc: string;
  igc_dueno: string;
  carga_total: string;
  ahorro_vs_14a: string;
  es_recomendado: boolean;
  es_transitoria: boolean;
  nota: string | null;
  fuente_legal: string;
}

export interface ComparadorResponse {
  tax_year: number;
  rli: string;
  retiros_pesos: string;
  scenarios: RegimenScenario[];
  disclaimer: string;
}

// Simulador de cierre.

export type SimulatorRegimen = "14_a" | "14_d_3" | "14_d_8";

export interface SimulatorPalancas {
  dep_instantanea?: string;
  rebaja_14e_pct?: string;
  retiros_adicionales?: string;
  sueldo_empresarial_mensual?: string;
}

export interface ScenarioRequest {
  regimen: SimulatorRegimen;
  tax_year: number;
  rli_base: string;
  retiros_base?: string;
  palancas: SimulatorPalancas;
  nombre?: string;
}

export interface ScenarioResultado {
  rli: string;
  idpc: string;
  retiros_total: string;
  igc_dueno: string;
  carga_total: string;
}

export interface PalancaImpacto {
  palanca_id: string;
  label: string;
  aplicada: boolean;
  monto_aplicado: string;
  fuente_legal: string;
  nota: string | null;
}

export interface BanderaRoja {
  severidad: "warning" | "block";
  palanca_id: string;
  mensaje: string;
}

export interface ScenarioResponse {
  id: string;
  nombre: string;
  tax_year: number;
  regimen: SimulatorRegimen;
  base: ScenarioResultado;
  simulado: ScenarioResultado;
  ahorro_total: string;
  palancas_aplicadas: PalancaImpacto[];
  banderas: BanderaRoja[];
  engine_version: string;
  disclaimer: string;
}

export interface ScenarioListItem {
  id: string;
  nombre: string;
  tax_year: number;
  regimen: SimulatorRegimen;
  carga_base: string;
  carga_simulada: string;
  ahorro_total: string;
  es_recomendado: boolean;
  created_at: string;
}

export interface ScenarioListResponse {
  scenarios: ScenarioListItem[];
}

export interface CompareScenarioCard {
  id: string;
  nombre: string;
  tax_year: number;
  regimen: SimulatorRegimen;
  base: ScenarioResultado;
  simulado: ScenarioResultado;
  ahorro_total: string;
  palancas_aplicadas: PalancaImpacto[];
  banderas: BanderaRoja[];
  es_recomendado: boolean;
}

export interface PlanAccionItem {
  palanca_id: string;
  label: string;
  accion: string;
  fundamento_legal: string;
  fecha_limite: string;
}

export interface CompareResponse {
  scenarios: CompareScenarioCard[];
  plan_accion: PlanAccionItem[];
  disclaimer: string;
}
