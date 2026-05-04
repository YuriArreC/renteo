"use client";

import { useMutation } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "@/components/ui/sonner";
import {
  ApiError,
  type BatchDiagnoseRequest,
  type BatchDiagnoseResponse,
  type CarteraEmpresaItem,
  fetchApiClient,
} from "@/lib/api";

const SECTORS = [
  "comercio",
  "servicios",
  "agricola",
  "transporte",
  "mineria",
  "otro",
] as const;

function formatCLP(value: string | number): string {
  const n = typeof value === "string" ? Number(value) : value;
  return new Intl.NumberFormat("es-CL", {
    style: "currency",
    currency: "CLP",
    maximumFractionDigits: 0,
  }).format(n);
}

const REGIMEN_LABEL: Record<string, string> = {
  "14_a": "14 A",
  "14_d_3": "14 D N°3",
  "14_d_8": "14 D N°8",
};

export function BatchDiagnose({
  empresas,
}: {
  empresas: CarteraEmpresaItem[];
}) {
  const t = useTranslations("cartera.batch");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [open, setOpen] = useState(false);
  const [taxYear, setTaxYear] = useState(2026);
  const [ingresosProm, setIngresosProm] = useState(30000);
  const [ingresosMax, setIngresosMax] = useState(40000);
  const [capital, setCapital] = useState(5000);
  const [pctPasivos, setPctPasivos] = useState(0.1);
  const [ventas, setVentas] = useState(30000);
  const [sector, setSector] = useState<(typeof SECTORS)[number]>(
    "comercio",
  );
  const [rliProy, setRliProy] = useState(1000);
  const [planRetiros, setPlanRetiros] = useState(0.3);
  const [duenosChile, setDuenosChile] = useState(true);
  const [participaciones, setParticipaciones] = useState(false);

  const mutation = useMutation({
    mutationFn: (req: BatchDiagnoseRequest) =>
      fetchApiClient<BatchDiagnoseResponse>(
        "/api/cartera/batch-diagnose",
        {
          method: "POST",
          body: JSON.stringify(req),
        },
      ),
    onError: (err) =>
      toast.error(err instanceof ApiError ? err.detail : String(err)),
  });

  const toggle = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const onSubmit = () => {
    if (selected.size === 0) {
      toast.error(t("needSelection"));
      return;
    }
    mutation.mutate({
      empresa_ids: Array.from(selected),
      inputs: {
        tax_year: taxYear,
        ingresos_promedio_3a_uf: String(ingresosProm),
        ingresos_max_anual_uf: String(ingresosMax),
        capital_efectivo_inicial_uf: String(capital),
        pct_ingresos_pasivos: String(pctPasivos),
        todos_duenos_personas_naturales_chile: duenosChile,
        participacion_empresas_no_14d_sobre_10pct: participaciones,
        sector,
        ventas_anuales_uf: String(ventas),
        rli_proyectada_anual_uf: String(rliProy),
        plan_retiros_pct: String(planRetiros),
      },
    });
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-4">
        <p className="text-xs text-muted-foreground">
          {t("selected", { count: selected.size })}
        </p>
        <Button
          size="sm"
          onClick={() => setOpen(!open)}
          disabled={selected.size === 0}
        >
          {t("trigger")}
        </Button>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-border bg-muted/40 text-left">
              <th className="p-2"></th>
              <th className="p-2 font-medium">{t("resultEmpresa")}</th>
            </tr>
          </thead>
          <tbody>
            {empresas.map((e) => (
              <tr key={e.empresa_id} className="border-b border-border">
                <td className="p-2">
                  <Checkbox
                    checked={selected.has(e.empresa_id)}
                    onChange={() => toggle(e.empresa_id)}
                  />
                </td>
                <td className="p-2">
                  {e.razon_social}{" "}
                  <span className="text-xs text-muted-foreground">
                    ({e.rut})
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {open && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">{t("title")}</CardTitle>
            <p className="text-xs text-muted-foreground">
              {t("subtitle", { count: selected.size })}
            </p>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 md:grid-cols-3">
              <div className="space-y-1">
                <Label className="text-xs">{t("year")}</Label>
                <Input
                  type="number"
                  min={2024}
                  max={2030}
                  value={taxYear}
                  onChange={(e) => setTaxYear(Number(e.target.value))}
                />
              </div>
              <div className="space-y-1">
                <Label className="text-xs">{t("rliProyectada")}</Label>
                <Input
                  type="number"
                  min={0}
                  value={rliProy}
                  onChange={(e) => setRliProy(Number(e.target.value))}
                />
              </div>
              <div className="space-y-1">
                <Label className="text-xs">{t("planRetiros")}</Label>
                <Input
                  type="number"
                  min={0}
                  max={1}
                  step={0.05}
                  value={planRetiros}
                  onChange={(e) => setPlanRetiros(Number(e.target.value))}
                />
              </div>
              <div className="space-y-1">
                <Label className="text-xs">{t("ingresosProm")}</Label>
                <Input
                  type="number"
                  min={0}
                  value={ingresosProm}
                  onChange={(e) => setIngresosProm(Number(e.target.value))}
                />
              </div>
              <div className="space-y-1">
                <Label className="text-xs">{t("ingresosMax")}</Label>
                <Input
                  type="number"
                  min={0}
                  value={ingresosMax}
                  onChange={(e) => setIngresosMax(Number(e.target.value))}
                />
              </div>
              <div className="space-y-1">
                <Label className="text-xs">{t("capital")}</Label>
                <Input
                  type="number"
                  min={0}
                  value={capital}
                  onChange={(e) => setCapital(Number(e.target.value))}
                />
              </div>
              <div className="space-y-1">
                <Label className="text-xs">{t("ventas")}</Label>
                <Input
                  type="number"
                  min={0}
                  value={ventas}
                  onChange={(e) => setVentas(Number(e.target.value))}
                />
              </div>
              <div className="space-y-1">
                <Label className="text-xs">{t("pctPasivos")}</Label>
                <Input
                  type="number"
                  min={0}
                  max={1}
                  step={0.05}
                  value={pctPasivos}
                  onChange={(e) => setPctPasivos(Number(e.target.value))}
                />
              </div>
              <div className="space-y-1">
                <Label className="text-xs">{t("sector")}</Label>
                <select
                  value={sector}
                  onChange={(e) =>
                    setSector(e.target.value as typeof sector)
                  }
                  className="flex h-10 w-full rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                >
                  {SECTORS.map((s) => (
                    <option key={s} value={s}>
                      {s}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <label className="flex items-center gap-2 text-xs">
              <Checkbox
                checked={duenosChile}
                onChange={(e) => setDuenosChile(e.target.checked)}
              />
              {t("duenos")}
            </label>
            <label className="flex items-center gap-2 text-xs">
              <Checkbox
                checked={participaciones}
                onChange={(e) =>
                  setParticipaciones(e.target.checked)
                }
              />
              {t("participaciones")}
            </label>

            <div className="flex gap-2">
              <Button onClick={onSubmit} disabled={mutation.isPending}>
                {mutation.isPending ? t("submitting") : t("submit")}
              </Button>
              <Button
                variant="outline"
                onClick={() => setOpen(false)}
                disabled={mutation.isPending}
              >
                {t("cancel")}
              </Button>
            </div>

            {mutation.data && (
              <div className="space-y-3 border-t border-border pt-4">
                <p className="text-xs font-semibold">
                  {t("resultsKpi", {
                    creadas: mutation.data.creadas,
                    fallidas: mutation.data.fallidas,
                  })}
                </p>
                <p className="text-xs text-muted-foreground">
                  Δ ahorro 3a agregado:{" "}
                  {formatCLP(mutation.data.ahorro_total_clp)}
                </p>
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-border bg-muted/40 text-left">
                      <th className="p-2">{t("resultEmpresa")}</th>
                      <th className="p-2">{t("resultActual")}</th>
                      <th className="p-2">{t("resultRec")}</th>
                      <th className="p-2 text-right">
                        {t("resultAhorro")}
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {mutation.data.items.map((it) => (
                      <tr
                        key={it.empresa_id}
                        className="border-b border-border"
                      >
                        <td className="p-2">{it.razon_social}</td>
                        <td className="p-2">
                          {REGIMEN_LABEL[it.regimen_actual] ??
                            it.regimen_actual}
                        </td>
                        <td className="p-2 font-medium">
                          {REGIMEN_LABEL[it.regimen_recomendado] ??
                            it.regimen_recomendado}
                        </td>
                        <td className="p-2 text-right font-mono text-green-700">
                          {formatCLP(it.ahorro_estimado_clp)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {mutation.data.failures.length > 0 && (
                  <div className="rounded border border-destructive/40 bg-destructive/5 p-2 text-xs text-destructive">
                    <p className="mb-1 font-semibold">
                      {t("failureHeader")}
                    </p>
                    <ul className="space-y-1">
                      {mutation.data.failures.map((f) => (
                        <li key={f.empresa_id} className="font-mono">
                          {f.empresa_id}: {f.error}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
