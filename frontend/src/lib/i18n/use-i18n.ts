"use client";

import { useCallback, useContext, useMemo, useSyncExternalStore } from "react";
import { I18nContext } from "react-i18next";

/**
 * Garder le snapshot français pendant l’hydratation de chaque composant.
 * Une préférence restaurée tôt ne doit pas modifier le texte d’un segment encore côté serveur.
 */
export function useI18n() {
  const context = useContext(I18nContext);
  if (!context?.i18n) throw new Error("useI18n requires LanguageProvider");
  const i18n = context.i18n;
  const subscribe = useCallback(
    (notify: () => void) => {
      i18n.on("languageChanged", notify);
      return () => {
        i18n.off("languageChanged", notify);
      };
    },
    [i18n],
  );
  const snapshot = useCallback(
    () => i18n.resolvedLanguage || "fr",
    [i18n],
  );
  const language = useSyncExternalStore(subscribe, snapshot, () => "fr");
  const t = useMemo(() => i18n.getFixedT(language), [i18n, language]);
  return { t, i18n, language };
}
