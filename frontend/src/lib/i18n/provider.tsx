"use client";

import { createInstance } from "i18next";
import { I18nextProvider } from "react-i18next";
import { useEffect, useState, type ReactNode } from "react";
import fr from "./locales/fr.json";
import en from "./locales/en.json";

export const LANGUAGE_STORAGE_KEY = "fullstack-language-v1";
export const supportedLanguages = ["fr", "en"] as const;
export type Language = (typeof supportedLanguages)[number];
export function isLanguage(value: unknown): value is Language {
  return value === "fr" || value === "en";
}

/** Une instance par arbre React : aucune langue mutable partagée entre rendus serveur. */
export function LanguageProvider({ children }: { children: ReactNode }) {
  const [instance] = useState(() => {
    const i18n = createInstance();
    void i18n.init({
      resources: { fr: { translation: fr }, en: { translation: en } },
      lng: "fr",
      fallbackLng: "fr",
      supportedLngs: [...supportedLanguages],
      initAsync: false,
      keySeparator: false,
      nsSeparator: false,
      interpolation: { escapeValue: false },
      react: { useSuspense: false },
    });
    return i18n;
  });

  useEffect(() => {
    const syncDocument = () => {
      const language = instance.resolvedLanguage || "fr";
      document.documentElement.lang = language;
    };
    const syncStorage = (event: StorageEvent) => {
      if (event.key === LANGUAGE_STORAGE_KEY)
        void instance.changeLanguage(
          isLanguage(event.newValue) ? event.newValue : "fr",
        );
    };
    try {
      const saved = localStorage.getItem(LANGUAGE_STORAGE_KEY);
      if (isLanguage(saved)) void instance.changeLanguage(saved);
    } catch {
      /* Le changement de langue reste disponible sans stockage navigateur. */
    }
    syncDocument();
    instance.on("languageChanged", syncDocument);
    window.addEventListener("storage", syncStorage);
    return () => {
      instance.off("languageChanged", syncDocument);
      window.removeEventListener("storage", syncStorage);
    };
  }, [instance]);

  return <I18nextProvider i18n={instance}>{children}</I18nextProvider>;
}

/** Préférence d’interface uniquement : ne pas y stocker de données de session. */
export function persistLanguage(language: Language) {
  try {
    localStorage.setItem(LANGUAGE_STORAGE_KEY, language);
  } catch {
    /* Stockage désactivé : conserver la préférence pour cet onglet. */
  }
}
