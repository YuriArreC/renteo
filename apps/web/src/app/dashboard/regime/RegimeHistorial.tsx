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
  fetchApiClient,
  type RecomendacionListResponse,
} from "@/lib/api";

const REGIMEN_LABEL: Record<string, string> = {
  "14_a": "14 A",
  "14_d_3": "14 D N°3",
  "14_d_8": "14 D N°8",
  renta_presunta: "Renta presunta",
};

function formatCLP(value: string | number | null): string {
  if (value === null) return "—";
  const n = typeof value === "string" ? Number(value) : value;
  return new Intl.NumberFormat("es-CL", {
    style: "currency",
    currency: "CLP",
    maximumFractionDigits: 0,
  }).format(n);
}

function formatDate(iso: string): string {
  return new Intl.DateTimeFormat("es-CL", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(iso));
}

export function RegimeHistorial() {
  const t = useTranslations("regime.historial");

  const query = useQuery<RecomendacionListResponse>({
    queryKey: ["regime-recomendaciones"],
    queryFn: () =>
      fetchApiClient<RecomendacionListResponse>(
        "/api/regime/recomendaciones",
      ),
  });

  if (query.isPending) return null;

  const items = query.data?.recomendaciones ?? [];

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{t("header")}</CardTitle>
      </CardHeader>
      <CardContent>
        {items.length === 0 ? (
          <p className="text-xs text-muted-foreground">{t("empty")}</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border bg-muted/40 text-left">
                  <th className="p-3 font-medium">{t("year")}</th>
                  <th className="p-3 font-medium">{t("from")}</th>
                  <th className="p-3 font-medium" />
                  <th className="p-3 font-medium">{t("to")}</th>
                  <th className="p-3 text-right font-medium">{t("ahorro")}</th>
                  <th className="p-3 font-medium">{t("createdAt")}</th>
                  <th className="p-3 font-medium">{t("version")}</th>
                </tr>
              </thead>
              <tbody>
                {items.map((r) => (
                  <tr key={r.id} className="border-b border-border">
                    <td className="p-3">{r.tax_year}</td>
                    <td className="p-3">
                      {REGIMEN_LABEL[r.regimen_actual] ?? r.regimen_actual}
                    </td>
                    <td className="p-3 text-muted-foreground">
                      {t("arrow")}
                    </td>
                    <td className="p-3 font-medium">
                      {REGIMEN_LABEL[r.regimen_recomendado] ??
                        r.regimen_recomendado}
                    </td>
                    <td className="p-3 text-right font-mono">
                      {formatCLP(r.ahorro_estimado_clp)}
                    </td>
                    <td className="p-3 text-xs text-muted-foreground">
                      {formatDate(r.created_at)}
                    </td>
                    <td className="p-3 text-xs text-muted-foreground">
                      {t("diagnosticVersion", {
                        disclaimer: r.disclaimer_version,
                        engine: r.engine_version,
                      })}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
