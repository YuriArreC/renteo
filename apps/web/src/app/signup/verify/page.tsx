"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { type FormEvent, Suspense, useState } from "react";

import { ApiError, fetchApiClient, type MeResponse } from "@/lib/api";
import { createClient } from "@/lib/supabase/client";

export default function SignupVerifyPage() {
  // Next 15 requiere que useSearchParams viva dentro de un <Suspense>
  // boundary para que la generación estática no falle. El fallback es
  // intencionalmente mínimo — la página solo es relevante con la query
  // string presente.
  return (
    <Suspense fallback={null}>
      <SignupVerifyForm />
    </Suspense>
  );
}

function SignupVerifyForm() {
  const t = useTranslations("auth.verify");
  const router = useRouter();
  const searchParams = useSearchParams();
  const email = searchParams.get("email") ?? "";

  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [resending, setResending] = useState(false);
  const [resent, setResent] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);

    if (!email) {
      setSubmitting(false);
      setError(t("missingEmail"));
      return;
    }

    const supabase = createClient();
    const { error: verifyError } = await supabase.auth.verifyOtp({
      email,
      token: code,
      type: "signup",
    });

    if (verifyError) {
      setSubmitting(false);
      setError(verifyError.message);
      return;
    }

    // Verify exitoso → sesión activa. Decidir destino según tenancy.
    try {
      const me = await fetchApiClient<MeResponse>("/api/me");
      router.push(me.workspace ? "/dashboard" : "/onboarding/workspace");
      router.refresh();
    } catch (err) {
      setSubmitting(false);
      setError(err instanceof ApiError ? err.detail : String(err));
    }
  }

  async function handleResend() {
    setError(null);
    setResent(false);
    setResending(true);

    if (!email) {
      setResending(false);
      setError(t("missingEmail"));
      return;
    }

    const supabase = createClient();
    const { error: resendError } = await supabase.auth.resend({
      type: "signup",
      email,
    });

    setResending(false);
    if (resendError) {
      setError(resendError.message);
      return;
    }
    setResent(true);
  }

  return (
    <main className="container max-w-md py-16">
      <h1 className="mb-2 text-3xl font-semibold tracking-tight">
        {t("title")}
      </h1>
      <p className="mb-8 text-sm text-muted-foreground">
        {t("subtitle", { email: email || "—" })}
      </p>

      <form onSubmit={handleSubmit} className="space-y-5">
        <div>
          <label htmlFor="code" className="mb-1 block text-sm font-medium">
            {t("codeLabel")}
          </label>
          <input
            id="code"
            type="text"
            required
            inputMode="numeric"
            pattern="[0-9]{6}"
            maxLength={6}
            autoComplete="one-time-code"
            value={code}
            onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
            placeholder="123456"
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-center font-mono text-lg tracking-widest focus:outline-none focus:ring-2 focus:ring-ring"
          />
          <p className="mt-1 text-xs text-muted-foreground">
            {t("codeHint")}
          </p>
        </div>

        {error && (
          <p className="text-sm text-destructive" role="alert">
            {error}
          </p>
        )}

        {resent && (
          <p className="text-sm text-muted-foreground" role="status">
            {t("resent")}
          </p>
        )}

        <button
          type="submit"
          disabled={submitting || code.length !== 6}
          className="inline-flex h-10 w-full items-center justify-center rounded-md bg-primary font-medium text-primary-foreground disabled:opacity-50"
        >
          {submitting ? t("submitting") : t("submit")}
        </button>
      </form>

      <button
        type="button"
        onClick={handleResend}
        disabled={resending}
        className="mt-6 w-full text-center text-sm text-muted-foreground hover:text-foreground disabled:opacity-50"
      >
        {resending ? t("resending") : t("resend")}
      </button>
    </main>
  );
}
