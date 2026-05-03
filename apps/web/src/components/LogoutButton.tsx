"use client";

import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { Button } from "@/components/ui/button";
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
    <Button
      type="button"
      variant="ghost"
      size="sm"
      onClick={handleLogout}
      disabled={submitting}
    >
      {t("logout")}
    </Button>
  );
}
