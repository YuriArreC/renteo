"use client";

import { useQuery } from "@tanstack/react-query";

import { fetchApiClient, type MeResponse } from "@/lib/api";

export const meQueryKey = ["me"] as const;

export function useMe() {
  return useQuery({
    queryKey: meQueryKey,
    queryFn: () => fetchApiClient<MeResponse>("/api/me"),
  });
}
