"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { ScenarioHistorial } from "@/app/dashboard/simulator/ScenarioHistorial";
import { DecisionRibbon } from "@/components/DecisionRibbon";
import { SnapshotTrace_Shared } from "@/components/SnapshotTrace_Shared";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { toast } from "@/components/ui/sonner";
import {
  ApiError,
  type EmpresasListResponse,
  fetchApiClient,
  type ScenarioRequest,
  type ScenarioResponse,
  type SimulatorPalancas,
} from "@/lib/api";

function formatCLP(value: string | number): string {
  const n = typeof value === "string" ? Number(value) : value;
  return new Intl.NumberFormat("es-CL", {
    style: "currency",
    currency: "CLP",
    maximumFractionDigits: 0,
  }).format(n);
}

const schema = z.object({
  regimen: z.enum(["14_a", "14_d_3", "14_d_8"]),
  tax_year: z.coerce.number().int().min(2024).max(2030),
  empresa_id: z.string(),
  rli_base: z.coerce.number().min(0),
  retiros_base: z.coerce.number().min(0),
  planilla_anual_pesos: z.coerce.number().min(0),
  dep_instantanea: z.coerce.number().min(0),
  sence_monto: z.coerce.number().min(0),
  rebaja_14e_pct: z.coerce.number().min(0).max(1),
  retiros_adicionales: z.coerce.number().min(0),
  sueldo_empresarial_mensual: z.coerce.number().min(0),
  credito_id_monto: z.coerce.number().min(0),
  apv_monto: z.coerce.number().min(0),
  ppm_extraordinario_monto: z.coerce.number().min(0),
  iva_postergacion_aplicada: z.boolean(),
  credito_reinversion_monto: z.coerce.number().min(0),
  depreciacion_acelerada_monto: z.coerce.number().min(0),
  cambio_regimen_objetivo: z.enum(["", "14_a", "14_d_3", "14_d_8"]),
});

type FormValues = z.infer<typeof schema>;

function buildPalancas(v: FormValues): SimulatorPalancas {
  const p: SimulatorPalancas = {};
  if (v.dep_instantanea > 0) p.dep_instantanea = String(v.dep_instantanea);
  if (v.sence_monto > 0) p.sence_monto = String(v.sence_monto);
  if (v.rebaja_14e_pct > 0) p.rebaja_14e_pct = String(v.rebaja_14e_pct);
  if (v.retiros_adicionales > 0)
    p.retiros_adicionales = String(v.retiros_adicionales);
  if (v.sueldo_empresarial_mensual > 0)
    p.sueldo_empresarial_mensual = String(v.sueldo_empresarial_mensual);
  if (v.credito_id_monto > 0)
    p.credito_id_monto = String(v.credito_id_monto);
  if (v.apv_monto > 0) p.apv_monto = String(v.apv_monto);
  if (v.ppm_extraordinario_monto > 0)
    p.ppm_extraordinario_monto = String(v.ppm_extraordinario_monto);
  if (v.iva_postergacion_aplicada) p.iva_postergacion_aplicada = true;
  if (v.credito_reinversion_monto > 0)
    p.credito_reinversion_monto = String(v.credito_reinversion_monto);
  if (v.depreciacion_acelerada_monto > 0)
    p.depreciacion_acelerada_monto = String(v.depreciacion_acelerada_monto);
  if (v.cambio_regimen_objetivo !== "")
    p.cambio_regimen_objetivo = v.cambio_regimen_objetivo;
  return p;
}

export function ScenarioSimulator() {
  const tForm = useTranslations("simulator.form");
  const tResult = useTranslations("simulator.result");
  const tSeverity = useTranslations("simulator.severity");
  const tSimulator = useTranslations("simulator");
  const queryClient = useQueryClient();

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      regimen: "14_d_3",
      tax_year: 2026,
      empresa_id: "",
      rli_base: 30_000_000,
      retiros_base: 0,
      planilla_anual_pesos: 0,
      dep_instantanea: 0,
      sence_monto: 0,
      rebaja_14e_pct: 0,
      retiros_adicionales: 0,
      sueldo_empresarial_mensual: 0,
      credito_id_monto: 0,
      apv_monto: 0,
      ppm_extraordinario_monto: 0,
      iva_postergacion_aplicada: false,
      credito_reinversion_monto: 0,
      depreciacion_acelerada_monto: 0,
      cambio_regimen_objetivo: "",
    },
  });

  const empresasQuery = useQuery<EmpresasListResponse>({
    queryKey: ["empresas-list"],
    queryFn: () =>
      fetchApiClient<EmpresasListResponse>("/api/empresas"),
  });
  const empresas = empresasQuery.data?.empresas ?? [];

  const mutation = useMutation({
    mutationFn: (req: ScenarioRequest) =>
      fetchApiClient<ScenarioResponse>("/api/scenario/simulate", {
        method: "POST",
        body: JSON.stringify(req),
      }),
    onSuccess: (data) => {
      toast.success(tSimulator("saved", { nombre: data.nombre }));
      queryClient.invalidateQueries({ queryKey: ["scenario-list"] });
    },
    onError: (err) =>
      toast.error(err instanceof ApiError ? err.detail : String(err)),
  });

  return (
    <div className="space-y-8">
      <Card>
        <CardHeader>
          <CardTitle>{tForm("submit")}</CardTitle>
        </CardHeader>
        <CardContent>
          <Form {...form}>
            <form
              onSubmit={form.handleSubmit((v) =>
                mutation.mutate({
                  regimen: v.regimen,
                  tax_year: v.tax_year,
                  rli_base: String(v.rli_base),
                  retiros_base: String(v.retiros_base),
                  planilla_anual_pesos: String(v.planilla_anual_pesos),
                  palancas: buildPalancas(v),
                  empresa_id: v.empresa_id || undefined,
                }),
              )}
              className="space-y-8"
            >
              <div className="grid gap-5 md:grid-cols-2">
                <FormField
                  control={form.control}
                  name="regimen"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>{tForm("regimen")}</FormLabel>
                      <FormControl>
                        <select
                          {...field}
                          className="flex h-10 w-full rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                        >
                          <option value="14_a">
                            {tForm("regimenOptions.14_a")}
                          </option>
                          <option value="14_d_3">
                            {tForm("regimenOptions.14_d_3")}
                          </option>
                          <option value="14_d_8">
                            {tForm("regimenOptions.14_d_8")}
                          </option>
                        </select>
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="tax_year"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>{tForm("year")}</FormLabel>
                      <FormControl>
                        <Input type="number" min={2024} max={2030} {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="empresa_id"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>{tSimulator("empresaSelect")}</FormLabel>
                      <FormControl>
                        <select
                          {...field}
                          className="flex h-10 w-full rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                        >
                          <option value="">
                            {tSimulator("empresaSelectNone")}
                          </option>
                          {empresas.map((e) => (
                            <option key={e.id} value={e.id}>
                              {e.razon_social} ({e.rut})
                            </option>
                          ))}
                        </select>
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="rli_base"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>{tForm("rliBase")}</FormLabel>
                      <FormControl>
                        <Input type="number" min={0} {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="retiros_base"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>{tForm("retirosBase")}</FormLabel>
                      <FormControl>
                        <Input type="number" min={0} {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="planilla_anual_pesos"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>{tForm("planilla")}</FormLabel>
                      <FormControl>
                        <Input type="number" min={0} {...field} />
                      </FormControl>
                      <FormDescription>
                        {tForm("planillaHint")}
                      </FormDescription>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>

              <div className="space-y-4 rounded-md border border-border p-4">
                <h3 className="text-sm font-semibold">
                  {tForm("palancasHeader")}
                </h3>
                <div className="grid gap-5 md:grid-cols-2">
                  <FormField
                    control={form.control}
                    name="dep_instantanea"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>{tForm("p1Label")}</FormLabel>
                        <FormControl>
                          <Input type="number" min={0} {...field} />
                        </FormControl>
                        <FormDescription>{tForm("p1Hint")}</FormDescription>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="sence_monto"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>{tForm("p2Label")}</FormLabel>
                        <FormControl>
                          <Input type="number" min={0} {...field} />
                        </FormControl>
                        <FormDescription>{tForm("p2Hint")}</FormDescription>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="rebaja_14e_pct"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>{tForm("p3Label")}</FormLabel>
                        <FormControl>
                          <Input
                            type="number"
                            min={0}
                            max={1}
                            step={0.05}
                            {...field}
                          />
                        </FormControl>
                        <FormDescription>{tForm("p3Hint")}</FormDescription>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="retiros_adicionales"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>{tForm("p4Label")}</FormLabel>
                        <FormControl>
                          <Input type="number" min={0} {...field} />
                        </FormControl>
                        <FormDescription>{tForm("p4Hint")}</FormDescription>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="sueldo_empresarial_mensual"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>{tForm("p5Label")}</FormLabel>
                        <FormControl>
                          <Input type="number" min={0} {...field} />
                        </FormControl>
                        <FormDescription>{tForm("p5Hint")}</FormDescription>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="credito_id_monto"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>{tForm("p6Label")}</FormLabel>
                        <FormControl>
                          <Input type="number" min={0} {...field} />
                        </FormControl>
                        <FormDescription>{tForm("p6Hint")}</FormDescription>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="apv_monto"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>{tForm("p9Label")}</FormLabel>
                        <FormControl>
                          <Input type="number" min={0} {...field} />
                        </FormControl>
                        <FormDescription>{tForm("p9Hint")}</FormDescription>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="ppm_extraordinario_monto"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>{tForm("p7Label")}</FormLabel>
                        <FormControl>
                          <Input type="number" min={0} {...field} />
                        </FormControl>
                        <FormDescription>{tForm("p7Hint")}</FormDescription>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="credito_reinversion_monto"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>{tForm("p10Label")}</FormLabel>
                        <FormControl>
                          <Input type="number" min={0} {...field} />
                        </FormControl>
                        <FormDescription>{tForm("p10Hint")}</FormDescription>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="depreciacion_acelerada_monto"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>{tForm("p11Label")}</FormLabel>
                        <FormControl>
                          <Input type="number" min={0} {...field} />
                        </FormControl>
                        <FormDescription>{tForm("p11Hint")}</FormDescription>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="cambio_regimen_objetivo"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>{tForm("p12Label")}</FormLabel>
                        <FormControl>
                          <select
                            {...field}
                            className="flex h-10 w-full rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                          >
                            <option value="">
                              {tForm("p12None")}
                            </option>
                            <option value="14_a">14 A</option>
                            <option value="14_d_3">14 D N°3</option>
                            <option value="14_d_8">14 D N°8</option>
                          </select>
                        </FormControl>
                        <FormDescription>{tForm("p12Hint")}</FormDescription>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="iva_postergacion_aplicada"
                    render={({ field }) => (
                      <FormItem className="flex items-start gap-3 md:col-span-2">
                        <FormControl>
                          <input
                            type="checkbox"
                            checked={field.value}
                            onChange={(e) =>
                              field.onChange(e.target.checked)
                            }
                            className="mt-1 h-4 w-4 rounded border-input"
                          />
                        </FormControl>
                        <div className="space-y-1 leading-none">
                          <FormLabel className="font-normal">
                            {tForm("p8Label")}
                          </FormLabel>
                          <FormDescription>{tForm("p8Hint")}</FormDescription>
                        </div>
                      </FormItem>
                    )}
                  />
                </div>
              </div>

              <Button
                type="submit"
                size="lg"
                disabled={mutation.isPending}
                className="w-full md:w-auto"
              >
                {mutation.isPending
                  ? tForm("submitting")
                  : tForm("submit")}
              </Button>
            </form>
          </Form>
        </CardContent>
      </Card>

      {mutation.data && (
        <ResultPanels
          data={mutation.data}
          tResult={tResult}
          tSeverity={tSeverity}
        />
      )}

      <ScenarioHistorial />
    </div>
  );
}

type ResultPanelsProps = {
  data: ScenarioResponse;
  tResult: ReturnType<typeof useTranslations<"simulator.result">>;
  tSeverity: ReturnType<typeof useTranslations<"simulator.severity">>;
};

function ResultPanels({ data, tResult, tSeverity }: ResultPanelsProps) {
  const rows: Array<{
    label: string;
    base: string;
    simulado: string;
  }> = [
    {
      label: tResult("rli"),
      base: data.base.rli,
      simulado: data.simulado.rli,
    },
    {
      label: tResult("idpc"),
      base: data.base.idpc,
      simulado: data.simulado.idpc,
    },
    {
      label: tResult("retiros"),
      base: data.base.retiros_total,
      simulado: data.simulado.retiros_total,
    },
    {
      label: tResult("igc"),
      base: data.base.igc_dueno,
      simulado: data.simulado.igc_dueno,
    },
    {
      label: tResult("carga"),
      base: data.base.carga_total,
      simulado: data.simulado.carga_total,
    },
  ];
  const aplicadas = data.palancas_aplicadas.filter((p) => p.aplicada);
  const ahorroNum = Number(data.ahorro_total);

  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle>{tResult("header")}</CardTitle>
        </CardHeader>
        <CardContent className="overflow-x-auto p-0">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-muted/40 text-left">
                <th className="p-4 font-medium">{tResult("metric")}</th>
                <th className="p-4 text-right font-medium">
                  {tResult("base")}
                </th>
                <th className="p-4 text-right font-medium">
                  {tResult("simulado")}
                </th>
                <th className="p-4 text-right font-medium">
                  {tResult("delta")}
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => {
                const delta = Number(r.simulado) - Number(r.base);
                return (
                  <tr key={r.label} className="border-b border-border">
                    <td className="p-4 font-medium">{r.label}</td>
                    <td className="p-4 text-right font-mono">
                      {formatCLP(r.base)}
                    </td>
                    <td className="p-4 text-right font-mono">
                      {formatCLP(r.simulado)}
                    </td>
                    <td
                      className={`p-4 text-right font-mono ${
                        delta < 0
                          ? "text-green-700"
                          : delta > 0
                            ? "text-destructive"
                            : "text-muted-foreground"
                      }`}
                    >
                      {delta === 0 ? "—" : formatCLP(delta)}
                    </td>
                  </tr>
                );
              })}
              <tr className="bg-primary/5">
                <td className="p-4 font-semibold">{tResult("ahorro")}</td>
                <td className="p-4" />
                <td className="p-4" />
                <td
                  className={`p-4 text-right font-mono font-semibold ${
                    ahorroNum > 0
                      ? "text-green-700"
                      : ahorroNum < 0
                        ? "text-destructive"
                        : "text-muted-foreground"
                  }`}
                >
                  {ahorroNum === 0 ? "—" : formatCLP(data.ahorro_total)}
                </td>
              </tr>
            </tbody>
          </table>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">
            {tResult("palancasHeader")}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {aplicadas.length === 0 ? (
            <p className="text-xs text-muted-foreground">
              {tResult("noPalancas")}
            </p>
          ) : (
            aplicadas.map((p) => (
              <div
                key={p.palanca_id}
                className="border-l-2 border-border pl-4"
              >
                <div className="flex items-baseline justify-between gap-3">
                  <div className="text-sm font-medium">{p.label}</div>
                  <div className="font-mono text-sm">
                    {formatCLP(p.monto_aplicado)}
                  </div>
                </div>
                <div className="mt-1 text-xs text-muted-foreground">
                  <strong>Fundamento:</strong> {p.fuente_legal}
                </div>
                {p.nota && (
                  <p className="mt-2 text-xs text-muted-foreground">
                    {p.nota}
                  </p>
                )}
              </div>
            ))
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">
            {tResult("banderasHeader")}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {data.banderas.length === 0 ? (
            <p className="text-xs text-muted-foreground">
              {tResult("noBanderas")}
            </p>
          ) : (
            data.banderas.map((b, idx) => (
              <div
                key={`${b.palanca_id}-${idx}`}
                className={`rounded border p-3 text-xs ${
                  b.severidad === "block"
                    ? "border-destructive/40 bg-destructive/5 text-destructive"
                    : "border-yellow-300 bg-yellow-50 text-yellow-900"
                }`}
              >
                <strong>{tSeverity(b.severidad)}:</strong> {b.mensaje}
              </div>
            ))
          )}
        </CardContent>
      </Card>

      <p className="rounded border border-yellow-300 bg-yellow-50 p-3 text-xs text-yellow-900">
        {data.disclaimer}
      </p>

      <DecisionRibbon
        context={`Escenario simulado #${data.id} (${data.regimen}, AT ${data.tax_year})`}
      />
      <SnapshotTrace_Shared
        rulesSnapshotHash={data.rules_snapshot_hash}
        engineVersion={data.engine_version}
      />
    </>
  );
}
