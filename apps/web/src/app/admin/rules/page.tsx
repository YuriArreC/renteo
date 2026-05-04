import Link from "next/link";
import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";

import { LogoutButton } from "@/components/LogoutButton";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  ApiError,
  type MeResponse,
  type RuleSetListResponse,
  type RuleStatus,
} from "@/lib/api";
import { fetchApiServer } from "@/lib/api-server";

export const dynamic = "force-dynamic";

export default async function AdminRulesPage() {
  let me: MeResponse;
  try {
    me = await fetchApiServer<MeResponse>("/api/me");
  } catch {
    redirect("/login");
  }

  const tCommon = await getTranslations("common");
  const t = await getTranslations("adminRules");
  const tStatus = await getTranslations("adminRules.statusLabel");

  let rules: RuleSetListResponse | null = null;
  let forbidden = false;
  try {
    rules = await fetchApiServer<RuleSetListResponse>("/api/admin/rules");
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

      <main className="container flex-1 space-y-8 py-12">
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
            <CardHeader className="flex flex-row items-center justify-between gap-4">
              <CardTitle className="text-base">
                {t("title")}{" "}
                <span className="text-xs font-normal text-muted-foreground">
                  ({rules?.rule_sets.length ?? 0})
                </span>
              </CardTitle>
              <Button asChild size="sm">
                <Link href="/admin/rules/new">{t("newRule")}</Link>
              </Button>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-border bg-muted/40 text-left">
                      <th className="p-2 font-medium">{t("table.domain")}</th>
                      <th className="p-2 font-medium">{t("table.key")}</th>
                      <th className="p-2 font-medium">{t("table.version")}</th>
                      <th className="p-2 font-medium">{t("table.status")}</th>
                      <th className="p-2 font-medium">
                        {t("table.vigencia")}
                      </th>
                      <th className="p-2 font-medium">
                        {t("table.firmado")}
                      </th>
                      <th className="p-2 font-medium">
                        {t("table.rowAction")}
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {(rules?.rule_sets ?? []).map((r) => (
                      <tr
                        key={r.id}
                        className="border-b border-border hover:bg-muted/30"
                      >
                        <td className="p-2 font-mono">{r.domain}</td>
                        <td className="p-2 font-mono">{r.key}</td>
                        <td className="p-2 text-right font-mono">
                          v{r.version}
                        </td>
                        <td className="p-2">
                          <StatusBadge
                            status={r.status}
                            label={tStatus(r.status)}
                          />
                        </td>
                        <td className="p-2 text-muted-foreground">
                          {r.vigencia_desde}
                          {r.vigencia_hasta
                            ? ` → ${r.vigencia_hasta}`
                            : " → ∞"}
                        </td>
                        <td className="p-2 text-muted-foreground">
                          {r.published_at ? "✓✓" : r.published_by_contador ? "✓·" : "·"}
                        </td>
                        <td className="p-2">
                          <Link
                            href={`/admin/rules/${r.id}`}
                            className="text-xs text-primary hover:underline"
                          >
                            {t("table.rowAction")}
                          </Link>
                        </td>
                      </tr>
                    ))}
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
    <span className={`rounded px-2 py-0.5 ${tone}`}>{label}</span>
  );
}
