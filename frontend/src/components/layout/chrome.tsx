"use client";
import { appName } from "@/lib/app-config";
import { usePathname } from "next/navigation";
import { useI18n } from "@/lib/i18n/use-i18n";

export function SkipLink() {
  const { t } = useI18n();
  return (
    <a className="skip-link" href="#page-content">
      {t("Aller au contenu")}
    </a>
  );
}
export function Footer() {
  const { t } = useI18n();
  return (
    <footer className="site-footer page-shell">
      <span>{appName}.</span>
      <p>{t("Vos échanges deviennent des idées claires.")}</p>
      <span className="footer-stack">RÉUNIONS · TRANSCRIPTION · IA LOCALE</span>
    </footer>
  );
}

/** Un seul titre React, localisé sans concurrence avec les métadonnées streamées. */
export function PageTitle() {
  const { t } = useI18n();
  const pathname = usePathname();
  const title =
    pathname === "/confirmer-email"
      ? t("Confirmer l’adresse e-mail")
      : pathname === "/mot-de-passe-oublie"
        ? t("Mot de passe oublié")
        : pathname === "/reinitialiser-mot-de-passe"
          ? t("Réinitialiser le mot de passe")
          : pathname === "/connexion"
            ? t("Se connecter")
            : pathname === "/inscription"
              ? t("Créer un compte")
              : pathname === "/profil"
                ? t("Mon profil")
                : null;
  return (
    <title>{title ? `${title} · ${appName}` : `${appName} · Réunions et mémoire`}</title>
  );
}
