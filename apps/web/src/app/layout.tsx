import type { Metadata } from "next";
import { NextIntlClientProvider } from "next-intl";
import { getMessages } from "next-intl/server";

import { Providers } from "@/components/Providers";

import "./globals.css";

export const metadata: Metadata = {
  title: "Renteo",
  description: "Optimización tributaria proactiva para Chile.",
};

export default async function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  const messages = await getMessages();

  return (
    <html lang="es-CL">
      <body className="min-h-screen bg-background font-sans antialiased">
        <NextIntlClientProvider messages={messages}>
          <Providers>{children}</Providers>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
