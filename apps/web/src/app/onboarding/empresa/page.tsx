"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { toast } from "@/components/ui/sonner";
import {
  ApiError,
  type CreateEmpresaRequest,
  type EmpresaResponse,
  fetchApiClient,
} from "@/lib/api";

const REGIMENS = [
  "desconocido",
  "14_a",
  "14_d_3",
  "14_d_8",
  "presunta",
] as const;

const schema = z.object({
  rut: z
    .string()
    .trim()
    .min(3)
    .regex(
      /^\d{1,8}-[0-9Kk]$|^\d{1,3}(\.\d{3}){0,2}-[0-9Kk]$/,
      "Formato esperado: 12345678-5",
    ),
  razon_social: z.string().trim().min(2).max(160),
  giro: z.string().trim().max(200),
  regimen_actual: z.enum(REGIMENS),
});

type FormValues = z.infer<typeof schema>;

export default function OnboardingEmpresaPage() {
  const t = useTranslations("onboarding.empresa");
  const router = useRouter();

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      rut: "",
      razon_social: "",
      giro: "",
      regimen_actual: "desconocido",
    },
  });

  const mutation = useMutation({
    mutationFn: (req: CreateEmpresaRequest) =>
      fetchApiClient<EmpresaResponse>("/api/empresas", {
        method: "POST",
        body: JSON.stringify(req),
      }),
    onSuccess: () => {
      router.push("/dashboard");
      router.refresh();
    },
    onError: (err) =>
      toast.error(err instanceof ApiError ? err.detail : String(err)),
  });

  const onSubmit = (v: FormValues) => {
    mutation.mutate({
      rut: v.rut,
      razon_social: v.razon_social,
      giro: v.giro || undefined,
      regimen_actual: v.regimen_actual,
    });
  };

  return (
    <main className="container flex min-h-screen items-center justify-center py-16">
      <Card className="w-full max-w-xl">
        <CardHeader>
          <CardTitle>{t("title")}</CardTitle>
          <CardDescription>{t("subtitle")}</CardDescription>
        </CardHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)}>
            <CardContent className="space-y-6">
              <FormField
                control={form.control}
                name="rut"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t("rut")}</FormLabel>
                    <FormControl>
                      <Input placeholder={t("rutPlaceholder")} {...field} />
                    </FormControl>
                    <FormDescription>{t("rutHint")}</FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="razon_social"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t("razonSocial")}</FormLabel>
                    <FormControl>
                      <Input
                        placeholder={t("razonSocialPlaceholder")}
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="giro"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t("giro")}</FormLabel>
                    <FormControl>
                      <Input
                        placeholder={t("giroPlaceholder")}
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="regimen_actual"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t("regimen")}</FormLabel>
                    <FormControl>
                      <select
                        {...field}
                        className="flex h-10 w-full rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                      >
                        {REGIMENS.map((r) => (
                          <option key={r} value={r}>
                            {t(`regimenOptions.${r}`)}
                          </option>
                        ))}
                      </select>
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </CardContent>
            <CardFooter className="flex items-center justify-between">
              <Link
                href="/dashboard"
                className="text-sm text-muted-foreground hover:underline"
              >
                {t("skip")}
              </Link>
              <Button
                type="submit"
                disabled={mutation.isPending}
              >
                {mutation.isPending ? t("submitting") : t("submit")}
              </Button>
            </CardFooter>
          </form>
        </Form>
      </Card>
    </main>
  );
}
