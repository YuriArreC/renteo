"use client";

import { zodResolver } from "@hookform/resolvers/zod";
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
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { toast } from "@/components/ui/sonner";
import { ApiError, type WorkspaceType } from "@/lib/api";
import { useCreateWorkspace } from "@/lib/hooks/useCreateWorkspace";

const schema = z.object({
  name: z.string().trim().min(1, "Ingresa un nombre").max(120),
  type: z.enum(["pyme", "accounting_firm"]),
});

type FormValues = z.infer<typeof schema>;

export default function OnboardingWorkspacePage() {
  const t = useTranslations("onboarding.workspace");
  const router = useRouter();
  const createWorkspace = useCreateWorkspace();

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { name: "", type: "pyme" },
  });

  async function onSubmit(values: FormValues) {
    try {
      await createWorkspace.mutateAsync({
        name: values.name,
        type: values.type as WorkspaceType,
        consent_tratamiento_datos: true,
      });
      router.push("/dashboard");
      router.refresh();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.detail : String(err));
    }
  }

  const selectedType = form.watch("type");

  return (
    <main className="container flex min-h-screen items-center justify-center py-16">
      <Card className="w-full max-w-xl">
        <CardHeader>
          <CardTitle>{t("title")}</CardTitle>
          <CardDescription>{t("subtitle")}</CardDescription>
        </CardHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)}>
            <CardContent className="space-y-8">
              <FormField
                control={form.control}
                name="name"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t("nameLabel")}</FormLabel>
                    <FormControl>
                      <Input placeholder={t("namePlaceholder")} {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="type"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t("typeLabel")}</FormLabel>
                    <FormControl>
                      <RadioGroup
                        onValueChange={field.onChange}
                        value={field.value}
                        className="space-y-3"
                      >
                        <label
                          className={`flex cursor-pointer flex-col gap-1 rounded-lg border p-4 transition-colors ${
                            selectedType === "pyme"
                              ? "border-primary bg-accent"
                              : "border-border"
                          }`}
                        >
                          <span className="flex items-center gap-3">
                            <RadioGroupItem value="pyme" id="r-pyme" />
                            <span className="font-medium">
                              {t("typePyme")}
                            </span>
                          </span>
                          <span className="ml-7 text-sm text-muted-foreground">
                            {t("typePymeBody")}
                          </span>
                        </label>

                        <label
                          className={`flex cursor-pointer flex-col gap-1 rounded-lg border p-4 transition-colors ${
                            selectedType === "accounting_firm"
                              ? "border-primary bg-accent"
                              : "border-border"
                          }`}
                        >
                          <span className="flex items-center gap-3">
                            <RadioGroupItem
                              value="accounting_firm"
                              id="r-firm"
                            />
                            <span className="font-medium">
                              {t("typeAccountingFirm")}
                            </span>
                          </span>
                          <span className="ml-7 text-sm text-muted-foreground">
                            {t("typeAccountingFirmBody")}
                          </span>
                        </label>
                      </RadioGroup>
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </CardContent>
            <CardFooter>
              <Button
                type="submit"
                className="w-full"
                disabled={
                  form.formState.isSubmitting || createWorkspace.isPending
                }
              >
                {form.formState.isSubmitting || createWorkspace.isPending
                  ? t("submitting")
                  : t("submit")}
              </Button>
            </CardFooter>
          </form>
        </Form>
      </Card>
    </main>
  );
}
