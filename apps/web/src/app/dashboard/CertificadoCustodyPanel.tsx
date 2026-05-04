"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useState } from "react";

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
  type CertificateMetadataResponse,
  type CertificateUploadRequest,
  type EmpresaResponse,
  fetchApiClient,
} from "@/lib/api";

async function fileToBase64(file: File): Promise<string> {
  return await new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result;
      if (typeof result !== "string") {
        reject(new Error("FileReader devolvió un buffer, no un string"));
        return;
      }
      // result tiene el prefijo "data:application/x-pkcs12;base64,..."
      const idx = result.indexOf(",");
      resolve(idx >= 0 ? result.slice(idx + 1) : result);
    };
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}

function CertificadoRow({ empresa }: { empresa: EmpresaResponse }) {
  const t = useTranslations("dashboard.custody");
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [rut, setRut] = useState("");
  const [nombre, setNombre] = useState("");
  const [validoDesde, setValidoDesde] = useState("");
  const [validoHasta, setValidoHasta] = useState("");
  const [passphrase, setPassphrase] = useState("");

  const status = useQuery<CertificateMetadataResponse | null>({
    queryKey: ["cert-status", empresa.id],
    queryFn: async () => {
      try {
        return await fetchApiClient<CertificateMetadataResponse>(
          `/api/empresas/${empresa.id}/certificado`,
        );
      } catch (err) {
        if (err instanceof ApiError && err.status === 404) {
          return null;
        }
        throw err;
      }
    },
  });

  const upload = useMutation({
    mutationFn: (req: CertificateUploadRequest) =>
      fetchApiClient<CertificateMetadataResponse>(
        `/api/empresas/${empresa.id}/certificado`,
        {
          method: "POST",
          body: JSON.stringify(req),
        },
      ),
    onSuccess: () => {
      toast.success(t("uploadOk", { razon: empresa.razon_social }));
      setOpen(false);
      setFile(null);
      setRut("");
      setNombre("");
      setValidoDesde("");
      setValidoHasta("");
      setPassphrase("");
      queryClient.invalidateQueries({
        queryKey: ["cert-status", empresa.id],
      });
    },
    onError: (err) =>
      toast.error(err instanceof ApiError ? err.detail : String(err)),
  });

  const revoke = useMutation({
    mutationFn: () =>
      fetchApiClient(`/api/empresas/${empresa.id}/certificado`, {
        method: "DELETE",
      }),
    onSuccess: () => {
      toast.success(t("revokeOk"));
      queryClient.invalidateQueries({
        queryKey: ["cert-status", empresa.id],
      });
    },
    onError: (err) =>
      toast.error(err instanceof ApiError ? err.detail : String(err)),
  });

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) {
      toast.error(t("fileRequired"));
      return;
    }
    if (!rut || !validoDesde || !validoHasta) {
      toast.error(t("fieldsRequired"));
      return;
    }
    try {
      const pfx_base64 = await fileToBase64(file);
      const req: CertificateUploadRequest = {
        pfx_base64,
        rut_titular: rut,
        valido_desde: validoDesde,
        valido_hasta: validoHasta,
      };
      if (nombre) req.nombre_titular = nombre;
      if (passphrase) req.passphrase = passphrase;
      upload.mutate(req);
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : String(err),
      );
    }
  };

  return (
    <div className="space-y-3 border-b border-border py-3 last:border-0">
      <div className="flex items-center justify-between gap-3">
        <div className="text-xs">
          <p className="font-medium">
            {empresa.razon_social}{" "}
            <span className="ml-1 font-mono text-[10px] text-muted-foreground">
              {empresa.rut}
            </span>
          </p>
          {status.data ? (
            <p className="text-[10px] text-muted-foreground">
              {t("active", {
                rut: status.data.rut_titular,
                hasta: status.data.valido_hasta,
              })}
            </p>
          ) : (
            <p className="text-[10px] text-muted-foreground">
              {t("noActive")}
            </p>
          )}
        </div>
        <div className="flex gap-2">
          <Button size="sm" onClick={() => setOpen((v) => !v)}>
            {open ? t("close") : status.data ? t("replace") : t("upload")}
          </Button>
          {status.data && (
            <Button
              size="sm"
              variant="ghost"
              disabled={revoke.isPending}
              onClick={() => revoke.mutate()}
            >
              {revoke.isPending ? t("revoking") : t("revoke")}
            </Button>
          )}
        </div>
      </div>

      {open && (
        <form
          onSubmit={onSubmit}
          className="grid gap-3 rounded-md border border-border bg-muted/30 p-3 md:grid-cols-2"
        >
          <div className="space-y-1 md:col-span-2">
            <Label className="text-xs">{t("file")}</Label>
            <input
              type="file"
              accept=".pfx,.p12"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              className="block w-full text-xs"
            />
          </div>
          <div className="space-y-1">
            <Label className="text-xs">{t("rut")}</Label>
            <Input
              value={rut}
              onChange={(e) => setRut(e.target.value)}
              placeholder="12.345.678-5"
              required
            />
          </div>
          <div className="space-y-1">
            <Label className="text-xs">{t("nombre")}</Label>
            <Input
              value={nombre}
              onChange={(e) => setNombre(e.target.value)}
            />
          </div>
          <div className="space-y-1">
            <Label className="text-xs">{t("validoDesde")}</Label>
            <Input
              type="date"
              value={validoDesde}
              onChange={(e) => setValidoDesde(e.target.value)}
              required
            />
          </div>
          <div className="space-y-1">
            <Label className="text-xs">{t("validoHasta")}</Label>
            <Input
              type="date"
              value={validoHasta}
              onChange={(e) => setValidoHasta(e.target.value)}
              required
            />
          </div>
          <div className="space-y-1 md:col-span-2">
            <Label className="text-xs">{t("passphrase")}</Label>
            <Input
              type="password"
              value={passphrase}
              onChange={(e) => setPassphrase(e.target.value)}
              placeholder={t("passphraseHint")}
            />
          </div>
          <div className="md:col-span-2">
            <Button type="submit" disabled={upload.isPending}>
              {upload.isPending ? t("uploading") : t("submit")}
            </Button>
          </div>
        </form>
      )}
    </div>
  );
}

export function CertificadoCustodyPanel({
  empresas,
}: {
  empresas: EmpresaResponse[];
}) {
  const t = useTranslations("dashboard.custody");
  if (empresas.length === 0) return null;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{t("header")}</CardTitle>
        <p className="text-xs text-muted-foreground">{t("subtitle")}</p>
      </CardHeader>
      <CardContent className="space-y-1">
        {empresas.map((e) => (
          <CertificadoRow key={e.id} empresa={e} />
        ))}
      </CardContent>
    </Card>
  );
}
