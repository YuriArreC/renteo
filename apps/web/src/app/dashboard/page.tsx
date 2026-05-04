import Link from "next/link";
import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";

import { AlertasInbox } from "@/app/dashboard/AlertasInbox";
import { LogoutButton } from "@/components/LogoutButton";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  type EmpresasListResponse,
  type MeResponse,
  type RegimenActual,
} from "@/lib/api";
import { fetchApiServer } from "@/lib/api-server";

export default async function DashboardPage() {
  let me: MeResponse;
  try {
    me = await fetchApiServer<MeResponse>("/api/me");
  } catch {
    redirect("/login");
  }

  if (!me.workspace) {
    redirect("/onboarding/workspace");
  }

  let empresas: EmpresasListResponse = { empresas: [] };
  try {
    empresas = await fetchApiServer<EmpresasListResponse>("/api/empresas");
  } catch {
    // Fallback silencioso: dashboard se renderea sin tabla.
  }

  const tCommon = await getTranslations("common");
  const t = await getTranslations("dashboard");
  const hasEmpresas = empresas.empresas.length > 0;

  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b border-border">
        <div className="container flex h-14 items-center justify-between">
          <div className="flex items-center gap-4">
            <Link href="/dashboard" className="font-semibold tracking-tight">
              {tCommon("appName")}
            </Link>
            <span className="text-sm text-muted-foreground">
              {me.workspace.name}
            </span>
          </div>
          <LogoutButton />
        </div>
      </header>

      <main className="container flex-1 space-y-10 py-16">
        <div>
          <h1 className="mb-3 text-3xl font-semibold tracking-tight">
            {t("empty.title", { name: me.workspace.name })}
          </h1>
          <p className="mb-6 max-w-2xl text-muted-foreground">
            {t("empty.body")}
          </p>
          <div className="flex flex-wrap gap-3">
            {!hasEmpresas && (
              <Button asChild>
                <Link href="/onboarding/empresa">
                  {t("empty.registerEmpresaCta")}
                </Link>
              </Button>
            )}
            <Button asChild variant={hasEmpresas ? "default" : "outline"}>
              <Link href="/dashboard/regime">{t("empty.regimeCta")}</Link>
            </Button>
            <Button asChild variant="outline">
              <Link href="/dashboard/simulator">
                {t("empty.simulatorCta")}
              </Link>
            </Button>
            <Button asChild variant="outline">
              <Link href="/dashboard/comparador">
                {t("empty.comparadorCta")}
              </Link>
            </Button>
            <Button asChild variant="outline">
              <Link href="/dashboard/calc">{t("empty.playgroundCta")}</Link>
            </Button>
            <Button asChild variant="ghost">
              <Link href="/dashboard/privacidad">
                {t("empty.privacidadCta")}
              </Link>
            </Button>
          </div>
        </div>

        <EmpresasSection empresas={empresas.empresas} />

        {hasEmpresas && <AlertasInbox empresas={empresas.empresas} />}
      </main>
    </div>
  );
}

async function EmpresasSection({
  empresas,
}: {
  empresas: EmpresasListResponse["empresas"];
}) {
  const t = await getTranslations("dashboard");
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-4">
        <CardTitle className="text-base">{t("empty.empresasHeader")}</CardTitle>
        <Button asChild size="sm" variant="outline">
          <Link href="/onboarding/empresa">{t("empty.addEmpresaCta")}</Link>
        </Button>
      </CardHeader>
      <CardContent>
        {empresas.length === 0 ? (
          <p className="text-xs text-muted-foreground">
            {t("empty.empresasEmpty")}
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border bg-muted/40 text-left">
                  <th className="p-3 font-medium">{t("empty.empresaRut")}</th>
                  <th className="p-3 font-medium">
                    {t("empty.empresaRazonSocial")}
                  </th>
                  <th className="p-3 font-medium">
                    {t("empty.empresaRegimen")}
                  </th>
                </tr>
              </thead>
              <tbody>
                {empresas.map((e) => (
                  <tr key={e.id} className="border-b border-border">
                    <td className="p-3 font-mono">{e.rut}</td>
                    <td className="p-3">{e.razon_social}</td>
                    <td className="p-3 text-xs text-muted-foreground">
                      {t(
                        `empty.regimenLabel.${e.regimen_actual as RegimenActual}`,
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
  );
}
