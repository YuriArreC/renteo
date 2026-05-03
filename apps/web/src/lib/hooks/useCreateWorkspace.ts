"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";

import {
  type CreateWorkspaceReq,
  type CreateWorkspaceResp,
  fetchApiClient,
} from "@/lib/api";
import { meQueryKey } from "@/lib/hooks/useMe";
import { createClient } from "@/lib/supabase/client";

export function useCreateWorkspace() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (payload: CreateWorkspaceReq) => {
      const response = await fetchApiClient<CreateWorkspaceResp>(
        "/api/workspaces",
        {
          method: "POST",
          body: JSON.stringify(payload),
        },
      );
      // Refrescar la sesión para que el Auth Hook re-ejecute con la
      // membership recién creada y el JWT lleve la tenancy.
      const supabase = createClient();
      await supabase.auth.refreshSession();
      return response;
    },
    onSuccess: () => {
      // /api/me y cualquier query dependiente quedan stale.
      void queryClient.invalidateQueries({ queryKey: meQueryKey });
    },
  });
}
