"use client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { adminApi } from "./api";
import { updateAdminCache } from "./cache";
import { useSession } from "@/features/auth/hooks";

/** Droits propres au compte ; les erreurs 403 ne sont pas des déconnexions. */
export function useMyAccess() {
  const session = useSession();
  return useQuery({
    queryKey: ["access", session.data?.username],
    queryFn: ({ signal }) => adminApi.me(signal),
    enabled: !!session.data,
    retry: false,
    staleTime: 15_000,
  });
}

/** Actualiser uniquement les objets et les droits affectés ; aucune mutation persistée. */
export function useAdminMutation() {
  const client = useQueryClient();
  const session = useSession();
  return useMutation({
    mutationFn: adminApi.execute,
    gcTime: 0,
    onSuccess: async (result, action) => {
      if (session.data)
        await updateAdminCache(client, session.data.username, action, result);
    },
  });
}
