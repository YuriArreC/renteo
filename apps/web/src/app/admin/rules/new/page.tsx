"use client";

import { useMutation } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "@/components/ui/sonner";
import {
  ApiError,
  type CreateRuleDraftRequest,
  fetchApiClient,
  type RuleSetSummary,
  type ValidateSchemaRequest,
  type ValidateSchemaResponse,
} from "@/lib/api";

const DEFAULT_RULES = `{
  "all_of": [
    {
      "field": "ingresos_promedio_3a_uf",
      "op": "lte",
      "value": 75000,
      "fundamento": "art. 14 D N°3 LIR"
    }
  ]
}`;

const DEFAULT_FUENTE = `[
  {"tipo": "ley", "id": "21.210"},
  {"tipo": "lir", "articulo": "art. 14 D N°3"}
]`;

export default function NewRulePage() {
  const t = useTranslations("adminRules");
  const tForm = useTranslations("adminRules.form");
  const router = useRouter();

  const [domain, setDomain] = useState("regime_eligibility");
  const [key, setKey] = useState("");
  const [vigenciaDesde, setVigenciaDesde] = useState("2027-01-01");
  const [vigenciaHasta, setVigenciaHasta] = useState("");
  const [rulesText, setRulesText] = useState(DEFAULT_RULES);
  const [fuenteText, setFuenteText] = useState(DEFAULT_FUENTE);
  const [domainsKnown, setDomainsKnown] = useState<string[]>([
    "regime_eligibility",
    "recomendacion_whitelist",
    "palanca_definition",
    "red_flag",
    "rli_formula",
    "credit_imputation_order",
  ]);
  const [validation, setValidation] =
    useState<ValidateSchemaResponse | null>(null);

  const validateMutation = useMutation({
    mutationFn: (req: ValidateSchemaRequest) =>
      fetchApiClient<ValidateSchemaResponse>(
        "/api/admin/rules/validate-schema",
        {
          method: "POST",
          body: JSON.stringify(req),
        },
      ),
    onSuccess: (data) => {
      setValidation(data);
      if (data.domains_disponibles.length > 0) {
        setDomainsKnown(data.domains_disponibles);
      }
    },
    onError: (err) =>
      toast.error(err instanceof ApiError ? err.detail : String(err)),
  });

  const createMutation = useMutation({
    mutationFn: (req: CreateRuleDraftRequest) =>
      fetchApiClient<RuleSetSummary>("/api/admin/rules", {
        method: "POST",
        body: JSON.stringify(req),
      }),
    onSuccess: (rule) => {
      toast.success(tForm("savedToast", { version: rule.version }));
      router.push(`/admin/rules/${rule.id}`);
    },
    onError: (err) =>
      toast.error(err instanceof ApiError ? err.detail : String(err)),
  });

  // Cuando cambia el textarea de rules, invalidar el badge.
  useEffect(() => {
    setValidation(null);
  }, [rulesText, domain]);

  const onValidate = () => {
    let parsed: Record<string, unknown>;
    try {
      parsed = JSON.parse(rulesText);
    } catch (err) {
      setValidation({
        valid: false,
        domains_disponibles: domainsKnown,
        errors: [{ path: "$", message: String(err) }],
      });
      return;
    }
    validateMutation.mutate({ domain, rules: parsed });
  };

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!validation || !validation.valid) {
      toast.error(tForm("needValidate"));
      return;
    }
    let rulesParsed: Record<string, unknown>;
    let fuenteParsed: Array<Record<string, unknown>>;
    try {
      rulesParsed = JSON.parse(rulesText);
    } catch (err) {
      toast.error(String(err));
      return;
    }
    try {
      fuenteParsed = JSON.parse(fuenteText);
      if (!Array.isArray(fuenteParsed) || fuenteParsed.length === 0) {
        toast.error(tForm("fuenteLegalParseError"));
        return;
      }
    } catch {
      toast.error(tForm("fuenteLegalParseError"));
      return;
    }
    createMutation.mutate({
      domain,
      key,
      vigencia_desde: vigenciaDesde,
      vigencia_hasta: vigenciaHasta || undefined,
      rules: rulesParsed,
      fuente_legal: fuenteParsed,
    });
  };

  return (
    <main className="container max-w-4xl space-y-6 py-12">
      <Link
        href="/admin/rules"
        className="text-sm text-muted-foreground hover:underline"
      >
        {t("back")}
      </Link>
      <Card>
        <CardHeader>
          <CardTitle>{tForm("title")}</CardTitle>
          <p className="text-sm text-muted-foreground">
            {tForm("subtitle")}
          </p>
        </CardHeader>
        <CardContent>
          <form onSubmit={onSubmit} className="space-y-5">
            <div className="grid gap-5 md:grid-cols-2">
              <div className="space-y-2">
                <Label>{tForm("domain")}</Label>
                <select
                  value={domain}
                  onChange={(e) => setDomain(e.target.value)}
                  className="flex h-10 w-full rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                >
                  {domainsKnown.map((d) => (
                    <option key={d} value={d}>
                      {d}
                    </option>
                  ))}
                </select>
                <p className="text-xs text-muted-foreground">
                  {tForm("domainHint")}
                </p>
              </div>
              <div className="space-y-2">
                <Label>{tForm("key")}</Label>
                <Input
                  value={key}
                  onChange={(e) => setKey(e.target.value)}
                  placeholder="14_d_3"
                  required
                />
                <p className="text-xs text-muted-foreground">
                  {tForm("keyHint")}
                </p>
              </div>
              <div className="space-y-2">
                <Label>{tForm("vigenciaDesde")}</Label>
                <Input
                  type="date"
                  value={vigenciaDesde}
                  onChange={(e) => setVigenciaDesde(e.target.value)}
                  required
                />
              </div>
              <div className="space-y-2">
                <Label>{tForm("vigenciaHasta")}</Label>
                <Input
                  type="date"
                  value={vigenciaHasta}
                  onChange={(e) => setVigenciaHasta(e.target.value)}
                />
              </div>
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label>{tForm("rules")}</Label>
                <div className="flex items-center gap-2">
                  {validation && (
                    <span
                      className={`rounded px-2 py-0.5 text-xs ${
                        validation.valid
                          ? "bg-green-100 text-green-900"
                          : "bg-destructive/10 text-destructive"
                      }`}
                    >
                      {validation.valid
                        ? tForm("validBadge")
                        : tForm("invalidBadge")}
                    </span>
                  )}
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    onClick={onValidate}
                    disabled={validateMutation.isPending}
                  >
                    {validateMutation.isPending
                      ? tForm("validating")
                      : tForm("validate")}
                  </Button>
                </div>
              </div>
              <textarea
                value={rulesText}
                onChange={(e) => setRulesText(e.target.value)}
                onBlur={onValidate}
                rows={14}
                className="w-full rounded-md border border-input bg-background p-3 font-mono text-xs focus:outline-none focus:ring-2 focus:ring-ring"
                spellCheck={false}
              />
              <p className="text-xs text-muted-foreground">
                {tForm("rulesHint")}
              </p>
              {validation && !validation.valid && (
                <div className="rounded border border-destructive/40 bg-destructive/5 p-3 text-xs text-destructive">
                  <p className="mb-2 font-semibold">
                    {tForm("errorsHeader")}
                  </p>
                  <ul className="space-y-1">
                    {validation.errors.map((err, idx) => (
                      <li key={idx} className="font-mono">
                        <span className="font-semibold">{err.path}</span>:{" "}
                        {err.message}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>

            <div className="space-y-2">
              <Label>{tForm("fuenteLegal")}</Label>
              <textarea
                value={fuenteText}
                onChange={(e) => setFuenteText(e.target.value)}
                rows={6}
                className="w-full rounded-md border border-input bg-background p-3 font-mono text-xs focus:outline-none focus:ring-2 focus:ring-ring"
                spellCheck={false}
              />
              <p className="text-xs text-muted-foreground">
                {tForm("fuenteLegalHint")}
              </p>
            </div>

            <Button
              type="submit"
              disabled={
                createMutation.isPending || !validation?.valid || !key
              }
            >
              {createMutation.isPending
                ? tForm("submitting")
                : tForm("submit")}
            </Button>
          </form>
        </CardContent>
      </Card>
    </main>
  );
}
