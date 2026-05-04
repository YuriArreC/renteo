/**
 * Sentry config — runtime edge (middleware Next.js).
 * Edge runtime tiene un subset reducido de APIs; mantenemos init mínimo.
 */
import * as Sentry from "@sentry/nextjs";

const dsn = process.env.SENTRY_DSN ?? process.env.NEXT_PUBLIC_SENTRY_DSN;

if (dsn) {
  Sentry.init({
    dsn,
    environment: process.env.NEXT_PUBLIC_ENV ?? "development",
    release: process.env.NEXT_PUBLIC_APP_VERSION,
    sampleRate: 1.0,
    tracesSampleRate: 0.1,
    sendDefaultPii: false,
  });
}
