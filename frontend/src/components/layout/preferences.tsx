"use client";

import { useSyncExternalStore } from "react";
import { useI18n } from "@/lib/i18n/use-i18n";
import { useTheme } from "next-themes";
import { Globe2, Palette } from "lucide-react";
import { isLanguage, persistLanguage } from "@/lib/i18n/provider";

const subscribe = () => () => {};
/** Éviter d’afficher une valeur de thème différente entre le serveur et l’hydratation. */
export function Preferences() {
  const { t, i18n, language } = useI18n();
  const { theme, setTheme } = useTheme();
  const mounted = useSyncExternalStore(
    subscribe,
    () => true,
    () => false,
  );
  return (
    <div
      className="preferences"
      role="group"
      aria-label={t("Préférences d’affichage")}
    >
      <label className="preference-control">
        <Globe2 size={16} aria-hidden="true" />
        <span className="sr-only">{t("Langue")}</span>
        <select
          aria-label={t("Langue")}
          value={language}
          onChange={(event) => {
            const language = event.target.value;
            if (isLanguage(language)) {
              persistLanguage(language);
              void i18n.changeLanguage(language);
            }
          }}
        >
          <option value="fr" lang="fr">
            Français
          </option>
          <option value="en" lang="en">
            English
          </option>
        </select>
      </label>
      <label className="preference-control">
        <Palette size={16} aria-hidden="true" />
        <span className="sr-only">{t("Thème")}</span>
        <select
          aria-label={t("Thème")}
          value={mounted ? theme || "system" : "system"}
          disabled={!mounted}
          onChange={(event) => setTheme(event.target.value)}
        >
          <option value="light">{t("Clair")}</option>
          <option value="dark">{t("Sombre")}</option>
          <option value="system">{t("Système")}</option>
        </select>
      </label>
    </div>
  );
}
