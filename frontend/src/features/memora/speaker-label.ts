/** Display an honest fallback without assigning unrelated voices to one person. */
export function speakerLabel(
  value: string | null | undefined,
  english = false,
) {
  const label = (value || "").trim();
  const normalized = label
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/\s+/g, " ");
  if (
    [
      "",
      "intervenant non identifie",
      "unidentified speaker",
      "unknown speaker",
      "unknown",
      "voix a verifier",
      "voice to verify",
    ].includes(normalized)
  )
    return english ? "Speaker" : "Intervenant";
  const numbered = /^Intervenant (\d+)$/.exec(label);
  return english && numbered ? `Speaker ${numbered[1]}` : label;
}
