import type { Metadata } from "next";
import Link from "next/link";
import { getTranslations } from "next-intl/server";

import { Footer_Shared } from "@/components/Footer_Shared";
import { fetchApiPublic, type LegalTextResponse } from "@/lib/api";

export const metadata: Metadata = {
  title: "Política de privacidad — Renteo",
  description:
    "Política de privacidad versión preliminar — pendiente de revisión por estudio jurídico.",
  robots: { index: false, follow: false },
};

// El cuerpo se sirve desde privacy.legal_texts vía /api/public/legal/...
// No hay nada que prerender en build: forzar SSR para evitar fetch a un
// backend que aún no existe durante `next build`.
export const dynamic = "force-dynamic";

export default async function PrivacidadPage() {
  const tLegal = await getTranslations("legal");
  const tPrivacidad = await getTranslations("legal.privacidad");
  const tCommon = await getTranslations("common");

  let legal: LegalTextResponse | null = null;
  let loadError = false;
  try {
    legal = await fetchApiPublic<LegalTextResponse>(
      "/api/public/legal/politica-privacidad",
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
            {tPrivacidad("title")}
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
