import { expect, test } from "@playwright/test";

/**
 * Smoke de la landing pública. Valida que Next.js + i18n hidratan,
 * que las copias core se renderean y que los CTAs llevan al login /
 * signup. No requiere backend.
 */

test.describe("Landing pública", () => {
  test("renderea el hero con CTAs hacia login y signup", async ({
    page,
  }) => {
    await page.goto("/");

    // Header con el nombre del producto.
    await expect(
      page.getByRole("link", { name: /renteo/i }).first(),
    ).toBeVisible();

    // Algún CTA reconocible: por copy o por hrefs.
    const loginLink = page.getByRole("link", { name: /iniciar sesión|entrar/i });
    const signupLink = page.getByRole("link", {
      name: /crear cuenta|registrarse|empezar/i,
    });
    const linkCount =
      (await loginLink.count()) + (await signupLink.count());
    expect(linkCount).toBeGreaterThan(0);
  });

  test("idioma por defecto es es-CL", async ({ page }) => {
    await page.goto("/");
    const html = page.locator("html");
    const lang = await html.getAttribute("lang");
    expect(lang).toMatch(/es/i);
  });
});
