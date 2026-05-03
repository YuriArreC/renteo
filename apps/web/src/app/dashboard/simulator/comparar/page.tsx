import Link from "next/link";
import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";

import { ScenarioCompare } from "@/app/dashboard/simulator/comparar/ScenarioCompare";
import { LogoutButton } from "@/components/LogoutButton";
import { type MeResponse } from "@/lib/api";
import { fetchApiServer } from "@/lib/api-server";

type SearchParams = Promise<{ ids?: string }>;

export default async function CompararPage({
  searchParams,
}: {
  searchParams: SearchParams;
}) {
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
  const t = await getTranslations("simulator.compare");

  const { ids = "" } = await searchParams;
  const idList = ids
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);

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
        <Link
          href="/dashboard/simulator"
          className="mb-6 inline-block text-sm text-muted-foreground hover:underline"
        >
          {t("back")}
        </Link>
        <h1 className="mb-2 text-3xl font-semibold tracking-tight">
          {t("title")}
        </h1>
        <p className="mb-10 max-w-3xl text-sm text-muted-foreground">
          {t("subtitle")}
        </p>

        {idList.length < 2 ? (
          <p className="rounded border border-yellow-300 bg-yellow-50 p-4 text-sm text-yellow-900">
            {t("missingIds")}
          </p>
        ) : (
          <ScenarioCompare ids={idList} />
        )}
      </main>
    </div>
  );
}
