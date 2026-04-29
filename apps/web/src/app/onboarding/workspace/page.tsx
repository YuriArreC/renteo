"use client";

import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { type FormEvent, useState } from "react";

import {
  ApiError,
  type CreateWorkspaceReq,
  type CreateWorkspaceResp,
  fetchApiClient,
  type WorkspaceType,
} from "@/lib/api";
import { createClient } from "@/lib/supabase/client";

export default function OnboardingWorkspacePage() {
  const t = useTranslations("onboarding.workspace");
  const router = useRouter();

  const [name, setName] = useState("");
  const [type, setType] = useState<WorkspaceType>("pyme");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);

    const payload: CreateWorkspaceReq = {
      name: name.trim(),
      type,
      consent_tratamiento_datos: true,
    };

    try {
      await fetchApiClient<CreateWorkspaceResp>("/api/workspaces", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      // Refrescar JWT para que el Auth Hook re-ejecute con el nuevo
      // workspace y la tenancy quede inyectada en los claims.
      const supabase = createClient();
      await supabase.auth.refreshSession();

      router.push("/dashboard");
      router.refresh();
    } catch (err) {
      setSubmitting(false);
      setError(err instanceof ApiError ? err.detail : String(err));
    }
  }

  return (
    <main className="container max-w-xl py-16">
      <h1 className="mb-2 text-3xl font-semibold tracking-tight">
        {t("title")}
      </h1>
      <p className="mb-10 text-sm text-muted-foreground">{t("subtitle")}</p>

      <form onSubmit={handleSubmit} className="space-y-8">
        <div>
          <label
            htmlFor="ws-name"
            className="mb-1 block text-sm font-medium"
          >
            {t("nameLabel")}
          </label>
          <input
            id="ws-name"
            type="text"
            required
            maxLength={120}
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder={t("namePlaceholder")}
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </div>

        <fieldset>
          <legend className="mb-3 block text-sm font-medium">
            {t("typeLabel")}
          </legend>
          <div className="space-y-3">
            <label
              className={`flex cursor-pointer flex-col gap-1 rounded-lg border p-4 ${
                type === "pyme"
                  ? "border-primary bg-accent"
                  : "border-border"
              }`}
            >
              <span className="flex items-center gap-3">
                <input
                  type="radio"
                  name="type"
                  value="pyme"
                  checked={type === "pyme"}
                  onChange={() => setType("pyme")}
                  className="h-4 w-4"
                />
                <span className="font-medium">{t("typePyme")}</span>
              </span>
              <span className="ml-7 text-sm text-muted-foreground">
                {t("typePymeBody")}
              </span>
            </label>

            <label
              className={`flex cursor-pointer flex-col gap-1 rounded-lg border p-4 ${
                type === "accounting_firm"
                  ? "border-primary bg-accent"
                  : "border-border"
              }`}
            >
              <span className="flex items-center gap-3">
                <input
                  type="radio"
                  name="type"
                  value="accounting_firm"
                  checked={type === "accounting_firm"}
                  onChange={() => setType("accounting_firm")}
                  className="h-4 w-4"
                />
                <span className="font-medium">
                  {t("typeAccountingFirm")}
                </span>
              </span>
              <span className="ml-7 text-sm text-muted-foreground">
                {t("typeAccountingFirmBody")}
              </span>
            </label>
          </div>
        </fieldset>

        {error && (
          <p className="text-sm text-destructive" role="alert">
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={submitting || !name.trim()}
          className="inline-flex h-10 w-full items-center justify-center rounded-md bg-primary font-medium text-primary-foreground disabled:opacity-50"
        >
          {submitting ? t("submitting") : t("submit")}
        </button>
      </form>
    </main>
  );
}
