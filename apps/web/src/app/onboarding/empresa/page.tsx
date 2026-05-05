import { redirect } from "next/navigation";

import { OnboardingEmpresaForm } from "@/app/onboarding/empresa/OnboardingEmpresaForm";
import { ApiError, type MeResponse } from "@/lib/api";
import { fetchApiServer } from "@/lib/api-server";

export const dynamic = "force-dynamic";

/**
 * Server shell con tres guards:
 *  1. No autenticado → /login.
 *  2. Sin workspace → /onboarding/workspace (paso anterior pendiente).
 *  3. workspace.type=accounting_firm → /cartera (cliente B no usa
 *     onboarding/empresa; tiene "Alta rápida con RUT" en /cartera).
 */
export default async function OnboardingEmpresaPage() {
  let me: MeResponse | null = null;
  try {
    me = await fetchApiServer<MeResponse>("/api/me");
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) {
      redirect("/login");
    }
  }
  if (!me?.workspace) {
    redirect("/onboarding/workspace");
  }
  if (me.workspace.type === "accounting_firm") {
    redirect("/cartera");
  }
  return <OnboardingEmpresaForm />;
}
