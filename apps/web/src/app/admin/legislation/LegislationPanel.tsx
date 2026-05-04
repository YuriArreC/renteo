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
import { toast } from "@/components/ui/sonner";
import {
  ApiError,
  type LegislativeAlertListResponse,
  type LegislativeAlertPatchRequest,
  type LegislativeAlertSource,
  type LegislativeAlertStatus,
  type LegislativeAlertSummary,
  type WatchdogRunResponse,
  fetchApiClient,
} from "@/lib/api";

const SOURCES: LegislativeAlertSource[] = [
  "dof",
  "sii_circular",
  "sii_oficio",
  "sii_resolucion",
  "presupuestos",
];

const STATUSES: LegislativeAlertStatus[] = [
  "open",
  "dismissed",
  "ignored",
  "drafted",
];

export function LegislationPanel({
  initialRecords,
}: {
  initialRecords: LegislativeAlertSummary[];
}) {
  const t = useTranslations("adminLegislation");
  const queryClient = useQueryClient();

  const [statusFilter, setStatusFilter] =
    useState<LegislativeAlertStatus | "">("");
  const [sourceFilter, setSourceFilter] =
    useState<LegislativeAlertSource | "">("");

  const params = new URLSearchParams();
  if (statusFilter) params.set("status_filter", statusFilter);
  if (sourceFilter) params.set("source", sourceFilter);
  const query = params.toString();
  const url = query
    ? `/api/admin/legislative-alerts?${query}`
    : "/api/admin/legislative-alerts";

  const list = useQuery<LegislativeAlertListResponse>({
    queryKey: ["legislative-alerts", statusFilter, sourceFilter],
    queryFn: () => fetchApiClient<LegislativeAlertListResponse>(url),
    initialData: !statusFilter && !sourceFilter
      ? { records: initialRecords }
      : undefined,
  });

  const runWatchdog = useMutation({
    mutationFn: () =>
      fetchApiClient<WatchdogRunResponse>(
        "/api/admin/legislative-alerts/run",
        { method: "POST" },
      ),
    onSuccess: (data) => {
      toast.success(
        t("ranOk", {
          monitor: data.monitor,
          nuevos: data.nuevos,
          existentes: data.existentes,
        }),
      );
      queryClient.invalidateQueries({
        queryKey: ["legislative-alerts"],
      });
    },
    onError: (err) =>
      toast.error(err instanceof ApiError ? err.detail : String(err)),
  });

  const patch = useMutation({
    mutationFn: ({
      id,
      payload,
    }: {
      id: string;
      payload: LegislativeAlertPatchRequest;
    }) =>
      fetchApiClient(`/api/admin/legislative-alerts/${id}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      }),
    onSuccess: () => {
      toast.success(t("patchedOk"));
      queryClient.invalidateQueries({
        queryKey: ["legislative-alerts"],
      });
    },
    onError: (err) =>
      toast.error(err instanceof ApiError ? err.detail : String(err)),
  });

  const records = list.data?.records ?? [];

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end gap-4">
        <div className="space-y-1">
          <label className="text-xs font-medium">
            {t("filters.status")}
          </label>
          <select
            value={statusFilter}
            onChange={(e) =>
              setStatusFilter(
                e.target.value as LegislativeAlertStatus | "",
              )
            }
            className="flex h-10 w-44 rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          >
            <option value="">{t("filters.any")}</option>
            {STATUSES.map((s) => (
              <option key={s} value={s}>
                {t(`statusLabel.${s}`)}
              </option>
            ))}
          </select>
        </div>
        <div className="space-y-1">
          <label className="text-xs font-medium">
            {t("filters.source")}
          </label>
          <select
            value={sourceFilter}
            onChange={(e) =>
              setSourceFilter(
                e.target.value as LegislativeAlertSource | "",
              )
            }
            className="flex h-10 w-56 rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          >
            <option value="">{t("filters.any")}</option>
            {SOURCES.map((s) => (
              <option key={s} value={s}>
                {t(`sourceLabel.${s}`)}
              </option>
            ))}
          </select>
        </div>
        <div className="ml-auto">
          <Button
            disabled={runWatchdog.isPending}
            onClick={() => runWatchdog.mutate()}
          >
            {runWatchdog.isPending ? t("running") : t("runNow")}
          </Button>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">
            {t("listHeader", { count: records.length })}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {records.length === 0 ? (
            <p className="text-xs text-muted-foreground">
              {t("empty")}
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-border bg-muted/40 text-left">
                    <th className="p-2 font-medium">
                      {t("cols.publication")}
                    </th>
                    <th className="p-2 font-medium">
                      {t("cols.source")}
                    </th>
                    <th className="p-2 font-medium">
                      {t("cols.title")}
                    </th>
                    <th className="p-2 font-medium">
                      {t("cols.target")}
                    </th>
                    <th className="p-2 font-medium">
                      {t("cols.status")}
                    </th>
                    <th className="p-2 font-medium">
                      {t("cols.actions")}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {records.map((r) => (
                    <tr key={r.id} className="border-b border-border">
                      <td className="p-2">
                        {new Date(
                          r.publication_date,
                        ).toLocaleDateString("es-CL")}
                      </td>
                      <td className="p-2">
                        {t(`sourceLabel.${r.source}`)}
                      </td>
                      <td className="p-2">
                        {r.url ? (
                          <a
                            href={r.url}
                            target="_blank"
                            rel="noreferrer"
                            className="text-primary underline"
                          >
                            {r.title}
                          </a>
                        ) : (
                          r.title
                        )}
                        {r.summary && (
                          <p className="mt-0.5 text-[10px] text-muted-foreground">
                            {r.summary}
                          </p>
                        )}
                      </td>
                      <td className="p-2 font-mono text-[10px]">
                        {r.target_domain ?? "—"}
                        {r.target_key ? ` / ${r.target_key}` : ""}
                      </td>
                      <td className="p-2">
                        <span
                          className={`inline-block rounded px-2 py-0.5 text-[10px] uppercase ${
                            r.status === "open"
                              ? "bg-amber-100 text-amber-900"
                              : r.status === "drafted"
                                ? "bg-emerald-100 text-emerald-900"
                                : "bg-muted text-muted-foreground"
                          }`}
                        >
                          {t(`statusLabel.${r.status}`)}
                        </span>
                      </td>
                      <td className="p-2">
                        {r.status === "open" ? (
                          <div className="flex flex-wrap gap-1">
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() =>
                                patch.mutate({
                                  id: r.id,
                                  payload: {
                                    status: "drafted",
                                  },
                                })
                              }
                            >
                              {t("actions.draft")}
                            </Button>
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() =>
                                patch.mutate({
                                  id: r.id,
                                  payload: {
                                    status: "ignored",
                                  },
                                })
                              }
                            >
                              {t("actions.ignore")}
                            </Button>
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() =>
                                patch.mutate({
                                  id: r.id,
                                  payload: {
                                    status: "dismissed",
                                  },
                                })
                              }
                            >
                              {t("actions.dismiss")}
                            </Button>
                          </div>
                        ) : (
                          <span className="text-[10px] text-muted-foreground">
                            {r.review_note ?? "—"}
                          </span>
                        )}
                      </td>
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
