/** Dates UTC de l’API, affichées dans le fuseau du navigateur et la langue choisie. */
export function formatConnection(value: string | null, language = "fr") {
  const english = language === "en";
  if (!value) return english ? "First sign-in" : "Première connexion";
  const date = new Date(value);
  if (Number.isNaN(date.getTime()))
    return english ? "Date unavailable" : "Date indisponible";
  return new Intl.DateTimeFormat(english ? "en-GB" : "fr-FR", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}
