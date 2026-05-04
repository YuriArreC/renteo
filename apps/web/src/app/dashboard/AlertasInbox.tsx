"use client";

import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
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
  type AlertaEstado,
  type AlertaResponse,
  type AlertasListResponse,
  ApiError,
  type EmpresaResponse,
  type EvaluateAlertasRequest,
  type EvaluateAlertasResponse,
  fetchApiClient,
  type UpdateAlertaRequest,
} from "@/lib/api";

export function AlertasInbox({ empresas }: { empresas: EmpresaResponse[] }) {
  const t = useTranslations("alertas");
  const tSev = useTranslations("alertas.severidad");
  const tActions = useTranslations("alertas.actions");
  const queryClient = useQueryClient();

  const [selectedEmpresa, setSelectedEmpresa] = useState<string>(
    empresas[0]?.id ?? "",
  );

  const listQuery = useQuery<AlertasListResponse>({
    queryKey: ["alertas-list"],
    queryFn: () =>
      fetchApiClient<AlertasListResponse>("/api/alertas"),
  });

  const evaluateMutation = useMutation({
    mutationFn: (req: EvaluateAlertasRequest) =>
      fetchApiClient<EvaluateAlertasResponse>("/api/alertas/evaluate", {
        method: "POST",
        body: JSON.stringify(req),
      }),
    onSuccess: (data) => {
      if (data.creadas > 0) {
        toast.success(t("createdToast", { count: data.creadas }));
      } else {
        toast.info(t("noNewToast"));
      }
      queryClient.invalidateQueries({ queryKey: ["alertas-list"] });
    },
    onError: (err) =>
      toast.error(err instanceof ApiError ? err.detail : String(err)),
  });

  const updateMutation = useMutation({
    mutationFn: ({
      id,
      req,
    }: {
      id: string;
      req: UpdateAlertaRequest;
    }) =>
      fetchApiClient<AlertaResponse>(`/api/alertas/${id}`, {
        method: "PATCH",
        body: JSON.stringify(req),
      }),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["alertas-list"] }),
    onError: (err) =>
      toast.error(err instanceof ApiError ? err.detail : String(err)),
  });

  const empresa = empresas.find((e) => e.id === selectedEmpresa);

  const handleEvaluate = () => {
    if (!empresa) {
      toast.error(t("needEmpresa"));
      return;
    }
    const regimen =
      empresa.regimen_actual === "presunta" ||
      empresa.regimen_actual === "desconocido"
        ? "14_d_3"
        : empresa.regimen_actual;
    evaluateMutation.mutate({
      empresa_id: empresa.id,
      tax_year: 2026,
      regimen,
      rli_proyectada_pesos: "30000000",
      retiros_declarados_pesos: "5000000",
      palancas_aplicadas: [],
    });
  };

  const alertas = listQuery.data?.alertas ?? [];

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-4">
        <CardTitle className="text-base">{t("header")}</CardTitle>
        <div className="flex items-center gap-2">
          {empresas.length > 1 && (
            <select
              value={selectedEmpresa}
              onChange={(e) => setSelectedEmpresa(e.target.value)}
              className="h-9 rounded-md border border-input bg-background px-3 text-sm"
            >
              {empresas.map((e) => (
                <option key={e.id} value={e.id}>
                  {e.razon_social}
                </option>
              ))}
            </select>
          )}
          <Button
            size="sm"
            onClick={handleEvaluate}
            disabled={
              evaluateMutation.isPending || empresas.length === 0
            }
          >
            {evaluateMutation.isPending
              ? t("evaluating")
              : t("evaluate")}
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {alertas.length === 0 ? (
          <p className="text-xs text-muted-foreground">{t("empty")}</p>
        ) : (
          alertas.map((a) => (
            <AlertaCard
              key={a.id}
              alerta={a}
              onUpdate={(estado) =>
                updateMutation.mutate({ id: a.id, req: { estado } })
              }
              busy={updateMutation.isPending}
              tSev={tSev}
              tActions={tActions}
              tFechaLabel={t("fechaLimite")}
            />
          ))
        )}
      </CardContent>
    </Card>
  );
}

type ActionTranslator = (
  k: "vista" | "accionada" | "descartada",
) => string;
type SeverityTranslator = (
  k: AlertaResponse["severidad"],
) => string;

function AlertaCard({
  alerta,
  onUpdate,
  busy,
  tSev,
  tActions,
  tFechaLabel,
}: {
  alerta: AlertaResponse;
  onUpdate: (estado: AlertaEstado) => void;
  busy: boolean;
  tSev: SeverityTranslator;
  tActions: ActionTranslator;
  tFechaLabel: string;
}) {
  const tone =
    alerta.severidad === "critical"
      ? "border-destructive/50 bg-destructive/5"
      : alerta.severidad === "warning"
        ? "border-yellow-300 bg-yellow-50"
        : "border-blue-200 bg-blue-50";
  const sevLabel =
    alerta.severidad === "critical"
      ? "text-destructive"
      : alerta.severidad === "warning"
        ? "text-yellow-900"
        : "text-blue-900";

  return (
    <div className={`rounded-md border p-3 text-sm ${tone}`}>
      <div className="mb-1 flex items-baseline justify-between gap-3">
        <span className={`text-xs font-semibold uppercase ${sevLabel}`}>
          {tSev(alerta.severidad)}
        </span>
        {alerta.fecha_limite && (
          <span className="text-xs text-muted-foreground">
            {tFechaLabel.replace("{fecha}", alerta.fecha_limite)}
          </span>
        )}
      </div>
      <h3 className="mb-1 font-medium">{alerta.titulo}</h3>
      <p className="mb-2 text-xs text-muted-foreground">
        {alerta.descripcion}
      </p>
      {alerta.accion_recomendada && (
        <p className="mb-3 text-xs text-muted-foreground">
          <strong>Acción:</strong> {alerta.accion_recomendada}
        </p>
      )}
      <div className="flex flex-wrap gap-2">
        {alerta.estado === "nueva" && (
          <Button
            size="sm"
            variant="outline"
            onClick={() => onUpdate("vista")}
            disabled={busy}
          >
            {tActions("vista")}
          </Button>
        )}
        <Button
          size="sm"
          variant="outline"
          onClick={() => onUpdate("accionada")}
          disabled={busy}
        >
          {tActions("accionada")}
        </Button>
        <Button
          size="sm"
          variant="ghost"
          onClick={() => onUpdate("descartada")}
          disabled={busy}
        >
          {tActions("descartada")}
        </Button>
      </div>
    </div>
  );
}
