"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "@/components/ui/sonner";
import {
  ApiError,
  type DpiaCreateRequest,
  type DpiaListResponse,
  type DpiaResponse,
  type RatBaseLegal,
  type RatCreateRequest,
  type RatListResponse,
  type RatResponse,
  type RiesgoNivel,
  fetchApiClient,
} from "@/lib/api";
import { createClient } from "@/lib/supabase/client";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const BASES_LEGALES: RatBaseLegal[] = [
  "consentimiento",
  "contrato",
  "interes_legitimo",
  "obligacion_legal",
  "interes_vital",
  "interes_publico",
];

const RIESGOS: RiesgoNivel[] = ["bajo", "medio", "alto"];

function splitLines(text: string): string[] {
  return text
    .split("\n")
    .map((s) => s.trim())
    .filter((s) => s.length > 0);
}

async function downloadXlsx(path: string, filename: string): Promise<void> {
  const supabase = createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();
  const headers: HeadersInit = {};
  if (session?.access_token) {
    headers["Authorization"] = `Bearer ${session.access_token}`;
  }
  const response = await fetch(`${API_URL}${path}`, { headers });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  const blob = await response.blob();
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(a.href);
}

function RatTab({ isAdmin }: { isAdmin: boolean }) {
  const t = useTranslations("privacyCompliance.rat");
  const queryClient = useQueryClient();

  const [nombre, setNombre] = useState("");
  const [finalidad, setFinalidad] = useState("");
  const [baseLegal, setBaseLegal] = useState<RatBaseLegal>("contrato");
  const [titulares, setTitulares] = useState("");
  const [datos, setDatos] = useState("");
  const [sensibles, setSensibles] = useState(false);
  const [encargados, setEncargados] = useState("");
  const [plazo, setPlazo] = useState("");
  const [medidas, setMedidas] = useState("");
  const [responsable, setResponsable] = useState("");

  const list = useQuery<RatListResponse>({
    queryKey: ["rat-list"],
    queryFn: () => fetchApiClient<RatListResponse>("/api/privacy/rat"),
  });

  const create = useMutation({
    mutationFn: (req: RatCreateRequest) =>
      fetchApiClient<RatResponse>("/api/privacy/rat", {
        method: "POST",
        body: JSON.stringify(req),
      }),
    onSuccess: () => {
      toast.success(t("created"));
      setNombre("");
      setFinalidad("");
      setTitulares("");
      setDatos("");
      setEncargados("");
      setPlazo("");
      setMedidas("");
      setResponsable("");
      queryClient.invalidateQueries({ queryKey: ["rat-list"] });
    },
    onError: (err) =>
      toast.error(err instanceof ApiError ? err.detail : String(err)),
  });

  const archive = useMutation({
    mutationFn: (id: string) =>
      fetchApiClient(`/api/privacy/rat/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      toast.success(t("archived"));
      queryClient.invalidateQueries({ queryKey: ["rat-list"] });
    },
    onError: (err) =>
      toast.error(err instanceof ApiError ? err.detail : String(err)),
  });

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!isAdmin) return;
    create.mutate({
      nombre_actividad: nombre,
      finalidad,
      base_legal: baseLegal,
      categorias_titulares: splitLines(titulares),
      categorias_datos: splitLines(datos),
      datos_sensibles: sensibles,
      encargados_referenciados: splitLines(encargados),
      transferencias_internacionales: [],
      plazo_conservacion: plazo,
      medidas_seguridad: splitLines(medidas),
      responsable_email: responsable,
    });
  };

  return (
    <div className="space-y-6">
      {isAdmin && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">{t("formHeader")}</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={onSubmit} className="grid gap-4 md:grid-cols-2">
              <div className="space-y-1">
                <Label>{t("fields.nombre")}</Label>
                <Input
                  value={nombre}
                  onChange={(e) => setNombre(e.target.value)}
                  required
                />
              </div>
              <div className="space-y-1">
                <Label>{t("fields.responsable")}</Label>
                <Input
                  type="email"
                  value={responsable}
                  onChange={(e) => setResponsable(e.target.value)}
                  required
                />
              </div>
              <div className="space-y-1 md:col-span-2">
                <Label>{t("fields.finalidad")}</Label>
                <textarea
                  value={finalidad}
                  onChange={(e) => setFinalidad(e.target.value)}
                  rows={3}
                  required
                  className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                />
              </div>
              <div className="space-y-1">
                <Label>{t("fields.baseLegal")}</Label>
                <select
                  value={baseLegal}
                  onChange={(e) =>
                    setBaseLegal(e.target.value as RatBaseLegal)
                  }
                  className="flex h-10 w-full rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                >
                  {BASES_LEGALES.map((b) => (
                    <option key={b} value={b}>
                      {t(`baseLegalOptions.${b}`)}
                    </option>
                  ))}
                </select>
              </div>
              <div className="space-y-1">
                <Label>{t("fields.plazo")}</Label>
                <Input
                  value={plazo}
                  onChange={(e) => setPlazo(e.target.value)}
                  required
                />
              </div>
              <div className="space-y-1">
                <Label>{t("fields.titulares")}</Label>
                <textarea
                  value={titulares}
                  onChange={(e) => setTitulares(e.target.value)}
                  rows={3}
                  className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                  placeholder={t("fields.linePlaceholder")}
                />
              </div>
              <div className="space-y-1">
                <Label>{t("fields.datos")}</Label>
                <textarea
                  value={datos}
                  onChange={(e) => setDatos(e.target.value)}
                  rows={3}
                  className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                  placeholder={t("fields.linePlaceholder")}
                />
              </div>
              <div className="space-y-1">
                <Label>{t("fields.encargados")}</Label>
                <textarea
                  value={encargados}
                  onChange={(e) => setEncargados(e.target.value)}
                  rows={3}
                  className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                  placeholder={t("fields.linePlaceholder")}
                />
              </div>
              <div className="space-y-1">
                <Label>{t("fields.medidas")}</Label>
                <textarea
                  value={medidas}
                  onChange={(e) => setMedidas(e.target.value)}
                  rows={3}
                  className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                  placeholder={t("fields.linePlaceholder")}
                />
              </div>
              <label className="flex items-center gap-2 text-xs">
                <input
                  type="checkbox"
                  checked={sensibles}
                  onChange={(e) => setSensibles(e.target.checked)}
                  className="h-4 w-4 rounded border-input"
                />
                {t("fields.sensibles")}
              </label>
              <div className="md:col-span-2">
                <Button type="submit" disabled={create.isPending}>
                  {create.isPending ? t("submitting") : t("submit")}
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-base">{t("listHeader")}</CardTitle>
          <Button
            size="sm"
            variant="outline"
            onClick={() =>
              downloadXlsx(
                "/api/privacy/rat.xlsx",
                "rat-actividades-tratamiento.xlsx",
              ).catch((err: unknown) =>
                toast.error(
                  err instanceof Error ? err.message : String(err),
                ),
              )
            }
          >
            {t("export")}
          </Button>
        </CardHeader>
        <CardContent>
          {list.isLoading ? (
            <p className="text-xs text-muted-foreground">{t("loading")}</p>
          ) : (list.data?.records ?? []).length === 0 ? (
            <p className="text-xs text-muted-foreground">{t("empty")}</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-border bg-muted/40 text-left">
                    <th className="p-2 font-medium">{t("cols.nombre")}</th>
                    <th className="p-2 font-medium">{t("cols.base")}</th>
                    <th className="p-2 font-medium">
                      {t("cols.sensibles")}
                    </th>
                    <th className="p-2 font-medium">
                      {t("cols.responsable")}
                    </th>
                    <th className="p-2 font-medium">{t("cols.creado")}</th>
                    {isAdmin && (
                      <th className="p-2 font-medium">
                        {t("cols.acciones")}
                      </th>
                    )}
                  </tr>
                </thead>
                <tbody>
                  {(list.data?.records ?? []).map((r) => (
                    <tr key={r.id} className="border-b border-border">
                      <td className="p-2">{r.nombre_actividad}</td>
                      <td className="p-2">
                        {t(`baseLegalOptions.${r.base_legal}`)}
                      </td>
                      <td className="p-2">
                        {r.datos_sensibles ? "sí" : "no"}
                      </td>
                      <td className="p-2 font-mono text-[10px]">
                        {r.responsable_email}
                      </td>
                      <td className="p-2 text-[10px]">
                        {new Date(r.created_at).toLocaleDateString("es-CL")}
                      </td>
                      {isAdmin && (
                        <td className="p-2">
                          <Button
                            size="sm"
                            variant="ghost"
                            disabled={archive.isPending}
                            onClick={() => archive.mutate(r.id)}
                          >
                            {t("archive")}
                          </Button>
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function DpiaTab({ isAdmin }: { isAdmin: boolean }) {
  const t = useTranslations("privacyCompliance.dpia");
  const queryClient = useQueryClient();

  const [nombre, setNombre] = useState("");
  const [descripcion, setDescripcion] = useState("");
  const [necesidad, setNecesidad] = useState("");
  const [riesgosTexto, setRiesgosTexto] = useState("");
  const [medidas, setMedidas] = useState("");
  const [riesgo, setRiesgo] = useState<RiesgoNivel>("medio");

  const list = useQuery<DpiaListResponse>({
    queryKey: ["dpia-list"],
    queryFn: () => fetchApiClient<DpiaListResponse>("/api/privacy/dpia"),
  });

  const create = useMutation({
    mutationFn: (req: DpiaCreateRequest) =>
      fetchApiClient<DpiaResponse>("/api/privacy/dpia", {
        method: "POST",
        body: JSON.stringify(req),
      }),
    onSuccess: () => {
      toast.success(t("created"));
      setNombre("");
      setDescripcion("");
      setNecesidad("");
      setRiesgosTexto("");
      setMedidas("");
      queryClient.invalidateQueries({ queryKey: ["dpia-list"] });
    },
    onError: (err) =>
      toast.error(err instanceof ApiError ? err.detail : String(err)),
  });

  const aprobar = useMutation({
    mutationFn: (id: string) =>
      fetchApiClient<DpiaResponse>(`/api/privacy/dpia/${id}`, {
        method: "PATCH",
        body: JSON.stringify({ aprobar: true }),
      }),
    onSuccess: () => {
      toast.success(t("approved"));
      queryClient.invalidateQueries({ queryKey: ["dpia-list"] });
    },
    onError: (err) =>
      toast.error(err instanceof ApiError ? err.detail : String(err)),
  });

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!isAdmin) return;
    create.mutate({
      nombre_evaluacion: nombre,
      descripcion_tratamiento: descripcion,
      necesidad_proporcionalidad: necesidad,
      riesgos_identificados: splitLines(riesgosTexto).map((r) => ({
        descripcion: r,
      })),
      medidas_mitigacion: splitLines(medidas),
      riesgo_residual: riesgo,
    });
  };

  return (
    <div className="space-y-6">
      {isAdmin && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">{t("formHeader")}</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={onSubmit} className="grid gap-4 md:grid-cols-2">
              <div className="space-y-1 md:col-span-2">
                <Label>{t("fields.nombre")}</Label>
                <Input
                  value={nombre}
                  onChange={(e) => setNombre(e.target.value)}
                  required
                />
              </div>
              <div className="space-y-1 md:col-span-2">
                <Label>{t("fields.descripcion")}</Label>
                <textarea
                  value={descripcion}
                  onChange={(e) => setDescripcion(e.target.value)}
                  rows={4}
                  required
                  className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                />
              </div>
              <div className="space-y-1 md:col-span-2">
                <Label>{t("fields.necesidad")}</Label>
                <textarea
                  value={necesidad}
                  onChange={(e) => setNecesidad(e.target.value)}
                  rows={3}
                  required
                  className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                />
              </div>
              <div className="space-y-1">
                <Label>{t("fields.riesgos")}</Label>
                <textarea
                  value={riesgosTexto}
                  onChange={(e) => setRiesgosTexto(e.target.value)}
                  rows={3}
                  className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                  placeholder={t("fields.linePlaceholder")}
                />
              </div>
              <div className="space-y-1">
                <Label>{t("fields.medidas")}</Label>
                <textarea
                  value={medidas}
                  onChange={(e) => setMedidas(e.target.value)}
                  rows={3}
                  className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                  placeholder={t("fields.linePlaceholder")}
                />
              </div>
              <div className="space-y-1">
                <Label>{t("fields.riesgo")}</Label>
                <select
                  value={riesgo}
                  onChange={(e) => setRiesgo(e.target.value as RiesgoNivel)}
                  className="flex h-10 w-full rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                >
                  {RIESGOS.map((r) => (
                    <option key={r} value={r}>
                      {t(`riesgoOptions.${r}`)}
                    </option>
                  ))}
                </select>
              </div>
              <div className="md:col-span-2">
                <Button type="submit" disabled={create.isPending}>
                  {create.isPending ? t("submitting") : t("submit")}
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-base">{t("listHeader")}</CardTitle>
          <Button
            size="sm"
            variant="outline"
            onClick={() =>
              downloadXlsx(
                "/api/privacy/dpia.xlsx",
                "dpia-evaluaciones-impacto.xlsx",
              ).catch((err: unknown) =>
                toast.error(
                  err instanceof Error ? err.message : String(err),
                ),
              )
            }
          >
            {t("export")}
          </Button>
        </CardHeader>
        <CardContent>
          {list.isLoading ? (
            <p className="text-xs text-muted-foreground">{t("loading")}</p>
          ) : (list.data?.records ?? []).length === 0 ? (
            <p className="text-xs text-muted-foreground">{t("empty")}</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-border bg-muted/40 text-left">
                    <th className="p-2 font-medium">{t("cols.nombre")}</th>
                    <th className="p-2 font-medium">{t("cols.riesgo")}</th>
                    <th className="p-2 font-medium">
                      {t("cols.aprobada")}
                    </th>
                    <th className="p-2 font-medium">{t("cols.version")}</th>
                    {isAdmin && (
                      <th className="p-2 font-medium">
                        {t("cols.acciones")}
                      </th>
                    )}
                  </tr>
                </thead>
                <tbody>
                  {(list.data?.records ?? []).map((r) => (
                    <tr key={r.id} className="border-b border-border">
                      <td className="p-2">{r.nombre_evaluacion}</td>
                      <td className="p-2">
                        {t(`riesgoOptions.${r.riesgo_residual}`)}
                      </td>
                      <td className="p-2">
                        {r.aprobado_at
                          ? new Date(r.aprobado_at).toLocaleDateString(
                              "es-CL",
                            )
                          : "—"}
                      </td>
                      <td className="p-2">v{r.version}</td>
                      {isAdmin && (
                        <td className="p-2">
                          {r.aprobado_at ? (
                            <span className="text-[10px] text-muted-foreground">
                              {t("alreadyApproved")}
                            </span>
                          ) : (
                            <Button
                              size="sm"
                              variant="ghost"
                              disabled={aprobar.isPending}
                              onClick={() => aprobar.mutate(r.id)}
                            >
                              {t("approve")}
                            </Button>
                          )}
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

export function RatDpiaPanel({ isAdmin }: { isAdmin: boolean }) {
  const t = useTranslations("privacyCompliance");
  const [tab, setTab] = useState<"rat" | "dpia">("rat");

  return (
    <div className="space-y-4">
      <div className="flex gap-2 border-b border-border">
        <button
          type="button"
          onClick={() => setTab("rat")}
          className={`px-4 py-2 text-sm font-medium ${
            tab === "rat"
              ? "border-b-2 border-primary text-primary"
              : "text-muted-foreground"
          }`}
        >
          {t("tabRat")}
        </button>
        <button
          type="button"
          onClick={() => setTab("dpia")}
          className={`px-4 py-2 text-sm font-medium ${
            tab === "dpia"
              ? "border-b-2 border-primary text-primary"
              : "text-muted-foreground"
          }`}
        >
          {t("tabDpia")}
        </button>
      </div>
      {tab === "rat" ? <RatTab isAdmin={isAdmin} /> : <DpiaTab isAdmin={isAdmin} />}
    </div>
  );
}
