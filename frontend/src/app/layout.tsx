import type { Metadata } from "next";
import { Suspense, type ReactNode } from "react";
import "./globals.css";
import { CaptureProvider } from "@/features/memora/capture-session";
import { Providers } from "@/components/providers";
import { Footer, SkipLink, PageTitle } from "@/components/layout/chrome";
import { WorkspaceFrame } from "@/features/memora/workspace-frame";
import { Navbar } from "@/components/layout/navbar";

export const metadata: Metadata = {
  description:
    "Memora, votre application de réunions, transcription et analyse IA locale.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html suppressHydrationWarning lang="fr" className="h-full antialiased">
      <body className="min-h-full">
        <Providers>
          <CaptureProvider>
            <Suspense fallback={<title>Memora</title>}>
              <PageTitle />
            </Suspense>
            <SkipLink />
            <Suspense fallback={<div />}>
              <WorkspaceFrame>
                <Suspense fallback={<header className="site-header" />}>
                  <Navbar />
                </Suspense>
                <div id="page-content" tabIndex={-1}>
                  {children}
                </div>
                <Footer />
              </WorkspaceFrame>
            </Suspense>
          </CaptureProvider>
        </Providers>
      </body>
    </html>
  );
}
