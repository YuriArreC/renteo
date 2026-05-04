import Link from "next/link";
import { getTranslations } from "next-intl/server";

import { NewRuleForm } from "./NewRuleForm";

// La página requiere un user autenticado para que el POST funcione;
// no tiene sentido prerenderearla estática.
export const dynamic = "force-dynamic";

export default async function NewRulePage() {
  const t = await getTranslations("adminRules");

  return (
    <main className="container max-w-4xl space-y-6 py-12">
      <Link
        href="/admin/rules"
        className="text-sm text-muted-foreground hover:underline"
      >
        {t("back")}
      </Link>
      <NewRuleForm />
    </main>
  );
}
