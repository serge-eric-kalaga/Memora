"use client";
import { useI18n } from "@/lib/i18n/use-i18n";
import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { useSession } from "./hooks";
export function HomeActions() {
  const { t } = useI18n();
  const session = useSession();
  return (
    <div className="hero-actions">
      <Link
        className="button button-primary button-large"
        href="/documentation"
      >
        {t("Consulter la documentation")}
        <ArrowRight size={18} />
      </Link>
      <Link
        className="button button-quiet"
        href={session.data ? "/profil" : "/connexion"}
      >
        {session.data
          ? t("Bonjour, {{username}}", { username: session.data.username })
          : t("Tester la connexion")}
      </Link>
    </div>
  );
}
