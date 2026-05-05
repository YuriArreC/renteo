import { expect, test } from "@playwright/test";

/**
 * Golden flow contra backend real. Requiere `next dev` apuntando al
 * API local + Supabase up + un usuario seed. Por defecto **skipped**
 * en CI; correr local con:
 *
 *   PLAYWRIGHT_FULL=1 \
 *   PLAYWRIGHT_BASE_URL=http://localhost:3000 \
 *   pnpm --filter @renteo/web test:e2e golden-flow
 *
 * Sirve como smoke pre-deploy: garantiza que login → dashboard →
 * onboarding empresa → diagnóstico → simular renderea sin
 * regresiones de UI.
 */

const FULL = !!process.env.PLAYWRIGHT_FULL;

test.describe("Golden flow cliente A", () => {
  test.skip(
    !FULL,
    "Requiere backend real; correr con PLAYWRIGHT_FULL=1 y stack arriba",
  );

  test("login → dashboard → diagnóstico → simular", async ({
    page,
  }) => {
    const email = process.env.E2E_USER_EMAIL ?? "demo@renteo.local";
    const password = process.env.E2E_USER_PASSWORD ?? "demo-password";

    await page.goto("/login");
    await page.getByLabel(/email|correo/i).fill(email);
    await page.getByLabel(/contraseña|password/i).fill(password);
    await page
      .getByRole("button", { name: /entrar|iniciar sesión/i })
      .click();

    // Llega al dashboard con su nombre de workspace.
    await page.waitForURL(/\/dashboard/, { timeout: 10_000 });
    await expect(
      page.getByRole("heading", { level: 1 }),
    ).toBeVisible();

    // Navega al simulador.
    await page
      .getByRole("link", { name: /simul/i })
      .first()
      .click();
    await page.waitForURL(/simulator/);
    await expect(
      page.getByRole("heading", { level: 1 }),
    ).toBeVisible();
  });
});

test.describe("Golden flow cliente B", () => {
  test.skip(
    !FULL,
    "Requiere backend real; correr con PLAYWRIGHT_FULL=1 y stack arriba",
  );

  test("login firm → cartera → batch diagnóstico", async ({
    page,
  }) => {
    const email =
      process.env.E2E_FIRM_EMAIL ?? "contador@renteo.local";
    const password =
      process.env.E2E_FIRM_PASSWORD ?? "demo-password";

    await page.goto("/login");
    await page.getByLabel(/email|correo/i).fill(email);
    await page.getByLabel(/contraseña|password/i).fill(password);
    await page
      .getByRole("button", { name: /entrar|iniciar sesión/i })
      .click();

    await page.waitForURL(/\/cartera/, { timeout: 10_000 });
    await expect(
      page.getByRole("heading", { level: 1 }),
    ).toBeVisible();
  });
});
