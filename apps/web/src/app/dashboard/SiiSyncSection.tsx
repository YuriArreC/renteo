"use client";

import { useMutation, useQueries, useQueryClient } from "@tanstack/react-query";
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
  type EmpresaResponse,
  type SyncSiiResponse,
  type SyncStatusResponse,
  fetchApiClient,
} from "@/lib/api";

function fmtDate(iso: string | null): string | null {
  if (!iso) return null;
  try {
    return new Date(iso).toLocaleString("es-CL");
  } catch {
    return iso;
  }
}

export function SiiSyncSection({
  empresas,
}: {
  empresas: EmpresaResponse[];
}) {
  const t = useTranslations("dashboard.sii");
  const queryClient = useQueryClient();
  const [months, setMonths] = useState<Record<string, number>>({});

  const statusQueries = useQueries({
    queries: empresas.map((e) => ({
      queryKey: ["sii-status", e.id],
      queryFn: () =>
        fetchApiClient<SyncStatusResponse>(
          `/api/empresas/${e.id}/sync-status`,
        ),
    })),
  });

  const sync = useMutation({
    mutationFn: ({
      empresaId,
      monthsValue,
    }: {
      empresaId: string;
      monthsValue: number;
    }) =>
      fetchApiClient<SyncSiiResponse>(
        `/api/empresas/${empresaId}/sync-sii`,
        {
          method: "POST",
          body: JSON.stringify({ months: monthsValue }),
        },
      ),
    onSuccess: (data, vars) => {
      toast.success(
        t("syncOk", {
          rows: data.rcv_rows_inserted,
          provider: data.provider,
        }),
      );
      queryClient.invalidateQueries({
        queryKey: ["sii-status", vars.empresaId],
      });
    },
    onError: (err) =>
      toast.error(
        t("syncFail", {
          error: err instanceof ApiError ? err.detail : String(err),
        }),
      ),
  });

  if (empresas.length === 0) return null;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{t("header")}</CardTitle>
        <p className="text-xs text-muted-foreground">{t("subtitle")}</p>
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-muted/40 text-left">
                <th className="p-3 font-medium">{t("empresa")}</th>
                <th className="p-3 font-medium">{t("lastSync")}</th>
                <th className="p-3 font-medium">{t("rcvRows")}</th>
                <th className="p-3 font-medium">{t("monthsLabel")}</th>
                <th className="p-3"></th>
              </tr>
            </thead>
            <tbody>
              {empresas.map((e, idx) => {
                const status = statusQueries[idx]?.data;
                const lastSyncText = status?.last_sync_at
                  ? fmtDate(status.last_sync_at)
                  : t("neverSynced");
                const monthsValue = months[e.id] ?? 12;
                const isPending =
                  sync.isPending && sync.variables?.empresaId === e.id;
                return (
                  <tr key={e.id} className="border-b border-border">
                    <td className="p-3">
                      {e.razon_social}
                      <span className="ml-2 font-mono text-xs text-muted-foreground">
                        {e.rut}
                      </span>
                    </td>
                    <td className="p-3 text-xs">
                      {lastSyncText}
                      {status?.last_sync_provider && (
                        <span className="ml-2 text-muted-foreground">
                          ({status.last_sync_provider})
                        </span>
                      )}
                    </td>
                    <td className="p-3 font-mono text-xs">
                      {status?.rcv_rows_total ?? "—"}
                    </td>
                    <td className="p-3">
                      <Label className="sr-only" htmlFor={`m-${e.id}`}>
                        {t("monthsLabel")}
                      </Label>
                      <Input
                        id={`m-${e.id}`}
                        type="number"
                        min={1}
                        max={24}
                        value={monthsValue}
                        onChange={(ev) =>
                          setMonths((prev) => ({
                            ...prev,
                            [e.id]: Number(ev.target.value),
                          }))
                        }
                        className="h-8 w-20 text-xs"
                      />
                    </td>
                    <td className="p-3 text-right">
                      <Button
                        size="sm"
                        disabled={isPending}
                        onClick={() =>
                          sync.mutate({
                            empresaId: e.id,
                            monthsValue,
                          })
                        }
                      >
                        {isPending ? t("syncing") : t("syncCta")}
                      </Button>
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
