"use client";

import { zodResolver } from "@hookform/resolvers/zod";
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
import { Checkbox } from "@/components/ui/checkbox";
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
import { mapAuthError } from "@/lib/auth-errors";
import { createClient } from "@/lib/supabase/client";

const schema = z.object({
  email: z.string().email("Correo inválido"),
  password: z.string().min(8, "Mínimo 8 caracteres."),
  consent: z.literal(true, {
    errorMap: () => ({ message: "Debes aceptar para continuar." }),
  }),
});

type FormValues = z.infer<typeof schema>;

export default function SignupPage() {
  const t = useTranslations("auth.signup");
  const router = useRouter();

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    // consent: defaultValue=false; el resolver convierte true literal cuando
    // el user lo marca.
    defaultValues: {
      email: "",
      password: "",
      consent: false as unknown as true,
    },
  });

  async function onSubmit(values: FormValues) {
    const supabase = createClient();
    const { error } = await supabase.auth.signUp({
      email: values.email,
      password: values.password,
    });
    if (error) {
      toast.error(mapAuthError(error));
      return;
    }
    router.push(`/signup/verify?email=${encodeURIComponent(values.email)}`);
    router.refresh();
  }

  return (
    <main className="container flex min-h-screen items-center justify-center py-16">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>{t("title")}</CardTitle>
          <CardDescription>{t("subtitle")}</CardDescription>
        </CardHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)}>
            <CardContent className="space-y-5">
              <FormField
                control={form.control}
                name="email"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t("email")}</FormLabel>
                    <FormControl>
                      <Input
                        type="email"
                        autoComplete="email"
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="password"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t("password")}</FormLabel>
                    <FormControl>
                      <Input
                        type="password"
                        autoComplete="new-password"
                        {...field}
                      />
                    </FormControl>
                    <FormDescription>{t("passwordHint")}</FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="consent"
                render={({ field }) => (
                  <FormItem>
                    <div className="flex items-start gap-3">
                      <FormControl>
                        <Checkbox
                          checked={!!field.value}
                          onChange={(e) =>
                            field.onChange(e.currentTarget.checked)
                          }
                          onBlur={field.onBlur}
                          name={field.name}
                          ref={field.ref}
                        />
                      </FormControl>
                      <span className="text-sm leading-snug text-muted-foreground">
                        {t.rich("consentLabel", {
                          politica: (chunks) => (
                            <Link
                              href="/legal/privacidad"
                              className="underline hover:text-foreground"
                            >
                              {chunks}
                            </Link>
                          ),
                          terminos: (chunks) => (
                            <Link
                              href="/legal/terminos"
                              className="underline hover:text-foreground"
                            >
                              {chunks}
                            </Link>
                          ),
                        })}
                      </span>
                    </div>
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
              <Link
                href="/login"
                className="text-sm text-muted-foreground hover:text-foreground"
              >
                {t("haveAccount")}
              </Link>
            </CardFooter>
          </form>
        </Form>
      </Card>
    </main>
  );
}
