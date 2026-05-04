"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";

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
  type DryRunResponse,
  fetchApiClient,
  type RuleSetDetail,
  type RuleStatus,
} from "@/lib/api";

function formatCLP(value: string): string {
  const n = Number(value);
  return new Intl.NumberFormat("es-CL", {
    style: "currency",
    currency: "CLP",
    maximumFractionDigits: 0,
  }).format(n);
}

export function RuleDetail({ ruleId }: { ruleId: string }) {
  const tDetail = useTranslations("adminRules.detail");
  const tStatus = useTranslations("adminRules.statusLabel");
  const queryClient = useQueryClient();

  const detailQuery = useQuery<RuleSetDetail>({
    queryKey: ["admin-rule", ruleId],
    queryFn: () =>
      fetchApiClient<RuleSetDetail>(`/api/admin/rules/${ruleId}`),
  });

  const dryRunMutation = useMutation({
    mutationFn: () =>
      fetchApiClient<DryRunResponse>(
        `/api/admin/rules/${ruleId}/dry-run`,
        { method: "POST" },
      ),
    onError: (err) =>
      toast.error(err instanceof ApiError ? err.detail : String(err)),
  });

  const actionMutation = useMutation({
    mutationFn: (action: "sign-contador" | "publish" | "deprecate") =>
      fetchApiClient(`/api/admin/rules/${ruleId}/${action}`, {
        method: "POST",
      }).then(() => action),
    onSuccess: (action) => {
      toast.success(tDetail("actionToast", { action }));
      queryClient.invalidateQueries({ queryKey: ["admin-rule", ruleId] });
      dryRunMutation.reset();
    },
    onError: (err) =>
      toast.error(err instanceof ApiError ? err.detail : String(err)),
  });

  if (detailQuery.isPending) return null;
  if (detailQuery.isError) {
    return (
      <p className="text-sm text-destructive">
        {detailQuery.error instanceof ApiError
          ? detailQuery.error.detail
          : String(detailQuery.error)}
      </p>
    );
  }

  const rule = detailQuery.data;
  const isEligibility = rule.domain === "regime_eligibility";
  const dryRun = dryRunMutation.data;

  const availableActions: Array<{
    id: "sign-contador" | "publish" | "deprecate";
    label: string;
    variant?: "default" | "outline" | "ghost";
  }> = [];
  if (rule.status === "draft") {
    availableActions.push({
      id: "sign-contador",
      label: tDetail("signContador"),
    });
  }
  if (rule.status === "pending_approval") {
    availableActions.push({ id: "publish", label: tDetail("publish") });
  }
  if (rule.status === "published") {
    availableActions.push({
      id: "deprecate",
      label: tDetail("deprecate"),
      variant: "outline",
    });
  }

  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-3">
            <span className="font-mono">
              {rule.domain}/{rule.key}
            </span>
            <span className="rounded bg-muted px-2 py-0.5 text-xs font-mono">
              v{rule.version}
            </span>
            <StatusBadge
              status={rule.status}
              label={tStatus(rule.status)}
            />
          </CardTitle>
          <p className="text-xs text-muted-foreground">
            {rule.vigencia_desde}
            {rule.vigencia_hasta ? ` → ${rule.vigencia_hasta}` : " → ∞"}
          </p>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <h3 className="mb-2 text-xs font-semibold uppercase text-muted-foreground">
              {tDetail("rulesBody")}
            </h3>
            <pre className="overflow-x-auto rounded border border-border bg-muted/40 p-3 text-xs">
              {JSON.stringify(rule.rules, null, 2)}
            </pre>
          </div>
          <div>
            <h3 className="mb-2 text-xs font-semibold uppercase text-muted-foreground">
              {tDetail("fuenteLegal")}
            </h3>
            <pre className="overflow-x-auto rounded border border-border bg-muted/40 p-3 text-xs">
              {JSON.stringify(rule.fuente_legal, null, 2)}
            </pre>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">{tDetail("actions")}</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-3">
          {availableActions.length === 0 && (
            <p className="text-xs text-muted-foreground">
              {tDetail("noActions")}
            </p>
          )}
          {availableActions.map((a) => (
            <Button
              key={a.id}
              variant={a.variant ?? "default"}
              onClick={() => actionMutation.mutate(a.id)}
              disabled={actionMutation.isPending}
            >
              {a.label}
            </Button>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">{tDetail("dryRun")}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {!isEligibility ? (
            <p className="text-xs text-muted-foreground">
              {tDetail("dryRunUnsupportedDomain")}
            </p>
          ) : (
            <>
              <Button
                size="sm"
                variant="outline"
                onClick={() => dryRunMutation.mutate()}
                disabled={dryRunMutation.isPending}
              >
                {dryRunMutation.isPending
                  ? tDetail("dryRunRunning")
                  : tDetail("dryRun")}
              </Button>
              {dryRun && (
                <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-5">
                  <Stat
                    label={tDetail("dryRun_evaluadas")}
                    value={String(dryRun.evaluadas)}
                  />
                  <Stat
                    label={tDetail("dryRun_pasaban")}
                    value={String(dryRun.pasaban_antes)}
                  />
                  <Stat
                    label={tDetail("dryRun_pasan")}
                    value={String(dryRun.pasan_ahora)}
                  />
                  <Stat
                    label={tDetail("dryRun_cambian")}
                    value={String(dryRun.cambian_elegibilidad)}
                    highlight={dryRun.cambian_elegibilidad > 0}
                  />
                  <Stat
                    label={tDetail("dryRun_delta")}
                    value={formatCLP(dryRun.delta_ahorro_total_clp)}
                    highlight={Number(dryRun.delta_ahorro_total_clp) !== 0}
                  />
                </div>
              )}
              {dryRun && (
                <p className="text-xs text-muted-foreground">{dryRun.nota}</p>
              )}
            </>
          )}
        </CardContent>
      </Card>
    </>
  );
}

function Stat({
  label,
  value,
  highlight = false,
}: {
  label: string;
  value: string;
  highlight?: boolean;
}) {
  return (
    <div
      className={`rounded-md p-3 ${
        highlight ? "bg-yellow-50" : "bg-muted/40"
      }`}
    >
      <p className="text-xs uppercase text-muted-foreground">{label}</p>
      <p className="mt-1 font-mono text-lg font-semibold">{value}</p>
    </div>
  );
}

function StatusBadge({
  status,
  label,
}: {
  status: RuleStatus;
  label: string;
}) {
  const tone =
    status === "published"
      ? "bg-green-100 text-green-900"
      : status === "pending_approval"
        ? "bg-yellow-100 text-yellow-900"
        : status === "deprecated"
          ? "bg-muted text-muted-foreground line-through"
          : "bg-blue-100 text-blue-900";
  return (
    <span className={`rounded px-2 py-0.5 text-xs ${tone}`}>{label}</span>
  );
}
