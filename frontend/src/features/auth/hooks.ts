"use client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { authApi } from "./api";
import type { CurrentUser } from "@/lib/api/types";
import { useI18n } from "@/lib/i18n/use-i18n";

export const sessionKey = ["session"] as const;
export const sessionChannel = "fullstack-session";
// Identifier l’onglet émetteur évite de retraiter sa propre mise à jour déjà appliquée.
export const sessionSource = Math.random().toString(36).slice(2);
function notifySessionChange(kind: "account" | "profile" = "account") {
  if (typeof BroadcastChannel !== "undefined") {
    const channel = new BroadcastChannel(sessionChannel);
    channel.postMessage({ source: sessionSource, kind });
    channel.close();
  }
}
export function useSession() {
  return useQuery({
    queryKey: sessionKey,
    queryFn: ({ signal }) => authApi.session(signal),
    staleTime: 30_000,
    retry: false,
  });
}

/** Purger les données privées lors d’un changement de compte et synchroniser les onglets. */
export function useAuthenticate(mode: "login" | "register") {
  const client = useQueryClient();
  const { language } = useI18n();
  return useMutation({
    gcTime: 0,
    mutationFn: (input: {
      username: string;
      password: string;
      telephone?: string;
      email?: string;
    }) =>
      mode === "login"
        ? authApi.login(input)
        : authApi.register(
            { ...input, telephone: input.telephone || "" },
            language,
          ),
    onSuccess: async (user: CurrentUser | null) => {
      await client.cancelQueries();
      client.removeQueries({
        predicate: (query) => query.queryKey[0] !== "session",
      });
      client.setQueryData(sessionKey, user);
      notifySessionChange();
    },
  });
}
export function useLogout() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: authApi.logout,
    onSuccess: async () => {
      await client.cancelQueries();
      client.removeQueries({
        predicate: (query) => query.queryKey[0] !== "session",
      });
      client.setQueryData(sessionKey, null);
      notifySessionChange();
    },
  });
}
export function useUpdateProfile() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: authApi.updateProfile,
    onSuccess: (user) => {
      client.setQueryData(sessionKey, user);
      notifySessionChange("profile");
    },
  });
}
export function useUploadPhoto() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: authApi.uploadPhoto,
    onSuccess: (user) => {
      client.setQueryData(sessionKey, user);
      notifySessionChange("profile");
    },
  });
}

/** Les mots de passe/jetons restent en mémoire pendant l’envoi ; aucune persistance de mutation. */
export function useCredentialChange<T>(
  mutationFn: (input: T) => Promise<null>,
  beforeSessionClear?: () => void,
) {
  const client = useQueryClient();
  return useMutation({
    mutationFn,
    gcTime: 0,
    onSuccess: async () => {
      await client.cancelQueries();
      client.removeQueries({
        predicate: (query) => query.queryKey[0] !== "session",
      });
      beforeSessionClear?.();
      client.setQueryData(sessionKey, null);
      notifySessionChange();
    },
  });
}
