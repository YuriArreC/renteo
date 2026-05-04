import type { Metadata } from "next";
import Link from "next/link";
import { getTranslations } from "next-intl/server";

import { Footer_Shared } from "@/components/Footer_Shared";
import {
  type EncargadoListPublicResponse,
  fetchApiPublic,
} from "@/lib/api";

export const metadata: Metadata = {
  title: "Encargados de tratamiento — Renteo",
  description:
    "Lista pública de proveedores que tratan datos personales en nombre de Renteo (Ley 21.719).",
  robots: { index: false, follow: false },
};

export const dynamic = "force-dynamic";

export default async function EncargadosLegalPage() {
  const tCommon = await getTranslations("common");
  const t = await getTranslations("encargados");

  let data: EncargadoListPublicResponse = { encargados: [] };
  try {
    data = await fetchApiPublic<EncargadoListPublicResponse>(
      "/api/public/encargados",
    );
  } catch {
    // Fallback silencioso.
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
          <h1 className="mb-2 text-3xl font-semibold tracking-tight">
            {t("title")}
          </h1>
          <p className="mb-10 text-base leading-relaxed text-muted-foreground">
            {t("subtitle")}
          </p>

          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border bg-muted/40 text-left">
                  <th className="p-3 font-medium">{t("table.nombre")}</th>
                  <th className="p-3 font-medium">
                    {t("table.proposito")}
                  </th>
                  <th className="p-3 font-medium">{t("table.pais")}</th>
                </tr>
              </thead>
              <tbody>
                {data.encargados.length === 0 ? (
                  <tr>
                    <td
                      colSpan={3}
                      className="p-3 text-xs text-muted-foreground"
                    >
                      {t("empty")}
                    </td>
                  </tr>
                ) : (
                  data.encargados.map((e) => (
                    <tr key={e.nombre} className="border-b border-border">
                      <td className="p-3 font-medium">{e.nombre}</td>
                      <td className="p-3 text-muted-foreground">
                        {e.proposito}
                      </td>
                      <td className="p-3 font-mono text-xs">
                        {e.pais_tratamiento}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </article>
      </main>

      <Footer_Shared />
    </div>
  );
}
