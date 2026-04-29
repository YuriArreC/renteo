import type { Metadata } from "next";
import Link from "next/link";
import { getTranslations } from "next-intl/server";

import { Footer_Shared } from "@/components/Footer_Shared";

const SECTIONS = [
  "responsable",
  "alcance",
  "responsabilidad",
  "cumplimiento",
  "datos",
  "propiedad",
  "terminacion",
  "conflictos",
] as const;

const LAST_UPDATED = "2026-04-28";

export const metadata: Metadata = {
  title: "Términos de servicio — Renteo",
  description:
    "Términos de servicio versión preliminar (v1) — pendiente de revisión por estudio jurídico.",
  robots: { index: false, follow: false },
};

export default async function TerminosPage() {
  const t = await getTranslations("legal.terminos");
  const tLegal = await getTranslations("legal");
  const tCommon = await getTranslations("common");

  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b border-border">
        <div className="container flex h-14 items-center">
          <Link href="/" className="font-semibold tracking-tight">
            {tCommon("appName")}
          </Link>
        </div>
      </header>

      <main className="flex-1">
        <article className="container max-w-3xl py-16">
          <div className="mb-8 rounded-md border border-border bg-muted/40 p-4 text-sm text-muted-foreground">
            {tLegal("placeholderBanner")}
          </div>
          <h1 className="mb-2 text-3xl font-semibold tracking-tight">
            {t("title")}
          </h1>
          <p className="mb-8 text-sm text-muted-foreground">
            {tLegal("lastUpdated", { date: LAST_UPDATED })}
          </p>
          <p className="mb-10 text-base leading-relaxed">{t("intro")}</p>
          <div className="space-y-8">
            {SECTIONS.map((key) => (
              <section key={key}>
                <h2 className="mb-2 text-xl font-medium">
                  {t(`sections.${key}.title`)}
                </h2>
                <p className="text-base leading-relaxed text-muted-foreground">
                  {t(`sections.${key}.body`)}
                </p>
              </section>
            ))}
          </div>
        </article>
      </main>

      <Footer_Shared />
    </div>
  );
}
