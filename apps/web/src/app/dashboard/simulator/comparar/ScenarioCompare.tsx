"use client";

import { useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";

import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  ApiError,
  type CompareResponse,
  fetchApiClient,
} from "@/lib/api";

const REGIMEN_LABEL: Record<string, string> = {
  "14_a": "14 A",
  "14_d_3": "14 D N°3",
  "14_d_8": "14 D N°8",
};

function formatCLP(value: string | number): string {
  const n = typeof value === "string" ? Number(value) : value;
  return new Intl.NumberFormat("es-CL", {
    style: "currency",
    currency: "CLP",
    maximumFractionDigits: 0,
  }).format(n);
}

export function ScenarioCompare({ ids }: { ids: string[] }) {
  const t = useTranslations("simulator.compare");
  const tSeverity = useTranslations("simulator.severity");

  const query = useQuery<CompareResponse>({
    queryKey: ["scenario-compare", ids],
    queryFn: () =>
      fetchApiClient<CompareResponse>("/api/scenario/compare", {
        method: "POST",
        body: JSON.stringify({ ids }),
      }),
  });

  if (query.isPending) {
    return null;
  }

  if (query.isError) {
    const detail =
      query.error instanceof ApiError
        ? query.error.detail
        : t("loadFailed");
    return (
      <p className="rounded border border-destructive/40 bg-destructive/5 p-4 text-sm text-destructive">
        {detail}
      </p>
    );
  }

  const data = query.data;
  if (!data) return null;

  const cards = data.scenarios;
  const rows = [
    { key: "rli", label: t("rli") },
    { key: "idpc", label: t("idpc") },
    { key: "retiros_total", label: t("retiros") },
    { key: "igc_dueno", label: t("igc") },
    { key: "carga_total", label: t("carga") },
  ] as const;

  type ResultadoKey = (typeof rows)[number]["key"];

  return (
    <div className="space-y-8">
      <Card>
        <CardContent className="overflow-x-auto p-0">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-muted/40 text-left">
                <th className="p-4 font-medium">{t("metric")}</th>
                {cards.map((c) => (
                  <th
                    key={c.id}
                    className="p-4 text-right font-medium"
                  >
                    <div>{c.nombre}</div>
                    <div className="text-xs font-normal text-muted-foreground">
                      {REGIMEN_LABEL[c.regimen] ?? c.regimen} · AT{c.tax_year}
                    </div>
                    {c.es_recomendado && (
                      <span className="mt-1 inline-block rounded-full bg-primary px-2 py-0.5 text-xs font-medium text-primary-foreground">
                        ★
                      </span>
                    )}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.key} className="border-b border-border">
                  <td className="p-4 font-medium">{r.label}</td>
                  {cards.map((c) => (
                    <td
                      key={c.id}
                      className={`p-4 text-right font-mono ${
                        c.es_recomendado ? "bg-primary/5" : ""
                      }`}
                    >
                      {formatCLP(c.simulado[r.key as ResultadoKey])}
                    </td>
                  ))}
                </tr>
              ))}
              <tr className="bg-primary/5">
                <td className="p-4 font-semibold">{t("ahorro")}</td>
                {cards.map((c) => {
                  const n = Number(c.ahorro_total);
                  return (
                    <td
                      key={c.id}
                      className={`p-4 text-right font-mono font-semibold ${
                        n > 0
                          ? "text-green-700"
                          : n < 0
                            ? "text-destructive"
                            : "text-muted-foreground"
                      }`}
                    >
                      {n === 0 ? "—" : formatCLP(c.ahorro_total)}
                    </td>
                  );
                })}
              </tr>
              <tr>
                <td className="p-4 font-medium">{t("palancasHeader")}</td>
                {cards.map((c) => {
                  const aplicadas = c.palancas_aplicadas.filter(
                    (p) => p.aplicada,
                  );
                  return (
                    <td
                      key={c.id}
                      className="p-4 align-top text-xs text-muted-foreground"
                    >
                      {aplicadas.length === 0 ? (
                        <span>{t("noPalancas")}</span>
                      ) : (
                        <ul className="space-y-1">
                          {aplicadas.map((p) => (
                            <li key={p.palanca_id}>
                              · {p.label} ({formatCLP(p.monto_aplicado)})
                            </li>
                          ))}
                        </ul>
                      )}
                    </td>
                  );
                })}
              </tr>
            </tbody>
          </table>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">{t("planHeader")}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {data.plan_accion.length === 0 ? (
            <p className="text-xs text-muted-foreground">{t("planEmpty")}</p>
          ) : (
            <ol className="space-y-4">
              {data.plan_accion.map((item) => (
                <li
                  key={item.palanca_id}
                  className="border-l-2 border-primary/40 pl-4"
                >
                  <div className="text-sm font-medium">{item.label}</div>
                  <p className="mt-1 text-sm">{item.accion}</p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    <strong>Fundamento:</strong> {item.fundamento_legal}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {t("fechaLimite", { fecha: item.fecha_limite })}
                  </p>
                </li>
              ))}
            </ol>
          )}
        </CardContent>
      </Card>

      {cards.some((c) => c.banderas.length > 0) && (
        <Card>
          <CardContent className="space-y-3 p-6">
            {cards
              .flatMap((c) =>
                c.banderas.map((b, idx) => ({
                  ...b,
                  scenarioName: c.nombre,
                  key: `${c.id}-${idx}`,
                })),
              )
              .map((b) => (
                <div
                  key={b.key}
                  className={`rounded border p-3 text-xs ${
                    b.severidad === "block"
                      ? "border-destructive/40 bg-destructive/5 text-destructive"
                      : "border-yellow-300 bg-yellow-50 text-yellow-900"
                  }`}
                >
                  <strong>
                    {tSeverity(b.severidad)} ({b.scenarioName}):
                  </strong>{" "}
                  {b.mensaje}
                </div>
              ))}
          </CardContent>
        </Card>
      )}

      <p className="rounded border border-yellow-300 bg-yellow-50 p-3 text-xs text-yellow-900">
        {data.disclaimer}
      </p>
    </div>
  );
}
