"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { toast } from "@/components/ui/sonner";
import {
  ApiError,
  type ArcopEstado,
  type ArcopListResponse,
  type ArcopResponse,
  type ArcopTipo,
  type CreateArcopRequest,
  fetchApiClient,
  type UpdateArcopRequest,
} from "@/lib/api";

const ESTADOS = [
  "recibida",
  "en_proceso",
  "cumplida",
  "rechazada",
] as const;

const TERMINAL_ESTADOS: ReadonlySet<ArcopEstado> = new Set([
  "cumplida",
  "rechazada",
]);

const TIPOS = [
  "acceso",
  "rectificacion",
  "cancelacion",
  "oposicion",
  "portabilidad",
] as const;

const schema = z.object({
  tipo: z.enum(TIPOS),
  descripcion: z.string().trim().max(2000),
});

type FormValues = z.infer<typeof schema>;

function formatDate(iso: string): string {
  return new Intl.DateTimeFormat("es-CL", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(new Date(iso));
}

export function ArcopPortal({ isAdmin = false }: { isAdmin?: boolean }) {
  return (
    <Suspense fallback={null}>
      <ArcopPortalInner isAdmin={isAdmin} />
    </Suspense>
  );
}

function ArcopPortalInner({ isAdmin }: { isAdmin: boolean }) {
  const tForm = useTranslations("privacy.form");
  const tList = useTranslations("privacy.list");
  const tEstado = useTranslations("privacy.estadoLabel");
  const tTipo = useTranslations("privacy.tipoShort");

  const queryClient = useQueryClient();
  const searchParams = useSearchParams();
  const presetTipo = searchParams.get("tipo");
  const presetDescripcion = searchParams.get("descripcion");

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { tipo: "acceso", descripcion: "" },
  });

  useEffect(() => {
    if (
      presetTipo &&
      (TIPOS as readonly string[]).includes(presetTipo)
    ) {
      form.setValue("tipo", presetTipo as FormValues["tipo"]);
    }
    if (presetDescripcion) {
      form.setValue("descripcion", presetDescripcion);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [presetTipo, presetDescripcion]);

  const listQuery = useQuery<ArcopListResponse>({
    queryKey: ["arcop-list"],
    queryFn: () =>
      fetchApiClient<ArcopListResponse>("/api/privacy/arcop"),
  });

  const mutation = useMutation({
    mutationFn: (req: CreateArcopRequest) =>
      fetchApiClient<ArcopResponse>("/api/privacy/arcop", {
        method: "POST",
        body: JSON.stringify(req),
      }),
    onSuccess: (data) => {
      toast.success(tForm("saved", { tipo: tTipo(data.tipo) }));
      form.reset({ tipo: "acceso", descripcion: "" });
      queryClient.invalidateQueries({ queryKey: ["arcop-list"] });
    },
    onError: (err) =>
      toast.error(err instanceof ApiError ? err.detail : String(err)),
  });

  const onSubmit = (v: FormValues) => {
    mutation.mutate({
      tipo: v.tipo,
      descripcion: v.descripcion || undefined,
    });
  };

  const items = listQuery.data?.solicitudes ?? [];

  return (
    <div className="space-y-8">
      <Card>
        <CardHeader>
          <CardTitle>{tForm("header")}</CardTitle>
        </CardHeader>
        <CardContent>
          <Form {...form}>
            <form
              onSubmit={form.handleSubmit(onSubmit)}
              className="space-y-5"
            >
              <FormField
                control={form.control}
                name="tipo"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{tForm("tipo")}</FormLabel>
                    <FormControl>
                      <select
                        {...field}
                        className="flex h-10 w-full rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                      >
                        {TIPOS.map((t) => (
                          <option key={t} value={t}>
                            {tForm(`tipoOptions.${t}`)}
                          </option>
                        ))}
                      </select>
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="descripcion"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{tForm("descripcion")}</FormLabel>
                    <FormControl>
                      <Input
                        placeholder={tForm("descripcionPlaceholder")}
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <Button type="submit" disabled={mutation.isPending}>
                {mutation.isPending ? tForm("submitting") : tForm("submit")}
              </Button>
            </form>
          </Form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">
            {isAdmin ? tList("headerAdmin") : tList("header")}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {items.length === 0 ? (
            <p className="text-xs text-muted-foreground">
              {tList("empty")}
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border bg-muted/40 text-left">
                    <th className="p-3 font-medium">{tList("tipo")}</th>
                    <th className="p-3 font-medium">{tList("estado")}</th>
                    <th className="p-3 font-medium">{tList("recibida")}</th>
                    <th className="p-3 font-medium">{tList("respuesta")}</th>
                    {isAdmin && (
                      <th className="p-3 font-medium">{tList("acciones")}</th>
                    )}
                  </tr>
                </thead>
                <tbody>
                  {items.map((s) => (
                    <tr key={s.id} className="border-b border-border">
                      <td className="p-3 font-medium">
                        {tTipo(s.tipo as ArcopTipo)}
                      </td>
                      <td className="p-3 text-xs">
                        <EstadoBadge
                          estado={s.estado}
                          label={tEstado(s.estado)}
                        />
                      </td>
                      <td className="p-3 text-xs text-muted-foreground">
                        {formatDate(s.recibida_at)}
                      </td>
                      <td className="p-3 text-xs text-muted-foreground">
                        {s.respuesta ?? "—"}
                      </td>
                      {isAdmin && (
                        <td className="p-3 align-top">
                          <DpoActions arcop={s} />
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function DpoActions({ arcop }: { arcop: ArcopResponse }) {
  const tList = useTranslations("privacy.list");
  const queryClient = useQueryClient();
  const isTerminal = TERMINAL_ESTADOS.has(arcop.estado);

  const subSchema = z.object({
    estado: z.enum(ESTADOS),
    respuesta: z.string().trim().max(4000),
  });
  type SubValues = z.infer<typeof subSchema>;

  const subForm = useForm<SubValues>({
    resolver: zodResolver(subSchema),
    defaultValues: {
      estado: arcop.estado,
      respuesta: arcop.respuesta ?? "",
    },
  });

  const mutation = useMutation({
    mutationFn: (req: UpdateArcopRequest) =>
      fetchApiClient<ArcopResponse>(`/api/privacy/arcop/${arcop.id}`, {
        method: "PATCH",
        body: JSON.stringify(req),
      }),
    onSuccess: () => {
      toast.success(tList("savedToast"));
      queryClient.invalidateQueries({ queryKey: ["arcop-list"] });
    },
    onError: (err) =>
      toast.error(err instanceof ApiError ? err.detail : String(err)),
  });

  if (isTerminal) {
    return (
      <span className="text-xs text-muted-foreground">
        {tList("terminalNote")}
      </span>
    );
  }

  return (
    <Form {...subForm}>
      <form
        onSubmit={subForm.handleSubmit((v) => mutation.mutate(v))}
        className="flex flex-col gap-2"
      >
        <select
          {...subForm.register("estado")}
          className="h-8 rounded-md border border-input bg-background px-2 text-xs"
        >
          {ESTADOS.map((e) => (
            <option key={e} value={e}>
              {e}
            </option>
          ))}
        </select>
        <Input
          {...subForm.register("respuesta")}
          placeholder={tList("responsePlaceholder")}
          className="h-8 text-xs"
        />
        <Button
          type="submit"
          size="sm"
          disabled={mutation.isPending}
          className="h-8 text-xs"
        >
          {mutation.isPending ? tList("saving") : tList("saveResponse")}
        </Button>
      </form>
    </Form>
  );
}

function EstadoBadge({
  estado,
  label,
}: {
  estado: ArcopResponse["estado"];
  label: string;
}) {
  const tone =
    estado === "cumplida"
      ? "bg-green-100 text-green-900"
      : estado === "rechazada"
        ? "bg-destructive/10 text-destructive"
        : estado === "en_proceso"
          ? "bg-yellow-100 text-yellow-900"
          : "bg-muted text-muted-foreground";
  return (
    <span className={`rounded px-2 py-0.5 ${tone}`}>{label}</span>
  );
}
