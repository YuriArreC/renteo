/**
 * Carga la config client-side de Sentry. Next.js 15 espera este archivo
 * (mismo nivel que instrumentation.ts) para inicializar el SDK en el
 * navegador antes del primer render. Sentry v8 instrumenta las
 * transiciones del app router automáticamente vía BrowserTracing.
 */
import "../sentry.client.config";
