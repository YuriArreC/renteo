/**
 * Mapeo de errores de Supabase Auth a mensajes user-friendly es-CL.
 *
 * El SDK de Supabase devuelve `error.message` en inglés con códigos
 * variados según la versión. Este helper normaliza los más comunes
 * para que el usuario final no vea "Email rate limit exceeded" sin
 * contexto.
 *
 * Mantén el fallback al `error.message` original cuando no hay
 * mapping conocido — evita silenciar errores nuevos que merezcan
 * atención.
 */

export interface AuthErrorLike {
  message?: string;
  code?: string;
  status?: number;
  name?: string;
}

/**
 * Mapeo case-insensitive parcial: busca el patrón `key` dentro del
 * `message` original y devuelve la traducción. Suficiente para los
 * mensajes que Supabase formatea con detalles dinámicos.
 */
const _PATTERNS: Array<{ pattern: RegExp; mapped: string }> = [
  {
    pattern: /already\s+registered|already\s+exists|user.*exists/i,
    mapped:
      "Este correo ya está registrado. Si es tu cuenta, " +
      "inicia sesión; si la olvidaste, usa la opción de recuperar contraseña.",
  },
  {
    pattern: /invalid\s+login\s+credentials|invalid\s+grant/i,
    mapped: "Correo o contraseña incorrectos.",
  },
  {
    pattern: /token\s+has\s+expired|expired\s+token|otp.*expired/i,
    mapped:
      "El código expiró. Pide uno nuevo con 'Reenviar' y vuelve a " +
      "intentar.",
  },
  {
    pattern: /invalid\s+token|invalid\s+otp|token.*not.*found/i,
    mapped:
      "Código inválido. Revisa que ingresaste los dígitos correctos " +
      "y que sea el más reciente.",
  },
  {
    pattern: /rate\s+limit|too\s+many\s+requests/i,
    mapped:
      "Demasiados intentos. Espera unos minutos antes de volver a " +
      "intentar.",
  },
  {
    pattern: /email\s+not\s+confirmed|confirm.*email/i,
    mapped:
      "Tu correo aún no fue verificado. Revisa tu casilla y haz clic " +
      "en el enlace, o ingresa el código en /signup/verify.",
  },
  {
    pattern:
      /password.*too\s+short|password.*length|weak\s+password|password.*at\s+least/i,
    mapped: "La contraseña es demasiado corta. Usa al menos 8 caracteres.",
  },
  {
    pattern: /network|fetch\s+failed|failed\s+to\s+fetch/i,
    mapped:
      "No pudimos conectar con el servidor de autenticación. Revisa " +
      "tu conexión y vuelve a intentar.",
  },
];

const _CODE_MAP: Record<string, string> = {
  user_already_exists:
    "Este correo ya está registrado. Inicia sesión o recupera la " +
    "contraseña.",
  email_address_invalid: "El correo electrónico no es válido.",
  weak_password: "La contraseña es demasiado débil. Usa al menos 8 caracteres.",
  invalid_credentials: "Correo o contraseña incorrectos.",
  email_not_confirmed:
    "Tu correo aún no fue verificado. Revisa tu casilla.",
  otp_expired:
    "El código expiró. Pide uno nuevo y vuelve a intentar.",
  signup_disabled:
    "El registro está temporalmente deshabilitado. Vuelve a intentar " +
    "en unos minutos.",
};

export function mapAuthError(err: unknown): string {
  if (!err) return "Error desconocido.";
  const e = err as AuthErrorLike;

  if (e.code) {
    const mapped = _CODE_MAP[e.code];
    if (mapped) return mapped;
  }

  const msg = e.message ?? "";
  for (const { pattern, mapped } of _PATTERNS) {
    if (pattern.test(msg)) return mapped;
  }

  // Fallback: el mensaje crudo. Útil para diagnosticar errores nuevos
  // que no están en el catálogo todavía.
  return msg || "Error de autenticación.";
}
