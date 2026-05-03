"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import { fetchApiClient, type LegalTextResponse } from "@/lib/api";

/**
 * Ribbon de decisiones automatizadas (skill 2 + skill 5).
 *
 * Aparece debajo de cualquier output del motor que incorpore
 * tratamiento automatizado (wizard de régimen, simulador, comparador).
 * El body viene de privacy.legal_texts (key
 * `ribbon-decisiones-automatizadas`); el CTA aterriza en
 * /dashboard/privacidad con tipo=oposicion pre-rellenado.
 */
export function DecisionRibbon({ context }: { context: string }) {
  const t = useTranslations("decisionRibbon");
  const query = useQuery<LegalTextResponse>({
    queryKey: ["legal-ribbon"],
    queryFn: () =>
      fetchApiClient<LegalTextResponse>(
        "/api/legal/ribbon-decisiones-automatizadas",
      ),
  });

  if (query.isPending || !query.data) return null;

  const params = new URLSearchParams({
    tipo: "oposicion",
    descripcion: context,
  });

  return (
    <aside
      role="note"
      className="rounded-md border border-blue-200 bg-blue-50 p-4 text-xs text-blue-900"
    >
      <p className="mb-3 leading-relaxed">{query.data.body}</p>
      <Button
        asChild
        size="sm"
        variant="outline"
        className="border-blue-300 bg-white hover:bg-blue-100"
      >
        <Link href={`/dashboard/privacidad?${params.toString()}`}>
          {t("cta")}
        </Link>
      </Button>
    </aside>
  );
}
