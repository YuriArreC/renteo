import Link from "next/link";
import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";

import { ScenarioSimulator } from "@/app/dashboard/simulator/ScenarioSimulator";
import { LogoutButton } from "@/components/LogoutButton";
import { type MeResponse } from "@/lib/api";
import { fetchApiServer } from "@/lib/api-server";

export default async function DashboardSimulatorPage() {
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
  const t = await getTranslations("simulator");

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

      <main className="container flex-1 py-12">
        <h1 className="mb-2 text-3xl font-semibold tracking-tight">
          {t("title")}
        </h1>
        <p className="mb-10 max-w-3xl text-sm text-muted-foreground">
          {t("subtitle")}
        </p>

        <ScenarioSimulator />
      </main>
    </div>
  );
}
