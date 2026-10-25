"use client";
import {
  QueryClient,
  QueryClientProvider,
  useQueryClient,
} from "@tanstack/react-query";
import { useEffect, useState, type ReactNode } from "react";
import { ThemeProvider } from "next-themes";
import { LanguageProvider } from "@/lib/i18n/provider";
import {
  sessionChannel,
  sessionKey,
  sessionSource,
} from "@/features/auth/hooks";

function SessionEvents() {
  const client = useQueryClient();
  useEffect(() => {
    const expired = () => {
      void client.cancelQueries().then(() => {
        client.removeQueries({
          predicate: (query) => query.queryKey[0] !== "session",
        });
        client.setQueryData(sessionKey, null);
      });
    };
    const refresh = (event: MessageEvent) => {
      if (event.data?.source === sessionSource) return;
      if (event.data?.kind === "profile") {
        void client.invalidateQueries({ queryKey: sessionKey, exact: true });
        return;
      }
      void client.cancelQueries().then(() => {
        client.removeQueries({
          predicate: (query) => query.queryKey[0] !== "session",
        });
        void client.invalidateQueries({ queryKey: sessionKey });
      });
    };
    const channel =
      typeof BroadcastChannel !== "undefined"
        ? new BroadcastChannel(sessionChannel)
        : null;
    channel?.addEventListener("message", refresh);
    window.addEventListener("session-expired", expired);
    return () => {
      channel?.close();
      window.removeEventListener("session-expired", expired);
    };
  }, [client]);
  return null;
}
export function Providers({ children }: { children: ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: { retry: false, refetchOnWindowFocus: true },
          mutations: { retry: false },
        },
      }),
  );
  return (
    <ThemeProvider
      attribute="data-theme"
      defaultTheme="system"
      enableSystem
      storageKey="fullstack-theme-v1"
      disableTransitionOnChange
    >
      <LanguageProvider>
        <QueryClientProvider client={client}>
          <SessionEvents />
          {children}
        </QueryClientProvider>
      </LanguageProvider>
    </ThemeProvider>
  );
}
