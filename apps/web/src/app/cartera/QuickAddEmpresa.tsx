"use client";

import { useMutation } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
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
  type FromRutRequest,
  type FromRutResponse,
  fetchApiClient,
} from "@/lib/api";

export function QuickAddEmpresa() {
  const t = useTranslations("cartera.quickAdd");
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [rut, setRut] = useState("");
  const [fallback, setFallback] = useState("");
  const [meses, setMeses] = useState(12);
  const [lastResponse, setLastResponse] =
    useState<FromRutResponse | null>(null);

  const mutation = useMutation({
    mutationFn: (req: FromRutRequest) =>
      fetchApiClient<FromRutResponse>("/api/empresas/from-rut", {
        method: "POST",
        body: JSON.stringify(req),
      }),
    onSuccess: (data) => {
      setLastResponse(data);
      toast.success(
        t("created", {
          razon: data.razon_social || data.rut,
          regimen: data.regimen_actual,
        }),
      );
      setRut("");
      setFallback("");
      // Refresca la cartera (RSC) para que la empresa aparezca.
      router.refresh();
    },
    onError: (err) =>
      toast.error(err instanceof ApiError ? err.detail : String(err)),
  });

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmedRut = rut.trim();
    if (!trimmedRut) {
      toast.error(t("rutRequired"));
      return;
    }
    const req: FromRutRequest = {
      rut: trimmedRut,
      sync_meses: meses,
    };
    if (fallback.trim()) {
      req.razon_social_fallback = fallback.trim();
    }
    mutation.mutate(req);
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs text-muted-foreground">{t("hint")}</p>
        <Button
          size="sm"
          variant={open ? "ghost" : "default"}
          onClick={() => setOpen((v) => !v)}
        >
          {open ? t("close") : t("trigger")}
        </Button>
      </div>

      {open && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">{t("title")}</CardTitle>
            <p className="text-xs text-muted-foreground">{t("subtitle")}</p>
          </CardHeader>
          <CardContent>
            <form
              onSubmit={onSubmit}
              className="grid gap-3 md:grid-cols-3"
            >
              <div className="space-y-1 md:col-span-1">
                <Label className="text-xs">{t("rutLabel")}</Label>
                <Input
                  value={rut}
                  onChange={(e) => setRut(e.target.value)}
                  placeholder="12.345.678-5"
                  required
                />
              </div>
              <div className="space-y-1 md:col-span-2">
                <Label className="text-xs">{t("fallbackLabel")}</Label>
                <Input
                  value={fallback}
                  onChange={(e) => setFallback(e.target.value)}
                  placeholder={t("fallbackPlaceholder")}
                />
              </div>
              <div className="space-y-1 md:col-span-1">
                <Label className="text-xs">{t("mesesLabel")}</Label>
                <Input
                  type="number"
                  min={1}
                  max={24}
                  value={meses}
                  onChange={(e) => setMeses(Number(e.target.value))}
                />
              </div>
              <div className="md:col-span-3 flex gap-2">
                <Button type="submit" disabled={mutation.isPending}>
                  {mutation.isPending ? t("submitting") : t("submit")}
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setOpen(false)}
                  disabled={mutation.isPending}
                >
                  {t("cancel")}
                </Button>
              </div>
            </form>

            {lastResponse && (
              <div className="mt-4 rounded-md border border-border bg-muted/30 p-3 text-xs">
                <p className="font-semibold">
                  {t("resultHeader", {
                    razon: lastResponse.razon_social || lastResponse.rut,
                  })}
                </p>
                <ul className="mt-2 space-y-0.5 text-muted-foreground">
                  <li>
                    {t("resultRegimen", {
                      regimen: lastResponse.regimen_actual,
                    })}
                  </li>
                  <li>
                    {t("resultLookup", {
                      via: lastResponse.lookup.via_sii
                        ? t("viaSii")
                        : t("viaFallback"),
                    })}
                  </li>
                  {lastResponse.sync && (
                    <li>
                      {t("resultSync", {
                        rows: lastResponse.sync.rcv_rows_inserted,
                        provider: lastResponse.sync.provider,
                      })}
                    </li>
                  )}
                  {lastResponse.warnings.length > 0 && (
                    <li className="mt-2 text-amber-700">
                      <p className="font-semibold">{t("warnings")}</p>
                      <ul className="list-inside list-disc">
                        {lastResponse.warnings.map((w) => (
                          <li key={w}>{w}</li>
                        ))}
                      </ul>
                    </li>
                  )}
                </ul>
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
