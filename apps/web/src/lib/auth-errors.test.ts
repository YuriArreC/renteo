import { describe, expect, it } from "vitest";

import { mapAuthError } from "./auth-errors";

describe("mapAuthError", () => {
  it("traduce email ya registrado", () => {
    expect(
      mapAuthError({ message: "User already registered" }),
    ).toMatch(/ya está registrado/i);
  });

  it("traduce credenciales inválidas", () => {
    expect(
      mapAuthError({ message: "Invalid login credentials" }),
    ).toMatch(/incorrectos/i);
  });

  it("traduce token expirado", () => {
    expect(
      mapAuthError({ message: "Token has expired" }),
    ).toMatch(/expiró/i);
  });

  it("traduce código OTP inválido", () => {
    expect(
      mapAuthError({ message: "Invalid OTP" }),
    ).toMatch(/inválido/i);
  });

  it("traduce rate limit", () => {
    expect(
      mapAuthError({ message: "email rate limit exceeded" }),
    ).toMatch(/demasiados intentos/i);
  });

  it("traduce email sin confirmar", () => {
    expect(
      mapAuthError({ message: "Email not confirmed" }),
    ).toMatch(/aún no fue verificado/i);
  });

  it("traduce password débil", () => {
    expect(
      mapAuthError({ message: "Password should be at least 6 characters" }),
    ).toMatch(/al menos 8 caracteres/i);
  });

  it("traduce error de red", () => {
    expect(mapAuthError({ message: "Failed to fetch" })).toMatch(
      /conexión/i,
    );
  });

  it("usa mapping por code antes que por message", () => {
    expect(mapAuthError({ code: "user_already_exists" })).toMatch(
      /ya está registrado/i,
    );
  });

  it("fallback al mensaje original cuando no hay mapping", () => {
    const original = "Algún error nuevo no mapeado";
    expect(mapAuthError({ message: original })).toBe(original);
  });

  it("maneja error vacío", () => {
    expect(mapAuthError(null)).toMatch(/desconocido/i);
    expect(mapAuthError(undefined)).toMatch(/desconocido/i);
    expect(mapAuthError({})).toMatch(/autenticación/i);
  });
});
