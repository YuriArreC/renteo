import { redirect } from "next/navigation";

import { OnboardingWorkspaceForm } from "@/app/onboarding/workspace/OnboardingWorkspaceForm";
import { ApiError, type MeResponse } from "@/lib/api";
import { fetchApiServer } from "@/lib/api-server";

export const dynamic = "force-dynamic";

/**
 * Server shell con guard: si el usuario ya tiene workspace, lo
 * mandamos a su home (cartera para cliente B, dashboard para
 * cliente A). Evita crear un segundo workspace por accidente —
 * el API lo rechaza con 409, pero mejor evitarlo en UX antes.
 */
export default async function OnboardingWorkspacePage() {
  let me: MeResponse | null = null;
  try {
    me = await fetchApiServer<MeResponse>("/api/me");
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) {
      redirect("/login");
    }
    // Otros errores: dejamos que el form se renderee; al hacer
    // submit el usuario verá el error real.
  }
  if (me?.workspace) {
    const dest =
      me.workspace.type === "accounting_firm" ? "/cartera" : "/dashboard";
    redirect(dest);
  }
  return <OnboardingWorkspaceForm />;
}
