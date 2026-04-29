import Link from "next/link";
import { getTranslations } from "next-intl/server";

const APP_VERSION = process.env.NEXT_PUBLIC_APP_VERSION ?? "0.0.0";

export async function Footer_Shared() {
  const t = await getTranslations("footer");
  const tCommon = await getTranslations("common");
  const year = new Date().getFullYear();

  return (
    <footer className="border-t border-border bg-background">
      <div className="container flex flex-col gap-4 py-8 text-sm text-muted-foreground sm:flex-row sm:items-center sm:justify-between">
        <p>{t("copyright", { year })}</p>
        <nav aria-label="Enlaces legales">
          <ul className="flex flex-wrap gap-x-6 gap-y-2">
            <li>
              <Link
                href="/legal/privacidad"
                className="hover:text-foreground"
              >
                {t("links.privacidad")}
              </Link>
            </li>
            <li>
              <Link
                href="/legal/terminos"
                className="hover:text-foreground"
              >
                {t("links.terminos")}
              </Link>
            </li>
          </ul>
        </nav>
        <p className="text-xs">
          {tCommon("appName")} · {t("version", { version: APP_VERSION })}
        </p>
      </div>
    </footer>
  );
}
