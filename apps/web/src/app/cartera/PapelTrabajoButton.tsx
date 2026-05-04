"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import { toast } from "@/components/ui/sonner";
import { createClient } from "@/lib/supabase/client";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export function PapelTrabajoButton({
  empresaId,
  razonSocial,
  rut,
}: {
  empresaId: string;
  razonSocial: string;
  rut: string;
}) {
  const t = useTranslations("cartera.table");
  const [pending, setPending] = useState(false);

  const onClick = async () => {
    setPending(true);
    try {
      const supabase = createClient();
      const {
        data: { session },
      } = await supabase.auth.getSession();
      const headers: HeadersInit = {};
      if (session?.access_token) {
        headers["Authorization"] = `Bearer ${session.access_token}`;
      }
      const response = await fetch(
        `${API_URL}/api/empresas/${empresaId}/papel-trabajo.xlsx`,
        { headers },
      );
      if (!response.ok) {
        const detail = await response.text().catch(() => response.statusText);
        throw new Error(detail);
      }
      const blob = await response.blob();
      const compactRut = rut.replace(/[.-]/g, "");
      const safeName = razonSocial
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/^-+|-+$/g, "")
        .slice(0, 40) || "empresa";
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `papel-trabajo-${safeName}-${compactRut}.xlsx`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(a.href);
      toast.success(t("papelDescargado", { razon: razonSocial }));
    } catch (err) {
      toast.error(
        t("papelError", {
          error: err instanceof Error ? err.message : String(err),
        }),
      );
    } finally {
      setPending(false);
    }
  };

  return (
    <Button
      size="sm"
      variant="ghost"
      disabled={pending}
      onClick={onClick}
    >
      {pending ? t("papelDescargando") : t("papelTrabajo")}
    </Button>
  );
}
