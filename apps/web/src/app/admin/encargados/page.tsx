import Link from "next/link";
import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";

import { LogoutButton } from "@/components/LogoutButton";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  ApiError,
  type EncargadoListAdminResponse,
  type MeResponse,
} from "@/lib/api";
import { fetchApiServer } from "@/lib/api-server";

export const dynamic = "force-dynamic";

const SOON_DAYS = 60;

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  return new Intl.DateTimeFormat("es-CL", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(new Date(iso));
}

function dpaStatus(
  vigenteHasta: string | null,
): "ok" | "soon" | "expired" | "missing" {
  if (!vigenteHasta) return "missing";
  const ms = new Date(vigenteHasta).getTime() - Date.now();
  const days = ms / (1000 * 60 * 60 * 24);
  if (days < 0) return "expired";
  if (days < SOON_DAYS) return "soon";
  return "ok";
}

export default async function AdminEncargadosPage() {
  let me: MeResponse;
  try {
    me = await fetchApiServer<MeResponse>("/api/me");
  } catch {
    redirect("/login");
  }

  const tCommon = await getTranslations("common");
  const t = await getTranslations("encargados.admin");
  const tBase = await getTranslations("encargados");

  let data: EncargadoListAdminResponse | null = null;
  let forbidden = false;
  try {
    data = await fetchApiServer<EncargadoListAdminResponse>(
      "/api/admin/encargados",
    );
  } catch (err) {
    if (err instanceof ApiError && err.status === 403) {
      forbidden = true;
    } else {
      throw err;
    }
  }

  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b border-border">
        <div className="container flex h-14 items-center justify-between">
          <div className="flex items-center gap-4">
            <Link href="/dashboard" className="font-semibold tracking-tight">
              {tCommon("appName")}
            </Link>
            {me.workspace && (
              <span className="text-sm text-muted-foreground">
                {me.workspace.name}
              </span>
            )}
          </div>
          <LogoutButton />
        </div>
      </header>

      <main className="container flex-1 space-y-6 py-12">
        <div>
          <h1 className="mb-2 text-3xl font-semibold tracking-tight">
            {t("title")}
          </h1>
          <p className="max-w-3xl text-sm text-muted-foreground">
            {t("subtitle")}
          </p>
        </div>

        {forbidden ? (
          <Card>
            <CardContent className="py-8">
              <p className="text-sm text-destructive">{t("forbidden")}</p>
            </CardContent>
          </Card>
        ) : (
          <Card>
            <CardHeader>
              <CardTitle className="text-base">{t("tableHeader")}</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-border bg-muted/40 text-left">
                      <th className="p-2 font-medium">
                        {tBase("table.nombre")}
                      </th>
                      <th className="p-2 font-medium">
                        {tBase("table.proposito")}
                      </th>
                      <th className="p-2 font-medium">
                        {tBase("table.pais")}
                      </th>
                      <th className="p-2 font-medium">{t("dpaFirmado")}</th>
                      <th className="p-2 font-medium">{t("dpaVigente")}</th>
                      <th className="p-2 font-medium">{t("dpoContacto")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(data?.encargados ?? []).map((e) => {
                      const st = dpaStatus(e.dpa_vigente_hasta);
                      const tone =
                        st === "expired"
                          ? "bg-destructive/10 text-destructive"
                          : st === "soon"
                            ? "bg-yellow-100 text-yellow-900"
                            : st === "missing"
                              ? "bg-muted text-muted-foreground"
                              : "";
                      return (
                        <tr
                          key={e.id}
                          className={`border-b border-border ${tone}`}
                        >
                          <td className="p-2 font-medium">{e.nombre}</td>
                          <td className="p-2 text-muted-foreground">
                            {e.proposito}
                          </td>
                          <td className="p-2 font-mono">
                            {e.pais_tratamiento}
                          </td>
                          <td className="p-2 font-mono">
                            {formatDate(e.dpa_firmado_at)}
                          </td>
                          <td className="p-2 font-mono">
                            {formatDate(e.dpa_vigente_hasta)}
                            {st === "expired" && (
                              <span className="ml-1 text-xs">
                                ({t("expired")})
                              </span>
                            )}
                            {st === "soon" && (
                              <span className="ml-1 text-xs">
                                ({t("expiresSoon")})
                              </span>
                            )}
                          </td>
                          <td className="p-2 text-muted-foreground">
                            {e.contacto_dpo ?? "—"}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        )}
      </main>
    </div>
  );
}
