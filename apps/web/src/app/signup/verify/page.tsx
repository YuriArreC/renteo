"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useRouter, useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { Suspense, useState } from "react";
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
import { ApiError, fetchApiClient, type MeResponse } from "@/lib/api";
import { createClient } from "@/lib/supabase/client";

const schema = z.object({
  code: z
    .string()
    .min(6, "Código demasiado corto")
    .max(10, "Código demasiado largo")
    .regex(/^[0-9]+$/, "Solo números"),
});

type FormValues = z.infer<typeof schema>;

export default function SignupVerifyPage() {
  return (
    <Suspense fallback={null}>
      <SignupVerifyForm />
    </Suspense>
  );
}

function SignupVerifyForm() {
  const t = useTranslations("auth.verify");
  const router = useRouter();
  const searchParams = useSearchParams();
  const email = searchParams.get("email") ?? "";
  const [resending, setResending] = useState(false);

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { code: "" },
  });

  async function onSubmit(values: FormValues) {
    if (!email) {
      toast.error(t("missingEmail"));
      return;
    }
    const supabase = createClient();
    const { error } = await supabase.auth.verifyOtp({
      email,
      token: values.code,
      type: "email",
    });
    if (error) {
      toast.error(error.message);
      return;
    }

    try {
      const me = await fetchApiClient<MeResponse>("/api/me");
      router.push(me.workspace ? "/dashboard" : "/onboarding/workspace");
      router.refresh();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.detail : String(err));
    }
  }

  async function handleResend() {
    if (!email) {
      toast.error(t("missingEmail"));
      return;
    }
    setResending(true);
    const supabase = createClient();
    const { error } = await supabase.auth.resend({ type: "signup", email });
    setResending(false);
    if (error) toast.error(error.message);
    else toast.success(t("resent"));
  }

  return (
    <main className="container flex min-h-screen items-center justify-center py-16">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>{t("title")}</CardTitle>
          <CardDescription>
            {t("subtitle", { email: email || "—" })}
          </CardDescription>
        </CardHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)}>
            <CardContent>
              <FormField
                control={form.control}
                name="code"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t("codeLabel")}</FormLabel>
                    <FormControl>
                      <Input
                        inputMode="numeric"
                        autoComplete="one-time-code"
                        maxLength={10}
                        placeholder="••••••"
                        className="text-center font-mono text-lg tracking-widest"
                        {...field}
                        onChange={(e) =>
                          field.onChange(
                            e.currentTarget.value.replace(/\D/g, ""),
                          )
                        }
                      />
                    </FormControl>
                    <FormDescription>{t("codeHint")}</FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </CardContent>
            <CardFooter className="flex-col gap-4">
              <Button
                type="submit"
                className="w-full"
                disabled={form.formState.isSubmitting}
              >
                {form.formState.isSubmitting ? t("submitting") : t("submit")}
              </Button>
              <button
                type="button"
                onClick={handleResend}
                disabled={resending}
                className="text-sm text-muted-foreground hover:text-foreground disabled:opacity-50"
              >
                {resending ? t("resending") : t("resend")}
              </button>
            </CardFooter>
          </form>
        </Form>
      </Card>
    </main>
  );
}
