/**
 * Sentry config — runtime browser. Se carga vía instrumentation-client.ts.
 *
 * Sin DSN no hace nada (CI / dev local). En prod captura errores
 * automáticos del client (componentes, hooks, fetch) y suma el
 * `request_id` del backend a los breadcrumbs vía `tracePropagationTargets`.
 */
import * as Sentry from "@sentry/nextjs";

const dsn = process.env.NEXT_PUBLIC_SENTRY_DSN;

if (dsn) {
  Sentry.init({
    dsn,
    environment: process.env.NEXT_PUBLIC_ENV ?? "development",
    release: process.env.NEXT_PUBLIC_APP_VERSION,
    // Captura errores no controlados de UI sin samplear: queremos verlos todos.
    sampleRate: 1.0,
    // Tracing: 10% en prod (ajustar si hay ruido). El sampler de Next.js
    // respeta el `tracesSampleRate` global cuando no hay decisión upstream.
    tracesSampleRate: 0.1,
    // Permite que Sentry inyecte `sentry-trace` + `baggage` headers en
    // fetches al backend Renteo (mismo origen lógico) para correlacionar
    // con las trazas del FastAPI.
    tracePropagationTargets: [
      "localhost",
      /^\/api\//,
      /^https:\/\/[^/]*renteo[^/]*\//,
    ],
    // PII fuera por default — nuestros logs ya enmascaran RUTs y JWTs.
    sendDefaultPii: false,
  });
}
