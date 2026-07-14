"use client";

import { useQuery } from "@tanstack/react-query";

import { fetchApiClient, type LegalTextResponse } from "@/lib/api";

/**
 * Aviso "motor no validado por contador socio" (skill 1 + skill 2).
 *
 * Se monta junto a TODO output del motor que el usuario pueda leer como una
 * recomendación (wizard de régimen, simulador, comparador). Convive con
 * `DecisionRibbon`, que cubre otra cosa: aquel informa el derecho a oponerse
 * a decisiones automatizadas (Ley 21.719); este informa que las REGLAS
 * TRIBUTARIAS todavía no las firmó un contador socio.
 *
 * El texto NO vive acá: viene de `privacy.legal_texts`
 * (`banner-motor-no-validado`). La UI no inventa copy legal — es una
 * prohibición explícita del proyecto, y además permite retirar el banner
 * publicando una v2 del texto cuando llegue la firma, sin tocar código.
 *
 * Sufijo `_Shared`: lo consumen tanto la UX de cliente A (PYME) como la de
 * cliente B (contadores).
 */
export function EngineNotValidatedBanner_Shared() {
  const query = useQuery<LegalTextResponse>({
    queryKey: ["legal-banner-motor-no-validado"],
    queryFn: () =>
      fetchApiClient<LegalTextResponse>("/api/legal/banner-motor-no-validado"),
    // Si el texto no está publicado (p. ej. ya se firmó y se retiró con un
    // effective_to), la query falla y el banner simplemente no se muestra.
    retry: false,
  });

  if (query.isPending || query.isError || !query.data) return null;

  return (
    <aside
      role="alert"
      className="rounded-md border border-amber-300 bg-amber-50 p-4 text-xs text-amber-900"
    >
      <p className="mb-1 font-semibold uppercase tracking-wide">
        Demo — motor sin validar
      </p>
      <p className="leading-relaxed">{query.data.body}</p>
    </aside>
  );
}
