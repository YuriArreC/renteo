import { defineConfig } from "vitest/config";

/**
 * vitest corre los tests unitarios bajo `src/`. Los tests Playwright
 * (`e2e/*.spec.ts`) usan `test.describe` de @playwright/test, que
 * choca con la API de vitest, así que los excluimos explícitamente.
 */
export default defineConfig({
  test: {
    include: ["src/**/*.test.{ts,tsx}"],
    exclude: ["node_modules", "dist", ".next", "e2e/**"],
  },
});
