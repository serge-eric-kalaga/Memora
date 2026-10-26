/** Text edits do not repair an earlier failed acoustic separation. */
export function hasUnresolvedSpeakerFailure(meeting: {
  version: number;
  automatic_diarization?: { state?: string; source_version?: number };
  diarization?: object | null;
  segments: { speaker?: string | null }[];
}) {
  const failure = meeting.automatic_diarization;
  return (
    failure?.state === "failed" &&
    typeof failure.source_version === "number" &&
    failure.source_version <= meeting.version &&
    !meeting.diarization &&
    meeting.segments.some(
      (segment) => speakerLabel(segment.speaker) === "Intervenant",
    )
  );
}

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
