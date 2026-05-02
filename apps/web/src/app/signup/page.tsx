"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { type FormEvent, useState } from "react";

import { createClient } from "@/lib/supabase/client";

export default function SignupPage() {
  const t = useTranslations("auth.signup");
  const router = useRouter();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [consent, setConsent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);

    if (!consent) {
      setError(t("consentRequired"));
      return;
    }

    setSubmitting(true);
    const supabase = createClient();
    // Sin `emailRedirectTo` Supabase manda solo el código OTP en el email
    // (no link PKCE). El flujo siguiente es /signup/verify donde el user
    // pega el código de 6 dígitos. Esto es robusto contra Gmail prefetch
    // y no depende de cookies entre tabs.
    const { error: signUpError } = await supabase.auth.signUp({
      email,
      password,
    });
    setSubmitting(false);

    if (signUpError) {
      setError(signUpError.message);
      return;
    }
    router.push(`/signup/verify?email=${encodeURIComponent(email)}`);
    router.refresh();
  }

  return (
    <main className="container max-w-md py-16">
      <h1 className="mb-2 text-3xl font-semibold tracking-tight">
        {t("title")}
      </h1>
      <p className="mb-8 text-sm text-muted-foreground">{t("subtitle")}</p>

      <form onSubmit={handleSubmit} className="space-y-5">
        <div>
          <label
            htmlFor="signup-email"
            className="mb-1 block text-sm font-medium"
          >
            {t("email")}
          </label>
          <input
            id="signup-email"
            type="email"
            required
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </div>

        <div>
          <label
            htmlFor="signup-password"
            className="mb-1 block text-sm font-medium"
          >
            {t("password")}
          </label>
          <input
            id="signup-password"
            type="password"
            required
            minLength={8}
            autoComplete="new-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          />
          <p className="mt-1 text-xs text-muted-foreground">
            {t("passwordHint")}
          </p>
        </div>

        <label className="flex items-start gap-3 text-sm">
          <input
            type="checkbox"
            checked={consent}
            onChange={(e) => setConsent(e.target.checked)}
            className="mt-0.5 h-4 w-4 rounded border-border"
          />
          <span className="text-muted-foreground">
            {t.rich("consentLabel", {
              politica: (chunks) => (
                <Link
                  href="/legal/privacidad"
                  className="underline hover:text-foreground"
                >
                  {chunks}
                </Link>
              ),
              terminos: (chunks) => (
                <Link
                  href="/legal/terminos"
                  className="underline hover:text-foreground"
                >
                  {chunks}
                </Link>
              ),
            })}
          </span>
        </label>

        {error && (
          <p className="text-sm text-destructive" role="alert">
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={submitting || !consent}
          className="inline-flex h-10 w-full items-center justify-center rounded-md bg-primary font-medium text-primary-foreground disabled:opacity-50"
        >
          {submitting ? t("submitting") : t("submit")}
        </button>
      </form>

      <p className="mt-6 text-center text-sm">
        <Link href="/login" className="underline hover:text-foreground">
          {t("haveAccount")}
        </Link>
      </p>
    </main>
  );
}
