import type { Segment } from "./api";
/** The scope describes what the provider actually measured, not a per-segment inference. */
export function describeSegmentLanguage(
  segment: Segment,
  tr: (text: string) => string,
) {
  const language = segment.language || "";
  if (language === "unknown")
    return {
      label: tr("Langue non déterminée"),
      hint: tr(
        "Le moteur ne fournit pas de langue détectée ni de fiabilité chiffrée. Vérifiez les passages importants avec l’audio.",
      ),
    };
  const name =
    language === "fr"
      ? tr("français")
      : language === "en"
        ? tr("anglais")
        : language;
  if (segment.language_scope === "initial_window_detection")
    return {
      label: `${tr("Langue dominante :")} ${name}`,
      hint: tr(
        "Langue détectée au début de l’audio ; elle peut varier dans ce passage.",
      ),
    };
  if (segment.language_scope === "speech_region_detection")
    return {
      label: `${tr("Langue de la portion audio :")} ${name}`,
      hint: tr(
        "Langue estimée pour cette portion de parole. Les changements sans pause peuvent ne pas être détectés ; fiabilité non chiffrée.",
      ),
    };
  if (segment.language_scope === "forced")
    return {
      label: `${tr("Langue choisie :")} ${name}`,
      hint: tr(
        "Langue sélectionnée pour la transcription, sans détection propre à ce passage.",
      ),
    };
  return { label: language, hint: undefined };
}
