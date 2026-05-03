"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { toast } from "@/components/ui/sonner";
import {
  ApiError,
  type CalcResponse,
  fetchApiClient,
  type IdpcRequest,
  type IgcRequest,
  type PpmRequest,
} from "@/lib/api";

function formatCLP(value: string | number): string {
  const n = typeof value === "string" ? Number(value) : value;
  return new Intl.NumberFormat("es-CL", {
    style: "currency",
    currency: "CLP",
    maximumFractionDigits: 0,
  }).format(n);
}

function ResultBox({ result }: { result: CalcResponse }) {
  const t = useTranslations("calc.common");
  return (
    <div className="mt-4 space-y-2 rounded-md border border-border bg-muted/40 p-4">
      <div>
        <p className="text-xs uppercase text-muted-foreground">
          {t("result")}
        </p>
        <p className="font-mono text-2xl">{formatCLP(result.value)}</p>
      </div>
      <div>
        <p className="text-xs uppercase text-muted-foreground">
          {t("fuente")}
        </p>
        <p className="text-xs text-muted-foreground">{result.fuente_legal}</p>
      </div>
      <p className="rounded border border-yellow-300 bg-yellow-50 p-2 text-xs text-yellow-900">
        {result.disclaimer}
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// IDPC card
// ---------------------------------------------------------------------------

const idpcSchema = z.object({
  regimen: z.enum(["14_a", "14_d_3", "14_d_8"]),
  tax_year: z.coerce.number().int().min(2024).max(2030),
  rli: z.coerce.number().min(0),
});

function IdpcCard() {
  const t = useTranslations("calc.idpc");
  const tCommon = useTranslations("calc.common");
  const form = useForm<z.infer<typeof idpcSchema>>({
    resolver: zodResolver(idpcSchema),
    defaultValues: { regimen: "14_a", tax_year: 2026, rli: 50_000_000 },
  });
  const mutation = useMutation({
    mutationFn: (req: IdpcRequest) =>
      fetchApiClient<CalcResponse>("/api/calc/idpc", {
        method: "POST",
        body: JSON.stringify(req),
      }),
    onError: (err) =>
      toast.error(err instanceof ApiError ? err.detail : String(err)),
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">{t("title")}</CardTitle>
        <CardDescription>14 A · 14 D N°3 · 14 D N°8</CardDescription>
      </CardHeader>
      <CardContent>
        <Form {...form}>
          <form
            onSubmit={form.handleSubmit((v) =>
              mutation.mutate({
                regimen: v.regimen,
                tax_year: v.tax_year,
                rli: String(v.rli),
              }),
            )}
            className="space-y-4"
          >
            <FormField
              control={form.control}
              name="regimen"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t("regimen")}</FormLabel>
                  <FormControl>
                    <select
                      {...field}
                      className="flex h-10 w-full rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                    >
                      <option value="14_a">{t("regimenOptions.14_a")}</option>
                      <option value="14_d_3">
                        {t("regimenOptions.14_d_3")}
                      </option>
                      <option value="14_d_8">
                        {t("regimenOptions.14_d_8")}
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
                  <FormLabel>{tCommon("year")}</FormLabel>
                  <FormControl>
                    <Input type="number" min={2024} max={2030} {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="rli"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t("rli")}</FormLabel>
                  <FormControl>
                    <Input type="number" min={0} {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <Button
              type="submit"
              className="w-full"
              disabled={mutation.isPending}
            >
              {mutation.isPending ? tCommon("submitting") : tCommon("submit")}
            </Button>
            {mutation.data && <ResultBox result={mutation.data} />}
          </form>
        </Form>
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// IGC card
// ---------------------------------------------------------------------------

const igcSchema = z.object({
  tax_year: z.coerce.number().int().min(2024).max(2030),
  base_pesos: z.coerce.number().min(0),
});

function IgcCard() {
  const t = useTranslations("calc.igc");
  const tCommon = useTranslations("calc.common");
  const form = useForm<z.infer<typeof igcSchema>>({
    resolver: zodResolver(igcSchema),
    defaultValues: { tax_year: 2026, base_pesos: 33_380_160 },
  });
  const mutation = useMutation({
    mutationFn: (req: IgcRequest) =>
      fetchApiClient<CalcResponse>("/api/calc/igc", {
        method: "POST",
        body: JSON.stringify(req),
      }),
    onError: (err) =>
      toast.error(err instanceof ApiError ? err.detail : String(err)),
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">{t("title")}</CardTitle>
        <CardDescription>art. 52 LIR — 8 tramos en UTA</CardDescription>
      </CardHeader>
      <CardContent>
        <Form {...form}>
          <form
            onSubmit={form.handleSubmit((v) =>
              mutation.mutate({
                tax_year: v.tax_year,
                base_pesos: String(v.base_pesos),
              }),
            )}
            className="space-y-4"
          >
            <FormField
              control={form.control}
              name="tax_year"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{tCommon("year")}</FormLabel>
                  <FormControl>
                    <Input type="number" min={2024} max={2030} {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="base_pesos"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t("base")}</FormLabel>
                  <FormControl>
                    <Input type="number" min={0} {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <Button
              type="submit"
              className="w-full"
              disabled={mutation.isPending}
            >
              {mutation.isPending ? tCommon("submitting") : tCommon("submit")}
            </Button>
            {mutation.data && <ResultBox result={mutation.data} />}
          </form>
        </Form>
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// PPM card
// ---------------------------------------------------------------------------

const ppmSchema = z.object({
  regimen: z.enum(["14_d_3", "14_d_8"]),
  tax_year: z.coerce.number().int().min(2024).max(2030),
  ingresos_mes_pesos: z.coerce.number().min(0),
  ingresos_anio_anterior_uf: z.coerce.number().min(0),
});

function PpmCard() {
  const t = useTranslations("calc.ppm");
  const tCommon = useTranslations("calc.common");
  const form = useForm<z.infer<typeof ppmSchema>>({
    resolver: zodResolver(ppmSchema),
    defaultValues: {
      regimen: "14_d_3",
      tax_year: 2026,
      ingresos_mes_pesos: 10_000_000,
      ingresos_anio_anterior_uf: 30_000,
    },
  });
  const mutation = useMutation({
    mutationFn: (req: PpmRequest) =>
      fetchApiClient<CalcResponse>("/api/calc/ppm", {
        method: "POST",
        body: JSON.stringify(req),
      }),
    onError: (err) =>
      toast.error(err instanceof ApiError ? err.detail : String(err)),
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">{t("title")}</CardTitle>
        <CardDescription>14 D N°3 · 14 D N°8</CardDescription>
      </CardHeader>
      <CardContent>
        <Form {...form}>
          <form
            onSubmit={form.handleSubmit((v) =>
              mutation.mutate({
                regimen: v.regimen,
                tax_year: v.tax_year,
                ingresos_mes_pesos: String(v.ingresos_mes_pesos),
                ingresos_anio_anterior_uf: String(
                  v.ingresos_anio_anterior_uf,
                ),
              }),
            )}
            className="space-y-4"
          >
            <FormField
              control={form.control}
              name="regimen"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t("regimen")}</FormLabel>
                  <FormControl>
                    <select
                      {...field}
                      className="flex h-10 w-full rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                    >
                      <option value="14_d_3">
                        {t("regimenOptions.14_d_3")}
                      </option>
                      <option value="14_d_8">
                        {t("regimenOptions.14_d_8")}
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
                  <FormLabel>{tCommon("year")}</FormLabel>
                  <FormControl>
                    <Input type="number" min={2024} max={2030} {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="ingresos_mes_pesos"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t("ingresosMes")}</FormLabel>
                  <FormControl>
                    <Input type="number" min={0} {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="ingresos_anio_anterior_uf"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t("ingresosAnio")}</FormLabel>
                  <FormControl>
                    <Input type="number" min={0} {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <Button
              type="submit"
              className="w-full"
              disabled={mutation.isPending}
            >
              {mutation.isPending ? tCommon("submitting") : tCommon("submit")}
            </Button>
            {mutation.data && <ResultBox result={mutation.data} />}
          </form>
        </Form>
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Top-level export
// ---------------------------------------------------------------------------

export function CalcPlayground() {
  return (
    <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
      <IdpcCard />
      <IgcCard />
      <PpmCard />
    </div>
  );
}
