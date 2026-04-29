import Link from "next/link";
import { getTranslations } from "next-intl/server";

import { Footer_Shared } from "@/components/Footer_Shared";

export default async function HomePage() {
  const t = await getTranslations("landing");
  const tCommon = await getTranslations("common");

  const features = ["diagnostico", "simulador", "alertas"] as const;

  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b border-border">
        <div className="container flex h-14 items-center justify-between">
          <Link href="/" className="font-semibold tracking-tight">
            {tCommon("appName")}
          </Link>
          <nav className="flex items-center gap-3 text-sm">
            <Link
              href="/login"
              className="text-muted-foreground hover:text-foreground"
            >
              {t("cta.secondary")}
            </Link>
            <Link
              href="/signup"
              className="inline-flex h-9 items-center rounded-md bg-primary px-4 font-medium text-primary-foreground hover:bg-primary/90"
            >
              {t("cta.primary")}
            </Link>
          </nav>
        </div>
      </header>

      <main className="flex-1">
        <section className="container flex flex-col items-start gap-6 py-20 md:py-28">
          <h1 className="max-w-3xl text-4xl font-semibold tracking-tight md:text-5xl">
            {t("hero.headline")}
          </h1>
          <p className="max-w-2xl text-lg text-muted-foreground md:text-xl">
            {t("hero.subheadline")}
          </p>
          <div className="flex flex-wrap gap-3">
            <Link
              href="/signup"
              className="inline-flex h-11 items-center rounded-md bg-primary px-6 font-medium text-primary-foreground hover:bg-primary/90"
            >
              {t("cta.primary")}
            </Link>
            <Link
              href="/login"
              className="inline-flex h-11 items-center rounded-md border border-border px-6 font-medium hover:bg-accent"
            >
              {t("cta.secondary")}
            </Link>
          </div>
        </section>

        <section className="border-t border-border bg-muted/30">
          <div className="container py-16 md:py-20">
            <h2 className="mb-10 text-2xl font-semibold tracking-tight">
              {t("features.title")}
            </h2>
            <ul className="grid gap-6 md:grid-cols-3">
              {features.map((key) => (
                <li
                  key={key}
                  className="rounded-lg border border-border bg-background p-6"
                >
                  <h3 className="mb-2 text-lg font-medium">
                    {t(`features.items.${key}.title`)}
                  </h3>
                  <p className="text-sm text-muted-foreground">
                    {t(`features.items.${key}.body`)}
                  </p>
                </li>
              ))}
            </ul>
          </div>
        </section>

        <section className="container py-16">
          <p className="max-w-2xl text-sm text-muted-foreground">
            {t("complianceNote")}
          </p>
        </section>
      </main>

      <Footer_Shared />
    </div>
  );
}
