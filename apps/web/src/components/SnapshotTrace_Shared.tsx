"use client";

import { useTranslations } from "next-intl";

/**
 * Trace footer — muestra el hash + versiones del set de reglas que
 * produjo el cálculo. Cierra la promesa de skill 11: cualquier
 * decisión del motor queda firmada y verificable. El hash completo
 * va en title para copy-paste; en pantalla se ven los primeros 12.
 */
export function SnapshotTrace_Shared({
  rulesSnapshotHash,
  engineVersion,
  disclaimerVersion,
}: {
  rulesSnapshotHash: string;
  engineVersion: string;
  disclaimerVersion?: string;
}) {
  const t = useTranslations("snapshotTrace");
  const short = rulesSnapshotHash.slice(0, 12);
  return (
    <div className="mt-4 rounded-md border border-border bg-muted/30 p-3 text-[10px] font-mono text-muted-foreground">
      <span className="font-semibold uppercase tracking-wider">
        {t("label")}
      </span>{" "}
      <span title={rulesSnapshotHash}>{short}…</span>
      <span className="mx-2">·</span>
      <span>
        {t("engine")}: {engineVersion}
      </span>
      {disclaimerVersion && (
        <>
          <span className="mx-2">·</span>
          <span>
            {t("disclaimer")}: {disclaimerVersion}
          </span>
        </>
      )}
    </div>
  );
}
