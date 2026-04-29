import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";

import { LogoutButton } from "@/components/LogoutButton";
import { fetchApiServer, type MeResponse } from "@/lib/api";

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

  const tCommon = await getTranslations("common");
  const t = await getTranslations("dashboard");

  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b border-border">
        <div className="container flex h-14 items-center justify-between">
          <div className="flex items-center gap-4">
            <span className="font-semibold tracking-tight">
              {tCommon("appName")}
            </span>
            <span className="text-sm text-muted-foreground">
              {me.workspace.name}
            </span>
          </div>
          <LogoutButton />
        </div>
      </header>

      <main className="container flex-1 py-16">
        <h1 className="mb-3 text-3xl font-semibold tracking-tight">
          {t("empty.title", { name: me.workspace.name })}
        </h1>
        <p className="max-w-2xl text-muted-foreground">{t("empty.body")}</p>
      </main>
    </div>
  );
}
