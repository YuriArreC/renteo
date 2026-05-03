"use client";

import { useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { fetchApiClient, type ScenarioListResponse } from "@/lib/api";

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

function formatDate(iso: string): string {
  return new Intl.DateTimeFormat("es-CL", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(iso));
}

export function ScenarioHistorial() {
  const t = useTranslations("simulator.historial");
  const router = useRouter();
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const query = useQuery<ScenarioListResponse>({
    queryKey: ["scenario-list"],
    queryFn: () => fetchApiClient<ScenarioListResponse>("/api/scenario/list"),
  });

  const toggle = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else if (next.size < 4) next.add(id);
      return next;
    });
  };

  const goCompare = () => {
    if (selected.size < 2) return;
    const ids = Array.from(selected).join(",");
    router.push(`/dashboard/simulator/comparar?ids=${ids}`);
  };

  if (query.isPending) {
    return null;
  }
  const items = query.data?.scenarios ?? [];
  if (items.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base">{t("header")}</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-xs text-muted-foreground">{t("empty")}</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-4">
        <CardTitle className="text-base">{t("header")}</CardTitle>
        <Button
          size="sm"
          onClick={goCompare}
          disabled={selected.size < 2}
        >
          {t("compareSelected", { count: selected.size })}
        </Button>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-xs text-muted-foreground">{t("compareHint")}</p>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-muted/40 text-left">
                <th className="p-3 font-medium" aria-label={t("select")}></th>
                <th className="p-3 font-medium">{t("name")}</th>
                <th className="p-3 font-medium">{t("year")}</th>
                <th className="p-3 font-medium">{t("regimen")}</th>
                <th className="p-3 text-right font-medium">
                  {t("cargaSimulada")}
                </th>
                <th className="p-3 text-right font-medium">{t("ahorro")}</th>
                <th className="p-3 text-center font-medium">
                  {t("recomendado")}
                </th>
                <th className="p-3 font-medium">{t("createdAt")}</th>
              </tr>
            </thead>
            <tbody>
              {items.map((s) => {
                const ahorroNum = Number(s.ahorro_total);
                return (
                  <tr
                    key={s.id}
                    className={`border-b border-border ${
                      s.es_recomendado ? "bg-primary/5" : ""
                    }`}
                  >
                    <td className="p-3">
                      <Checkbox
                        checked={selected.has(s.id)}
                        onChange={() => toggle(s.id)}
                        aria-label={t("select")}
                      />
                    </td>
                    <td className="p-3 font-medium">{s.nombre}</td>
                    <td className="p-3">{s.tax_year}</td>
                    <td className="p-3">
                      {REGIMEN_LABEL[s.regimen] ?? s.regimen}
                    </td>
                    <td className="p-3 text-right font-mono">
                      {formatCLP(s.carga_simulada)}
                    </td>
                    <td
                      className={`p-3 text-right font-mono ${
                        ahorroNum > 0
                          ? "text-green-700"
                          : ahorroNum < 0
                            ? "text-destructive"
                            : "text-muted-foreground"
                      }`}
                    >
                      {ahorroNum === 0 ? "—" : formatCLP(s.ahorro_total)}
                    </td>
                    <td className="p-3 text-center">
                      {s.es_recomendado && (
                        <span className="inline-block rounded-full bg-primary px-2 py-0.5 text-xs font-medium text-primary-foreground">
                          ★
                        </span>
                      )}
                    </td>
                    <td className="p-3 text-xs text-muted-foreground">
                      {formatDate(s.created_at)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}
