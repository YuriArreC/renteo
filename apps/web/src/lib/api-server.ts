// Cliente HTTP para Server Components y route handlers.
// Importa `next/headers` (vía Supabase server client) — NO usar desde
// Client Components, eso rompería el bundling. La separación física en
// `api.ts` (cliente) y `api-server.ts` (servidor) garantiza que el
// bundler no arrastre next/headers a los Client Components.

import { _fetch } from "@/lib/api";
import { createClient as createServerClient } from "@/lib/supabase/server";

export async function fetchApiServer<T = unknown>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const supabase = await createServerClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();
  return _fetch<T>(path, session?.access_token ?? null, init);
}
