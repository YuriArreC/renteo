import Link from "next/link";
import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";

import { BatchDiagnose } from "@/app/cartera/BatchDiagnose";
import { PapelTrabajoButton } from "@/app/cartera/PapelTrabajoButton";
import { QuickAddEmpresa } from "@/app/cartera/QuickAddEmpresa";
import { LogoutButton } from "@/components/LogoutButton";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  type CarteraResponse,
  type MeResponse,
  type RegimenActual,
} from "@/lib/api";
import { fetchApiServer } from "@/lib/api-server";

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
  }).format(new Date(iso));
}

export default async function CarteraPage() {
  let me: MeResponse;
  try {
    me = await fetchApiServer<MeResponse>("/api/me");
  } catch {
    redirect("/login");
  }
  if (!me.workspace) {
    redirect("/onboarding/workspace");
  }

  let cartera: CarteraResponse = {
    empresas: [],
    total_empresas: 0,
    total_alertas_abiertas: 0,
    ahorro_potencial_estimado_clp: "0",
  };
  try {
    cartera = await fetchApiServer<CarteraResponse>("/api/cartera");
  } catch {
    // Empty fallback.
  }

  const tCommon = await getTranslations("common");
  const t = await getTranslations("cartera");

  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b border-border">
        <div className="container flex h-14 items-center justify-between">
          <div className="flex items-center gap-4">
            <Link href="/cartera" className="font-semibold tracking-tight">
              {tCommon("appName")}
            </Link>
            <span className="text-sm text-muted-foreground">
              {me.workspace.name}
            </span>
          </div>
          <LogoutButton />
        </div>
      </header>

      <main className="container flex-1 space-y-8 py-12">
        <div>
          <h1 className="mb-2 text-3xl font-semibold tracking-tight">
            {t("title")}
          </h1>
          <p className="max-w-3xl text-sm text-muted-foreground">
            {t("subtitle")}
          </p>
        </div>

        <div className="grid gap-4 md:grid-cols-3">
          <Kpi
            label={t("kpis.totalEmpresas")}
            value={String(cartera.total_empresas)}
          />
          <Kpi
            label={t("kpis.alertasAbiertas")}
            value={String(cartera.total_alertas_abiertas)}
          />
          <Kpi
            label={t("kpis.ahorroPotencial")}
            value={formatCLP(cartera.ahorro_potencial_estimado_clp)}
          />
        </div>

        <QuickAddEmpresa />

        <Card>
          <CardHeader className="flex flex-row items-center justify-between gap-4">
            <CardTitle className="text-base">{t("title")}</CardTitle>
            <Button asChild size="sm" variant="outline">
              <Link href="/onboarding/empresa">{t("registerEmpresa")}</Link>
            </Button>
          </CardHeader>
          <CardContent>
            {cartera.empresas.length === 0 ? (
              <p className="text-xs text-muted-foreground">{t("empty")}</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-border bg-muted/40 text-left">
                      <th className="p-2 font-medium">
                        {t("table.score")}
                      </th>
                      <th className="p-2 font-medium">{t("table.rut")}</th>
                      <th className="p-2 font-medium">
                        {t("table.razonSocial")}
                      </th>
                      <th className="p-2 font-medium">
                        {t("table.regimen")}
                      </th>
                      <th className="p-2 text-right font-medium">
                        {t("table.alertas")}
                      </th>
                      <th className="p-2 font-medium">
                        {t("table.ultimoDiag")}
                      </th>
                      <th className="p-2 font-medium">
                        {t("table.ultimaSim")}
                      </th>
                      <th className="p-2 font-medium">
                        {t("table.acciones")}
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {cartera.empresas.map((e) => (
                      <tr
                        key={e.empresa_id}
                        className="border-b border-border"
                      >
                        <td className="p-2">
                          <ScoreBadge score={e.score_oportunidad} />
                        </td>
                        <td className="p-2 font-mono">{e.rut}</td>
                        <td className="p-2 font-medium">{e.razon_social}</td>
                        <td className="p-2">
                          {t(
                            `regimenLabel.${e.regimen_actual as RegimenActual}`,
                          )}
                        </td>
                        <td className="p-2 text-right font-mono">
                          {e.alertas_abiertas > 0 ? (
                            <span className="rounded bg-yellow-100 px-2 py-0.5 text-yellow-900">
                              {e.alertas_abiertas}
                            </span>
                          ) : (
                            "0"
                          )}
                        </td>
                        <td className="p-2 text-muted-foreground">
                          {e.ultima_recomendacion ? (
                            <>
                              {t(
                                `regimenLabel.${e.ultima_recomendacion.regimen_recomendado as RegimenActual}`,
                              )}
                              {" · "}
                              {formatCLP(
                                e.ultima_recomendacion.ahorro_estimado_clp,
                              )}
                              {" · "}
                              {formatDate(e.ultima_recomendacion.created_at)}
                            </>
                          ) : (
                            t("table.noDiag")
                          )}
                        </td>
                        <td className="p-2 text-muted-foreground">
                          {e.ultima_simulacion ? (
                            <>
                              {formatCLP(
                                e.ultima_simulacion.ahorro_total_clp,
                              )}
                              {" · "}
                              {formatDate(e.ultima_simulacion.created_at)}
                            </>
                          ) : (
                            t("table.noSim")
                          )}
                        </td>
                        <td className="p-2">
                          <div className="flex gap-1">
                            <Button asChild size="sm" variant="outline">
                              <Link
                                href={`/dashboard/regime?empresa=${e.empresa_id}`}
                              >
                                {t("table.diagnosticar")}
                              </Link>
                            </Button>
                            <Button asChild size="sm" variant="ghost">
                              <Link
                                href={`/dashboard/simulator?empresa=${e.empresa_id}`}
                              >
                                {t("table.simular")}
                              </Link>
                            </Button>
                            <PapelTrabajoButton
                              empresaId={e.empresa_id}
                              razonSocial={e.razon_social}
                              rut={e.rut}
                            />
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>

        {cartera.empresas.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Batch diagnóstico</CardTitle>
            </CardHeader>
            <CardContent>
              <BatchDiagnose empresas={cartera.empresas} />
            </CardContent>
          </Card>
        )}
      </main>
    </div>
  );
}

function Kpi({ label, value }: { label: string; value: string }) {
  return (
    <Card>
      <CardContent className="py-5">
        <p className="text-xs uppercase text-muted-foreground">{label}</p>
        <p className="mt-1 text-2xl font-semibold">{value}</p>
      </CardContent>
    </Card>
  );
}

function ScoreBadge({ score }: { score: number }) {
  const tone =
    score >= 75
      ? "bg-destructive/10 text-destructive"
      : score >= 50
        ? "bg-yellow-100 text-yellow-900"
        : score >= 25
          ? "bg-blue-100 text-blue-900"
          : "bg-muted text-muted-foreground";
  return (
    <span
      className={`inline-block min-w-[2.5rem] rounded px-2 py-1 text-center font-mono font-medium ${tone}`}
    >
      {score}
    </span>
  );
}
