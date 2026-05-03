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

import { RegimeHistorial } from "@/app/dashboard/regime/RegimeHistorial";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
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
  type DiagnoseRequest,
  type DiagnoseResponse,
  type EmpresasListResponse,
  fetchApiClient,
} from "@/lib/api";

import { RegimeResult } from "./RegimeResult";

const SECTORS = [
  "comercio",
  "servicios",
  "agricola",
  "transporte",
  "mineria",
  "otro",
] as const;

const REGIMENS = ["14_a", "14_d_3", "14_d_8"] as const;

const schema = z.object({
  tax_year: z.coerce.number().int().min(2024).max(2030),
  regimen_actual: z.enum(["", ...REGIMENS]),
  empresa_id: z.string(),
  ingresos_promedio_3a_uf: z.coerce.number().min(0),
  ingresos_max_anual_uf: z.coerce.number().min(0),
  capital_efectivo_inicial_uf: z.coerce.number().min(0),
  pct_ingresos_pasivos: z.coerce.number().min(0).max(1),
  ventas_anuales_uf: z.coerce.number().min(0),
  sector: z.enum(SECTORS),
  todos_duenos_personas_naturales_chile: z.boolean(),
  participacion_empresas_no_14d_sobre_10pct: z.boolean(),
  rli_proyectada_anual_uf: z.coerce.number().min(0),
  plan_retiros_pct: z.coerce.number().min(0).max(1),
});

type FormValues = z.infer<typeof schema>;

export function RegimeWizard() {
  const tForm = useTranslations("regime.form");
  const tResult = useTranslations("regime.result");
  const queryClient = useQueryClient();

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      tax_year: 2026,
      regimen_actual: "",
      empresa_id: "",
      ingresos_promedio_3a_uf: 30000,
      ingresos_max_anual_uf: 40000,
      capital_efectivo_inicial_uf: 5000,
      pct_ingresos_pasivos: 0.1,
      ventas_anuales_uf: 30000,
      sector: "comercio",
      todos_duenos_personas_naturales_chile: true,
      participacion_empresas_no_14d_sobre_10pct: false,
      rli_proyectada_anual_uf: 1000,
      plan_retiros_pct: 0.3,
    },
  });

  const empresasQuery = useQuery<EmpresasListResponse>({
    queryKey: ["empresas-list"],
    queryFn: () =>
      fetchApiClient<EmpresasListResponse>("/api/empresas"),
  });
  const empresas = empresasQuery.data?.empresas ?? [];

  const mutation = useMutation({
    mutationFn: (req: DiagnoseRequest) =>
      fetchApiClient<DiagnoseResponse>("/api/regime/diagnose", {
        method: "POST",
        body: JSON.stringify(req),
      }),
    onSuccess: (data) => {
      toast.success(
        tResult("saved", {
          desc: `${data.veredicto.regimen_actual.toUpperCase()} → ${data.veredicto.regimen_recomendado.toUpperCase()}`,
        }),
      );
      queryClient.invalidateQueries({ queryKey: ["regime-recomendaciones"] });
    },
    onError: (err) =>
      toast.error(err instanceof ApiError ? err.detail : String(err)),
  });

  const onSubmit = (v: FormValues) => {
    const body: DiagnoseRequest = {
      tax_year: v.tax_year,
      ingresos_promedio_3a_uf: String(v.ingresos_promedio_3a_uf),
      ingresos_max_anual_uf: String(v.ingresos_max_anual_uf),
      capital_efectivo_inicial_uf: String(v.capital_efectivo_inicial_uf),
      pct_ingresos_pasivos: String(v.pct_ingresos_pasivos),
      ventas_anuales_uf: String(v.ventas_anuales_uf),
      sector: v.sector,
      todos_duenos_personas_naturales_chile:
        v.todos_duenos_personas_naturales_chile,
      participacion_empresas_no_14d_sobre_10pct:
        v.participacion_empresas_no_14d_sobre_10pct,
      rli_proyectada_anual_uf: String(v.rli_proyectada_anual_uf),
      plan_retiros_pct: String(v.plan_retiros_pct),
    };
    if (v.regimen_actual !== "") body.regimen_actual = v.regimen_actual;
    if (v.empresa_id) body.empresa_id = v.empresa_id;
    mutation.mutate(body);
  };

  return (
    <div className="space-y-8">
      <Card>
        <CardHeader>
          <CardTitle>{tForm("submit")}</CardTitle>
        </CardHeader>
        <CardContent>
          <Form {...form}>
            <form
              onSubmit={form.handleSubmit(onSubmit)}
              className="space-y-8"
            >
              <Section title={tForm("section1")}>
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
                  name="regimen_actual"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>{tForm("regimenActual")}</FormLabel>
                      <FormControl>
                        <select
                          {...field}
                          className="flex h-10 w-full rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                        >
                          <option value="">{tForm("regimenAuto")}</option>
                          <option value="14_a">14 A</option>
                          <option value="14_d_3">14 D N°3</option>
                          <option value="14_d_8">14 D N°8</option>
                        </select>
                      </FormControl>
                      <FormDescription>
                        {tForm("regimenActualHint")}
                      </FormDescription>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="empresa_id"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>{tForm("empresaSelect")}</FormLabel>
                      <FormControl>
                        <select
                          {...field}
                          className="flex h-10 w-full rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                        >
                          <option value="">
                            {tForm("empresaSelectNone")}
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
              </Section>

              <Section title={tForm("section2")}>
                <FormField
                  control={form.control}
                  name="ingresos_promedio_3a_uf"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>{tForm("ingresosProm")}</FormLabel>
                      <FormControl>
                        <Input type="number" min={0} {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="ingresos_max_anual_uf"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>{tForm("ingresosMax")}</FormLabel>
                      <FormControl>
                        <Input type="number" min={0} {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="capital_efectivo_inicial_uf"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>{tForm("capital")}</FormLabel>
                      <FormControl>
                        <Input type="number" min={0} {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="pct_ingresos_pasivos"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>{tForm("pctPasivos")}</FormLabel>
                      <FormControl>
                        <Input
                          type="number"
                          min={0}
                          max={1}
                          step={0.05}
                          {...field}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="ventas_anuales_uf"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>{tForm("ventasAnuales")}</FormLabel>
                      <FormControl>
                        <Input type="number" min={0} {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="sector"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>{tForm("sector")}</FormLabel>
                      <FormControl>
                        <select
                          {...field}
                          className="flex h-10 w-full rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                        >
                          {SECTORS.map((s) => (
                            <option key={s} value={s}>
                              {tForm(`sectorOptions.${s}`)}
                            </option>
                          ))}
                        </select>
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </Section>

              <Section title={tForm("section3")}>
                <FormField
                  control={form.control}
                  name="todos_duenos_personas_naturales_chile"
                  render={({ field }) => (
                    <FormItem className="flex items-start gap-3 md:col-span-2">
                      <FormControl>
                        <Checkbox
                          checked={field.value}
                          onChange={(e) =>
                            field.onChange(e.target.checked)
                          }
                        />
                      </FormControl>
                      <FormLabel className="font-normal">
                        {tForm("duenosChile")}
                      </FormLabel>
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="participacion_empresas_no_14d_sobre_10pct"
                  render={({ field }) => (
                    <FormItem className="flex items-start gap-3 md:col-span-2">
                      <FormControl>
                        <Checkbox
                          checked={field.value}
                          onChange={(e) =>
                            field.onChange(e.target.checked)
                          }
                        />
                      </FormControl>
                      <FormLabel className="font-normal">
                        {tForm("participaciones")}
                      </FormLabel>
                    </FormItem>
                  )}
                />
              </Section>

              <Section title={tForm("section4")}>
                <FormField
                  control={form.control}
                  name="rli_proyectada_anual_uf"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>{tForm("rliProyectada")}</FormLabel>
                      <FormControl>
                        <Input type="number" min={0} {...field} />
                      </FormControl>
                      <FormDescription>{tForm("rliHint")}</FormDescription>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="plan_retiros_pct"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>{tForm("planRetiros")}</FormLabel>
                      <FormControl>
                        <Input
                          type="number"
                          min={0}
                          max={1}
                          step={0.05}
                          {...field}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </Section>

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

      {mutation.data && <RegimeResult data={mutation.data} />}

      <RegimeHistorial />
    </div>
  );
}

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-4 rounded-md border border-border p-4">
      <h3 className="text-sm font-semibold">{title}</h3>
      <div className="grid gap-5 md:grid-cols-2">{children}</div>
    </div>
  );
}
