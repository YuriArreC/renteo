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

/**
 * Fetch al backend sin token. Sirve para endpoints públicos
 * (/api/public/legal/{key} para T&C / privacidad antes del login).
 */
export async function fetchApiPublic<T = unknown>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  return _fetch<T>(path, null, init);
}

export interface LegalTextResponse {
  key: string;
  version: string;
  body: string;
  effective_from: string;
}

// ARCOP (skill 5).

export type ArcopTipo =
  | "acceso"
  | "rectificacion"
  | "cancelacion"
  | "oposicion"
  | "portabilidad";

export type ArcopEstado =
  | "recibida"
  | "en_proceso"
  | "cumplida"
  | "rechazada";

export interface CreateArcopRequest {
  tipo: ArcopTipo;
  descripcion?: string;
}

export interface UpdateArcopRequest {
  estado?: ArcopEstado;
  respuesta?: string;
}

export interface ArcopResponse {
  id: string;
  tipo: ArcopTipo;
  estado: ArcopEstado;
  descripcion: string | null;
  recibida_at: string;
  respondida_at: string | null;
  respuesta: string | null;
}

export interface ArcopListResponse {
  solicitudes: ArcopResponse[];
}

// Alertas pre-cierre.

export type AlertaSeveridad = "info" | "warning" | "critical";
export type AlertaEstado =
  | "nueva"
  | "vista"
  | "descartada"
  | "accionada";

export interface AlertaResponse {
  id: string;
  empresa_id: string | null;
  tipo: string;
  severidad: AlertaSeveridad;
  titulo: string;
  descripcion: string;
  accion_recomendada: string | null;
  estado: AlertaEstado;
  fecha_limite: string | null;
  created_at: string;
}

export interface AlertasListResponse {
  alertas: AlertaResponse[];
}

export interface EvaluateAlertasRequest {
  empresa_id: string;
  tax_year: number;
  regimen: SimulatorRegimen;
  rli_proyectada_pesos: string;
  retiros_declarados_pesos?: string;
  palancas_aplicadas?: string[];
}

export interface EvaluateAlertasResponse {
  creadas: number;
  ya_existentes: number;
  alertas: AlertaResponse[];
}

export interface UpdateAlertaRequest {
  estado: AlertaEstado;
}

// Cartera (cliente B).

export interface UltimaSimulacion {
  id: string;
  ahorro_total_clp: string;
  created_at: string;
}

export interface UltimaRecomendacion {
  id: string;
  regimen_recomendado: string;
  ahorro_estimado_clp: string | null;
  created_at: string;
}

export interface CarteraEmpresaItem {
  empresa_id: string;
  rut: string;
  razon_social: string;
  regimen_actual: RegimenActual;
  alertas_abiertas: number;
  ultima_simulacion: UltimaSimulacion | null;
  ultima_recomendacion: UltimaRecomendacion | null;
  score_oportunidad: number;
}

export interface CarteraResponse {
  empresas: CarteraEmpresaItem[];
  total_empresas: number;
  total_alertas_abiertas: number;
  ahorro_potencial_estimado_clp: string;
}

// Admin rules (skill 11 fase 6).

export type RuleStatus =
  | "draft"
  | "pending_approval"
  | "published"
  | "deprecated";

export interface RuleSetSummary {
  id: string;
  domain: string;
  key: string;
  version: number;
  status: RuleStatus;
  vigencia_desde: string;
  vigencia_hasta: string | null;
  published_by_contador: string | null;
  published_by_admin: string | null;
  published_at: string | null;
  created_at: string;
}

export interface RuleSetListResponse {
  rule_sets: RuleSetSummary[];
}

export interface RuleSetDetail extends RuleSetSummary {
  rules: Record<string, unknown>;
  fuente_legal: Array<Record<string, unknown>>;
}

export interface ValidateSchemaRequest {
  domain: string;
  rules: Record<string, unknown>;
}

export interface ValidationFailureOut {
  path: string;
  message: string;
}

export interface ValidateSchemaResponse {
  valid: boolean;
  domains_disponibles: string[];
  errors: ValidationFailureOut[];
}

export interface CreateRuleDraftRequest {
  domain: string;
  key: string;
  vigencia_desde: string;
  vigencia_hasta?: string;
  rules: Record<string, unknown>;
  fuente_legal: Array<Record<string, unknown>>;
}

export interface DryRunResponse {
  rule_id: string;
  domain: string;
  key: string;
  evaluadas: number;
  pasaban_antes: number;
  pasan_ahora: number;
  cambian_elegibilidad: number;
  delta_ahorro_total_clp: string;
  nota: string;
}

// Batch diagnose (cliente B v2).

export interface DiagnoseInputsTemplate {
  tax_year: number;
  ingresos_promedio_3a_uf: string;
  ingresos_max_anual_uf: string;
  capital_efectivo_inicial_uf: string;
  pct_ingresos_pasivos: string;
  todos_duenos_personas_naturales_chile: boolean;
  participacion_empresas_no_14d_sobre_10pct: boolean;
  sector: Sector;
  ventas_anuales_uf: string;
  rli_proyectada_anual_uf: string;
  plan_retiros_pct: string;
}

export interface BatchDiagnoseRequest {
  empresa_ids: string[];
  inputs: DiagnoseInputsTemplate;
}

export interface BatchDiagnoseItem {
  empresa_id: string;
  razon_social: string;
  regimen_actual: "14_a" | "14_d_3" | "14_d_8";
  regimen_recomendado: "14_a" | "14_d_3" | "14_d_8";
  ahorro_estimado_clp: string;
  recomendacion_id: string;
  error: string | null;
}

export interface BatchDiagnoseFailure {
  empresa_id: string;
  error: string;
}

export interface BatchDiagnoseResponse {
  procesadas: number;
  creadas: number;
  fallidas: number;
  items: BatchDiagnoseItem[];
  failures: BatchDiagnoseFailure[];
  ahorro_total_clp: string;
  disclaimer_version: string;
}

// Encargados de tratamiento (skill 5).

export interface EncargadoPublic {
  nombre: string;
  proposito: string;
  pais_tratamiento: string;
}

export interface EncargadoListPublicResponse {
  encargados: EncargadoPublic[];
}

export interface EncargadoAdmin extends EncargadoPublic {
  id: string;
  dpa_firmado_at: string | null;
  dpa_vigente_hasta: string | null;
  dpa_url: string | null;
  contacto_dpo: string | null;
  notas: string | null;
  activo: boolean;
  created_at: string;
  updated_at: string;
}

export interface EncargadoListAdminResponse {
  encargados: EncargadoAdmin[];
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
  sence_monto?: string;
  rebaja_14e_pct?: string;
  retiros_adicionales?: string;
  sueldo_empresarial_mensual?: string;
  credito_id_monto?: string;
  apv_monto?: string;
}

export interface ScenarioRequest {
  regimen: SimulatorRegimen;
  tax_year: number;
  rli_base: string;
  retiros_base?: string;
  planilla_anual_pesos?: string;
  palancas: SimulatorPalancas;
  nombre?: string;
  empresa_id?: string;
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
  empresa_id: string | null;
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

// Empresas.

export type RegimenActual =
  | "14_a"
  | "14_d_3"
  | "14_d_8"
  | "presunta"
  | "desconocido";

export interface CreateEmpresaRequest {
  rut: string;
  razon_social: string;
  giro?: string;
  regimen_actual?: RegimenActual;
  fecha_inicio_actividades?: string;
  capital_inicial_uf?: string;
}

export interface EmpresaResponse {
  id: string;
  rut: string;
  razon_social: string;
  giro: string | null;
  regimen_actual: RegimenActual;
  fecha_inicio_actividades: string | null;
  capital_inicial_uf: string | null;
  created_at: string;
}

export interface EmpresasListResponse {
  empresas: EmpresaResponse[];
}

// Sincronización SII (skill 4).

export type SiiProvider = "mock" | "simpleapi" | "baseapi" | "apigateway";

export interface SyncSiiRequest {
  months?: number;
}

export interface SyncSiiResponse {
  sync_id: string;
  provider: SiiProvider;
  period_from: string;
  period_to: string;
  rcv_rows_inserted: number;
  rcv_rows_total: number;
  status: string;
}

export interface SyncStatusResponse {
  empresa_id: string;
  last_sync_at: string | null;
  last_sync_status: string | null;
  last_sync_provider: SiiProvider | null;
  rcv_rows_total: number;
  f29_periodos_total: number;
  f22_anios_total: number;
}

// Diagnóstico de régimen (skill 7).

export type RegimeKey = "14_a" | "14_d_3" | "14_d_8" | "renta_presunta";
export type Sector =
  | "comercio"
  | "servicios"
  | "agricola"
  | "transporte"
  | "mineria"
  | "otro";

export interface DiagnoseRequest {
  tax_year: number;
  regimen_actual?: "14_a" | "14_d_3" | "14_d_8";
  ingresos_promedio_3a_uf: string;
  ingresos_max_anual_uf: string;
  capital_efectivo_inicial_uf: string;
  pct_ingresos_pasivos: string;
  todos_duenos_personas_naturales_chile: boolean;
  participacion_empresas_no_14d_sobre_10pct: boolean;
  sector: Sector;
  ventas_anuales_uf: string;
  rli_proyectada_anual_uf: string;
  plan_retiros_pct: string;
  empresa_id?: string;
}

export interface RequisitoOut {
  texto: string;
  ok: boolean;
  fundamento: string;
}

export interface EligibilityOut {
  regimen: RegimeKey;
  label: string;
  elegible: boolean;
  requisitos: RequisitoOut[];
}

export interface ProjectionRow {
  año: number;
  rli: string;
  idpc: string;
  retiros: string;
  igc_dueno: string;
  carga_total: string;
}

export interface RegimeProjection {
  regimen: RegimeKey;
  label: string;
  rows: ProjectionRow[];
  total_3a: string;
  es_transitoria: boolean;
  nota: string | null;
}

export interface DualProjection {
  base: RegimeProjection;
  revertido: RegimeProjection;
}

export interface DiagnoseVeredicto {
  regimen_actual: "14_a" | "14_d_3" | "14_d_8";
  regimen_recomendado: RegimeKey;
  ahorro_3a_clp: string;
  ahorro_3a_uf: string;
}

export interface DiagnoseResponse {
  id: string;
  tax_year: number;
  veredicto: DiagnoseVeredicto;
  elegibilidad: EligibilityOut[];
  proyecciones: RegimeProjection[];
  proyeccion_dual_14d3: DualProjection | null;
  riesgos: string[];
  fuente_legal: string[];
  disclaimer: string;
  disclaimer_version: string;
  engine_version: string;
}

export interface RecomendacionListItem {
  id: string;
  tax_year: number;
  tipo: string;
  descripcion: string;
  regimen_actual: "14_a" | "14_d_3" | "14_d_8";
  regimen_recomendado: RegimeKey;
  ahorro_estimado_clp: string | null;
  disclaimer_version: string;
  engine_version: string;
  empresa_id: string | null;
  created_at: string;
}

export interface RecomendacionListResponse {
  recomendaciones: RecomendacionListItem[];
}
