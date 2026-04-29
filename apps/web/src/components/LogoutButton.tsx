"use client";

import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { createClient } from "@/lib/supabase/client";

export function LogoutButton() {
  const t = useTranslations("dashboard.header");
  const router = useRouter();
  const [submitting, setSubmitting] = useState(false);

  async function handleLogout() {
    setSubmitting(true);
    const supabase = createClient();
    await supabase.auth.signOut();
    router.push("/");
    router.refresh();
  }

  return (
    <button
      type="button"
      onClick={handleLogout}
      disabled={submitting}
      className="text-sm text-muted-foreground hover:text-foreground disabled:opacity-50"
    >
      {t("logout")}
    </button>
  );
}
