import { withSentryConfig } from "@sentry/nextjs";
import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin("./src/i18n/request.ts");

const nextConfig: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  typedRoutes: true,
};

// Sentry wrapping. Sin SENTRY_AUTH_TOKEN no sube sourcemaps (CI / dev
// local quedan silenciosos). En prod se setea el token y Sentry recibe
// los maps para des-minificar stack traces.
const sentryConfig = withSentryConfig(withNextIntl(nextConfig), {
  org: process.env.SENTRY_ORG,
  project: process.env.SENTRY_PROJECT,
  silent: !process.env.CI,
  // Soltar logs de sourcemap upload en builds locales sin token.
  disableLogger: true,
  // Telemetry de Sentry CLI: opt-out por default.
  telemetry: false,
});

export default sentryConfig;
