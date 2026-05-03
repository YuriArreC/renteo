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
  type ComparadorRequest,
  type ComparadorResponse,
  fetchApiClient,
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
  tax_year: z.coerce.number().int().min(2024).max(2030),
  rli: z.coerce.number().min(0),
  retiros_pesos: z.coerce.number().min(0),
});

type FormValues = z.infer<typeof schema>;

export function ComparadorRegimen() {
  const t = useTranslations("comparador");
  const tForm = useTranslations("comparador.form");
  const tTable = useTranslations("comparador.table");

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      tax_year: 2026,
      rli: 30_000_000,
      retiros_pesos: 10_000_000,
    },
  });

  const mutation = useMutation({
    mutationFn: (req: ComparadorRequest) =>
      fetchApiClient<ComparadorResponse>("/api/calc/comparador-regimen", {
        method: "POST",
        body: JSON.stringify(req),
      }),
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
                  tax_year: v.tax_year,
                  rli: String(v.rli),
                  retiros_pesos: String(v.retiros_pesos),
                }),
              )}
              className="grid gap-5 md:grid-cols-3"
            >
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
                name="rli"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{tForm("rli")}</FormLabel>
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
                name="retiros_pesos"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{tForm("retiros")}</FormLabel>
                    <FormControl>
                      <Input type="number" min={0} {...field} />
                    </FormControl>
                    <FormDescription>{tForm("retirosHint")}</FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <div className="md:col-span-3">
                <Button
                  type="submit"
                  className="w-full md:w-auto"
                  disabled={mutation.isPending}
                  size="lg"
                >
                  {mutation.isPending
                    ? tForm("submitting")
                    : tForm("submit")}
                </Button>
              </div>
            </form>
          </Form>
        </CardContent>
      </Card>

      {mutation.data && (
        <>
          <Card>
            <CardContent className="overflow-x-auto p-0">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border bg-muted/40 text-left">
                    <th className="p-4 font-medium">{tTable("regimen")}</th>
                    <th className="p-4 text-right font-medium">
                      {tTable("idpc")}
                    </th>
                    <th className="p-4 text-right font-medium">
                      {tTable("igc")}
                    </th>
                    <th className="p-4 text-right font-medium">
                      {tTable("total")}
                    </th>
                    <th className="p-4 text-right font-medium">
                      {tTable("ahorro")}
                    </th>
                    <th className="p-4 text-center font-medium">
                      {tTable("recomendado")}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {mutation.data.scenarios.map((s) => (
                    <tr
                      key={s.regimen}
                      className={`border-b border-border ${
                        s.es_recomendado ? "bg-primary/5" : ""
                      }`}
                    >
                      <td className="p-4">
                        <div className="font-medium">{s.label}</div>
                        {s.es_transitoria && (
                          <span className="mt-1 inline-block rounded bg-yellow-100 px-2 py-0.5 text-xs text-yellow-900">
                            {t("transitoria")}
                          </span>
                        )}
                      </td>
                      <td className="p-4 text-right font-mono">
                        {formatCLP(s.idpc)}
                      </td>
                      <td className="p-4 text-right font-mono">
                        {formatCLP(s.igc_dueno)}
                      </td>
                      <td className="p-4 text-right font-mono font-semibold">
                        {formatCLP(s.carga_total)}
                      </td>
                      <td
                        className={`p-4 text-right font-mono ${
                          Number(s.ahorro_vs_14a) > 0
                            ? "text-green-700"
                            : Number(s.ahorro_vs_14a) < 0
                              ? "text-destructive"
                              : "text-muted-foreground"
                        }`}
                      >
                        {Number(s.ahorro_vs_14a) === 0
                          ? "—"
                          : formatCLP(s.ahorro_vs_14a)}
                      </td>
                      <td className="p-4 text-center">
                        {s.es_recomendado && (
                          <span className="inline-block rounded-full bg-primary px-3 py-1 text-xs font-medium text-primary-foreground">
                            ★
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">{t("notesHeader")}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {mutation.data.scenarios.map((s) => (
                <div key={s.regimen} className="border-l-2 border-border pl-4">
                  <div className="text-sm font-medium">{s.label}</div>
                  <div className="mt-1 text-xs text-muted-foreground">
                    <strong>Fundamento:</strong> {s.fuente_legal}
                  </div>
                  {s.nota && (
                    <p className="mt-2 text-xs text-muted-foreground">
                      {s.nota}
                    </p>
                  )}
                </div>
              ))}
            </CardContent>
          </Card>

          <p className="rounded border border-yellow-300 bg-yellow-50 p-3 text-xs text-yellow-900">
            {mutation.data.disclaimer}
          </p>
        </>
      )}
    </div>
  );
}
