"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import * as React from "react";

import { Toaster } from "@/components/ui/sonner";

export function Providers({ children }: { children: React.ReactNode }) {
  // Crear el QueryClient en useState para que sea estable entre renders
  // y exclusivo del browser (evita compartir cache entre requests SSR).
  const [queryClient] = React.useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30 * 1000,
            refetchOnWindowFocus: false,
            retry: 1,
          },
          mutations: {
            retry: 0,
          },
        },
      }),
  );

  return (
    <QueryClientProvider client={queryClient}>
      {children}
      <Toaster position="top-right" richColors closeButton />
    </QueryClientProvider>
  );
}
