"use client";

import { useTranslations } from "next-intl";

import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  type DiagnoseResponse,
  type RegimeProjection,
} from "@/lib/api";

function formatCLP(value: string | number): string {
  const n = typeof value === "string" ? Number(value) : value;
  return new Intl.NumberFormat("es-CL", {
    style: "currency",
    currency: "CLP",
    maximumFractionDigits: 0,
  }).format(n);
}

function formatUF(value: string | number): string {
  const n = typeof value === "string" ? Number(value) : value;
  return `${new Intl.NumberFormat("es-CL", { maximumFractionDigits: 2 }).format(n)} UF`;
}

const REGIMEN_LABEL: Record<string, string> = {
  "14_a": "14 A",
  "14_d_3": "14 D N°3",
  "14_d_8": "14 D N°8",
  renta_presunta: "Renta presunta",
};

export function RegimeResult({ data }: { data: DiagnoseResponse }) {
  const t = useTranslations("regime.result");

  return (
    <div className="space-y-8">
      <Card>
        <CardHeader>
          <CardTitle>{t("veredictoHeader")}</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-6 md:grid-cols-3">
          <Stat
            label={t("currentRegimen")}
            value={
              REGIMEN_LABEL[data.veredicto.regimen_actual] ??
              data.veredicto.regimen_actual
            }
          />
          <Stat
            label={t("recomendado")}
            value={
              REGIMEN_LABEL[data.veredicto.regimen_recomendado] ??
              data.veredicto.regimen_recomendado
            }
            highlight
          />
          <Stat
            label={t("ahorro3a")}
            value={formatCLP(data.veredicto.ahorro_3a_clp)}
            sub={formatUF(data.veredicto.ahorro_3a_uf)}
            highlight={Number(data.veredicto.ahorro_3a_clp) > 0}
          />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">
            {t("elegibilidadHeader")}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-5">
          {data.elegibilidad.map((e) => (
            <div
              key={e.regimen}
              className="border-l-2 border-border pl-4"
            >
              <div className="flex items-baseline justify-between gap-4">
                <span className="text-sm font-medium">{e.label}</span>
                <span
                  className={`text-xs font-medium ${
                    e.elegible ? "text-green-700" : "text-destructive"
                  }`}
                >
                  {e.elegible ? `✓ ${t("elegible")}` : `✗ ${t("noElegible")}`}
                </span>
              </div>
              <ul className="mt-2 space-y-1 text-xs text-muted-foreground">
                {e.requisitos.map((r, idx) => (
                  <li key={idx}>
                    <span
                      className={
                        r.ok ? "text-green-700" : "text-destructive"
                      }
                    >
                      {r.ok ? "✓" : "✗"}
                    </span>{" "}
                    {r.texto}{" "}
                    <span className="text-muted-foreground/70">
                      ({r.fundamento})
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">{t("proyeccionHeader")}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          {data.proyecciones.map((p) => (
            <ProjectionTable key={p.regimen} proj={p} t={t} />
          ))}
        </CardContent>
      </Card>

      {data.proyeccion_dual_14d3 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">{t("dualHeader")}</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-6 md:grid-cols-2">
            <div>
              <div className="mb-2 text-xs font-semibold uppercase text-muted-foreground">
                {t("dualBase")}
              </div>
              <ProjectionTable
                proj={data.proyeccion_dual_14d3.base}
                t={t}
                hideHeader
              />
              {data.proyeccion_dual_14d3.base.nota && (
                <p className="mt-2 text-xs text-muted-foreground">
                  {data.proyeccion_dual_14d3.base.nota}
                </p>
              )}
            </div>
            <div>
              <div className="mb-2 text-xs font-semibold uppercase text-muted-foreground">
                {t("dualRevertido")}
              </div>
              <ProjectionTable
                proj={data.proyeccion_dual_14d3.revertido}
                t={t}
                hideHeader
              />
              {data.proyeccion_dual_14d3.revertido.nota && (
                <p className="mt-2 text-xs text-muted-foreground">
                  {data.proyeccion_dual_14d3.revertido.nota}
                </p>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">{t("riesgosHeader")}</CardTitle>
        </CardHeader>
        <CardContent>
          <ul className="space-y-2 text-sm">
            {data.riesgos.map((r, idx) => (
              <li key={idx} className="flex gap-2">
                <span className="text-muted-foreground">·</span>
                <span>{r}</span>
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">{t("fuenteHeader")}</CardTitle>
        </CardHeader>
        <CardContent>
          <ul className="space-y-1 text-xs text-muted-foreground">
            {data.fuente_legal.map((f, idx) => (
              <li key={idx}>· {f}</li>
            ))}
          </ul>
        </CardContent>
      </Card>

      <p className="rounded border border-yellow-300 bg-yellow-50 p-3 text-xs text-yellow-900">
        {data.disclaimer}
      </p>
    </div>
  );
}

function Stat({
  label,
  value,
  sub,
  highlight = false,
}: {
  label: string;
  value: string;
  sub?: string;
  highlight?: boolean;
}) {
  return (
    <div
      className={`rounded-md p-4 ${
        highlight ? "bg-primary/5" : "bg-muted/40"
      }`}
    >
      <div className="text-xs uppercase text-muted-foreground">{label}</div>
      <div className="mt-1 text-xl font-semibold">{value}</div>
      {sub && <div className="text-xs text-muted-foreground">{sub}</div>}
    </div>
  );
}

function ProjectionTable({
  proj,
  t,
  hideHeader = false,
}: {
  proj: RegimeProjection;
  t: ReturnType<typeof useTranslations<"regime.result">>;
  hideHeader?: boolean;
}) {
  return (
    <div>
      {!hideHeader && (
        <div className="mb-2 flex items-baseline justify-between">
          <span className="text-sm font-medium">{proj.label}</span>
          {proj.es_transitoria && (
            <span className="rounded bg-yellow-100 px-2 py-0.5 text-xs text-yellow-900">
              {t("transitoria")}
            </span>
          )}
        </div>
      )}
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-border bg-muted/40 text-left">
              <th className="p-2 font-medium">{t("year")}</th>
              <th className="p-2 text-right font-medium">{t("rli")}</th>
              <th className="p-2 text-right font-medium">{t("idpc")}</th>
              <th className="p-2 text-right font-medium">{t("retiros")}</th>
              <th className="p-2 text-right font-medium">{t("igc")}</th>
              <th className="p-2 text-right font-medium">{t("total")}</th>
            </tr>
          </thead>
          <tbody>
            {proj.rows.map((r) => (
              <tr key={r.año} className="border-b border-border">
                <td className="p-2 font-medium">{r.año}</td>
                <td className="p-2 text-right font-mono">
                  {formatCLP(r.rli)}
                </td>
                <td className="p-2 text-right font-mono">
                  {formatCLP(r.idpc)}
                </td>
                <td className="p-2 text-right font-mono">
                  {formatCLP(r.retiros)}
                </td>
                <td className="p-2 text-right font-mono">
                  {formatCLP(r.igc_dueno)}
                </td>
                <td className="p-2 text-right font-mono font-semibold">
                  {formatCLP(r.carga_total)}
                </td>
              </tr>
            ))}
            <tr className="bg-primary/5">
              <td className="p-2 font-semibold" colSpan={5}>
                {t("total3a")}
              </td>
              <td className="p-2 text-right font-mono font-semibold">
                {formatCLP(proj.total_3a)}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}
