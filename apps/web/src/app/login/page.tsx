"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { type FormEvent, useState } from "react";

import { ApiError, fetchApiClient, type MeResponse } from "@/lib/api";
import { createClient } from "@/lib/supabase/client";

export default function LoginPage() {
  const t = useTranslations("auth.login");
  const router = useRouter();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);

    const supabase = createClient();
    const { error: signInError } = await supabase.auth.signInWithPassword({
      email,
      password,
    });

    if (signInError) {
      setSubmitting(false);
      setError(signInError.message);
      return;
    }

    try {
      const me = await fetchApiClient<MeResponse>("/api/me");
      if (me.workspace) {
        router.push("/dashboard");
      } else {
        router.push("/onboarding/workspace");
      }
      router.refresh();
    } catch (err) {
      setSubmitting(false);
      setError(err instanceof ApiError ? err.detail : String(err));
    }
  }

  return (
    <main className="container max-w-md py-16">
      <h1 className="mb-8 text-3xl font-semibold tracking-tight">
        {t("title")}
      </h1>

      <form onSubmit={handleSubmit} className="space-y-5">
        <div>
          <label
            htmlFor="login-email"
            className="mb-1 block text-sm font-medium"
          >
            {t("email")}
          </label>
          <input
            id="login-email"
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
            htmlFor="login-password"
            className="mb-1 block text-sm font-medium"
          >
            {t("password")}
          </label>
          <input
            id="login-password"
            type="password"
            required
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </div>

        {error && (
          <p className="text-sm text-destructive" role="alert">
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={submitting}
          className="inline-flex h-10 w-full items-center justify-center rounded-md bg-primary font-medium text-primary-foreground disabled:opacity-50"
        >
          {submitting ? t("submitting") : t("submit")}
        </button>
      </form>

      <p className="mt-6 text-center text-sm">
        <Link href="/signup" className="underline hover:text-foreground">
          {t("noAccount")}
        </Link>
      </p>
    </main>
  );
}
