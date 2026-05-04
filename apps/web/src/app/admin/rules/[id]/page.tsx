import Link from "next/link";
import { getTranslations } from "next-intl/server";

import { RuleDetail } from "./RuleDetail";

export const dynamic = "force-dynamic";

type Params = Promise<{ id: string }>;

export default async function RuleDetailPage({
  params,
}: {
  params: Params;
}) {
  const { id } = await params;
  const t = await getTranslations("adminRules");

  return (
    <main className="container max-w-4xl space-y-6 py-12">
      <Link
        href="/admin/rules"
        className="text-sm text-muted-foreground hover:underline"
      >
        {t("back")}
      </Link>
      <RuleDetail ruleId={id} />
    </main>
  );
}
