// Next route handler que recibe el callback de Supabase tras confirmar email
// (signup) o login OAuth. Intercambia el code por una sesión y redirige
// según el estado de tenancy del usuario.

import { NextResponse, type NextRequest } from "next/server";

import { fetchApiServer, type MeResponse } from "@/lib/api";
import { createClient } from "@/lib/supabase/server";

export async function GET(request: NextRequest) {
  const { searchParams, origin } = new URL(request.url);
  const code = searchParams.get("code");

  if (!code) {
    return NextResponse.redirect(
      `${origin}/login?error=missing_code`,
    );
  }

  const supabase = await createClient();
  const { error: exchangeError } =
    await supabase.auth.exchangeCodeForSession(code);

  if (exchangeError) {
    return NextResponse.redirect(
      `${origin}/login?error=${encodeURIComponent(exchangeError.message)}`,
    );
  }

  try {
    const me = await fetchApiServer<MeResponse>("/api/me");
    const target = me.workspace ? "/dashboard" : "/onboarding/workspace";
    return NextResponse.redirect(`${origin}${target}`);
  } catch {
    // Si /api/me no responde (backend caído), enviamos al onboarding —
    // el JWT igual quedó establecido y el usuario puede continuar.
    return NextResponse.redirect(`${origin}/onboarding/workspace`);
  }
}
