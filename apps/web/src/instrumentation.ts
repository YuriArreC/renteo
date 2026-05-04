/**
 * Next.js 15 instrumentation hook. Carga el config Sentry según runtime
 * (`nodejs` o `edge`). Sin DSN, los configs son no-op.
 *
 * Doc: https://nextjs.org/docs/app/api-reference/file-conventions/instrumentation
 */
export async function register(): Promise<void> {
  if (process.env.NEXT_RUNTIME === "nodejs") {
    await import("../sentry.server.config");
  }
  if (process.env.NEXT_RUNTIME === "edge") {
    await import("../sentry.edge.config");
  }
}

// Captura errores de Server Components / Route Handlers que escapan al
// boundary de React. Sentry lo expone como callback dedicado en Next 15.
export { captureRequestError as onRequestError } from "@sentry/nextjs";
