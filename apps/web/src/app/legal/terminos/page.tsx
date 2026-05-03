import type { Metadata } from "next";
import Link from "next/link";
import { getTranslations } from "next-intl/server";

import { Footer_Shared } from "@/components/Footer_Shared";
import { fetchApiPublic, type LegalTextResponse } from "@/lib/api";

export const metadata: Metadata = {
  title: "Términos de servicio — Renteo",
  description:
    "Términos de servicio versión preliminar — pendiente de revisión por estudio jurídico.",
  robots: { index: false, follow: false },
};

export const dynamic = "force-dynamic";

export default async function TerminosPage() {
  const tLegal = await getTranslations("legal");
  const tTerminos = await getTranslations("legal.terminos");
  const tCommon = await getTranslations("common");

  let legal: LegalTextResponse | null = null;
  let loadError = false;
  try {
    legal = await fetchApiPublic<LegalTextResponse>(
      "/api/public/legal/terminos-servicio",
    );
  } catch {
    loadError = true;
  }

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
            {tTerminos("title")}
          </h1>
          {legal && (
            <p className="mb-8 text-xs text-muted-foreground">
              {tLegal("versionInfo", {
                version: legal.version,
                date: legal.effective_from,
              })}
            </p>
          )}
          {loadError ? (
            <p className="rounded border border-destructive/40 bg-destructive/5 p-4 text-sm text-destructive">
              {tLegal("loadFailed")}
            </p>
          ) : (
            <div className="whitespace-pre-line text-base leading-relaxed">
              {legal?.body}
            </div>
          )}
        </article>
      </main>

      <Footer_Shared />
    </div>
  );
}
