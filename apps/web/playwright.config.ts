import { defineConfig, devices } from "@playwright/test";

/**
 * Configuración Playwright e2e (skill 9 — golden flows).
 *
 * Estrategia: el front se levanta con `next dev` apuntando a un
 * backend mock. Los tests interceptan llamadas /api/* con
 * page.route() y devuelven respuestas canned. Esto mantiene el job
 * de CI rápido (sin DB ni API real) y enfocado en validar la UX
 * (forms, navegación, render, role gates).
 *
 * Para una corrida con backend real (smoke pre-deploy), levantar
 * la API + Supabase + frontend manualmente y correr con
 * `PLAYWRIGHT_BASE_URL=http://localhost:3000 pnpm test:e2e`.
 */

const PORT = Number(process.env.PLAYWRIGHT_PORT ?? 3100);
const BASE_URL =
  process.env.PLAYWRIGHT_BASE_URL ?? `http://localhost:${PORT}`;

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI ? "github" : "list",
  timeout: 30_000,
  use: {
    baseURL: BASE_URL,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: process.env.PLAYWRIGHT_BASE_URL
    ? undefined
    : {
        command: `npx next dev --turbopack -p ${PORT}`,
        url: BASE_URL,
        reuseExistingServer: !process.env.CI,
        timeout: 120_000,
        env: {
          NEXT_PUBLIC_API_URL: "http://localhost:0",
          NEXT_PUBLIC_SUPABASE_URL: "https://e2e.example.supabase.co",
          NEXT_PUBLIC_SUPABASE_ANON_KEY: "e2e-anon-key",
        },
      },
});
