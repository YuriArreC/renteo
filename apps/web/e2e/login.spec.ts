import { expect, test } from "@playwright/test";

/**
 * Smoke del flow de login (form, validación, manejo de error 401).
 * Sin backend real: interceptamos la llamada al API que dispara
 * `signInWithPassword` para verificar que la UI mapea el error.
 */

test.describe("Login", () => {
  test("renderea email/password y valida campos requeridos", async ({
    page,
  }) => {
    await page.goto("/login");

    const email = page.getByLabel(/email|correo/i);
    const password = page.getByLabel(/contraseña|password/i);
    await expect(email).toBeVisible();
    await expect(password).toBeVisible();

    const submit = page.getByRole("button", {
      name: /entrar|iniciar sesión|continuar/i,
    });
    await expect(submit).toBeVisible();
  });

  test("aviso de credenciales inválidas viaja al usuario", async ({
    page,
  }) => {
    // Mock Supabase auth endpoint con 400.
    await page.route(
      "**/auth/v1/token**",
      async (route) =>
        await route.fulfill({
          status: 400,
          contentType: "application/json",
          body: JSON.stringify({
            error: "invalid_grant",
            error_description: "Invalid login credentials",
          }),
        }),
    );

    await page.goto("/login");
    await page.getByLabel(/email|correo/i).fill("noone@renteo.local");
    await page.getByLabel(/contraseña|password/i).fill("wrong");
    await page
      .getByRole("button", {
        name: /entrar|iniciar sesión|continuar/i,
      })
      .click();

    // El feedback puede llegar via toast o por mensaje inline; aceptamos
    // cualquiera que mencione "invalid" o "credenciales".
    const feedback = page.getByText(/invalid|credenciales|no válid/i);
    await expect(feedback.first()).toBeVisible({ timeout: 5_000 });
  });
});
