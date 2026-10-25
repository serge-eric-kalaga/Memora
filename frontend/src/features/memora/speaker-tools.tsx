"use client";
import { useConfirmation } from "@/components/ui/confirmation";
import { useRef, useState } from "react";
import type { Segment } from "./api";
import { speakerLabel } from "./speaker-label";
import s from "./transcript-tools.module.css";

export function SpeakerTools({
  segments,
  version,
  guest,
  english,
  busy,
  canSeparate,
  separationFailed = false,
  run,
}: {
  segments: Segment[];
  version: number;
  guest: boolean;
  english: boolean;
  busy: boolean;
  canSeparate: boolean;
  separationFailed?: boolean;
  run: (path: string, method: string, body: unknown) => Promise<boolean>;
}) {
  const { confirm: confirmAction, confirmation } = useConfirmation();
  const names = [...new Set(segments.map((segment) => segment.speaker || ""))];
  const [from, setFrom] = useState(names[0] || "");
  const [to, setTo] = useState("");
  const [name, setName] = useState("");
  const [confirm, setConfirm] = useState(false);
  const [count, setCount] = useState("");
  const [message, setMessage] = useState("");
  const panel = useRef<HTMLDetailsElement>(null);
  const countInput = useRef<HTMLInputElement>(null);
  const unidentified =
    !from.trim() || /non identifi|unknown|unidentified/i.test(from);
  return (
    <>
      {confirmation}
      {separationFailed && canSeparate && (
        <div className={s.recovery} role="status">
          <strong>
            {english
              ? "Speakers could not be distinguished automatically"
              : "Les intervenants n’ont pas pu être distingués automatiquement"}
          </strong>
          <p>
            {english
              ? "This does not mean only one person spoke. Enter the known speaker count to retry; your transcript is preserved."
              : "Cela ne signifie pas qu’une seule personne a parlé. Indiquez le nombre d’intervenants connu pour réessayer ; votre transcription est conservée."}
          </p>
          <button
            type="button"
            className={s.button}
            onClick={() => {
              if (panel.current) panel.current.open = true;
              countInput.current?.focus();
              countInput.current?.scrollIntoView({
                block: "center",
                behavior: "smooth",
              });
            }}
          >
            {english ? "Distinguish speakers" : "Distinguer les intervenants"}
          </button>
        </div>
      )}
      <details className={s.speakers} ref={panel}>
        <summary className={s.summary}>
          {english ? "Manage speakers" : "Gérer les intervenants"}
        </summary>
        <div className={s.section}>
          <h3 className={s.title}>
            {english ? "Rename a speaker" : "Renommer un intervenant"}
          </h3>
          <p className={s.help}>
            {english
              ? "A rename affects every passage bearing this label and creates a new transcript version. It does not identify a voice."
              : "Le renommage concerne tous les passages portant cette étiquette et crée une nouvelle version. Il n’identifie pas une voix."}
          </p>
          {guest && (
            <label className={s.field}>
              {english ? "Your name" : "Votre nom"}
              <input
                className={s.input}
                required
                minLength={2}
                maxLength={100}
                value={name}
                onChange={(event) => setName(event.target.value)}
              />
            </label>
          )}
          <form
            onSubmit={async (event) => {
              event.preventDefault();
              setMessage("");
              if (
                await run("/speakers/rename", "POST", {
                  version,
                  from_speaker: from,
                  to_speaker: to,
                  confirm_unidentified: confirm,
                  ...(guest ? { editor_name: name } : {}),
                })
              )
                setMessage(
                  english
                    ? "Speaker renamed. The report needs regeneration."
                    : "Intervenant renommé. Le rapport est à actualiser.",
                );
            }}
          >
            <div className={s.renameGrid}>
              <label className={s.field}>
                {english ? "Existing label" : "Étiquette actuelle"}
                <select
                  className={s.select}
                  aria-label={english ? "Existing label" : "Étiquette actuelle"}
                  value={from}
                  onChange={(event) => {
                    setFrom(event.target.value);
                    setConfirm(false);
                  }}
                >
                  {names.map((value) => (
                    <option key={value} value={value}>
                      {speakerLabel(value, english)}
                    </option>
                  ))}
                </select>
              </label>
              <label className={s.field}>
                {english ? "New name" : "Nouveau nom"}
                <input
                  className={s.input}
                  required
                  maxLength={100}
                  value={to}
                  onChange={(event) => setTo(event.target.value)}
                />
              </label>
            </div>
            {unidentified && (
              <label className={s.confirm}>
                <input
                  type="checkbox"
                  checked={confirm}
                  onChange={(event) => setConfirm(event.target.checked)}
                />{" "}
                {english
                  ? "I checked that ALL passages with this unidentified label belong to the same person."
                  : "J’ai vérifié que TOUS les passages portant cette étiquette inconnue appartiennent à la même personne."}
              </label>
            )}
            <div className={s.submit}>
              <button
                className={s.button}
                disabled={
                  busy ||
                  !to.trim() ||
                  (unidentified && !confirm) ||
                  (guest && name.trim().length < 2)
                }
              >
                {english
                  ? "Rename all these passages"
                  : "Renommer tous ces passages"}
              </button>
            </div>
          </form>
        </div>
        {canSeparate && (
          <div className={s.section}>
            <h3 className={s.title}>
              {english
                ? "Local speaker separation"
                : "Séparation locale des voix"}
            </h3>
            <p className={s.help}>
              {english
                ? "Groups similar voices into numbered speakers. Short passages, similar voices and overlapping speech may be mislabelled. Review labels before assigning names. The text is preserved; the report becomes out of date."
                : "Regroupe les voix similaires sous des intervenants numérotés. Les passages courts, les voix proches et les paroles simultanées peuvent être mal attribués. Vérifiez avant de nommer les personnes. Le texte est conservé ; le rapport devient à actualiser."}
            </p>
            <div className={s.separationRow}>
              <label className={s.field}>
                {english
                  ? "Known speaker count (optional)"
                  : "Nombre d’intervenants connu (facultatif)"}
                <input
                  className={s.input}
                  type="number"
                  ref={countInput}
                  min={1}
                  max={8}
                  placeholder={
                    english ? "Automatic estimate" : "Estimation automatique"
                  }
                  value={count}
                  onChange={(event) => setCount(event.target.value)}
                />
              </label>
              <button
                className={s.button}
                disabled={
                  busy ||
                  (guest && name.trim().length < 2) ||
                  (!!count &&
                    (!Number.isInteger(Number(count)) ||
                      Number(count) < 1 ||
                      Number(count) > 8))
                }
                onClick={async () => {
                  if (
                    !(await confirmAction({
                      title: english
                        ? "Separate speakers"
                        : "Séparer les intervenants",
                      confirmLabel: english
                        ? "Start separation"
                        : "Lancer la séparation",
                      message: english
                        ? "Replace current speaker labels with a local estimate? Previous labels remain in history. Review the result before regenerating the report."
                        : "Remplacer les étiquettes actuelles par une estimation locale ? Les anciennes restent dans l’historique. Vérifiez le résultat avant de régénérer le rapport.",
                    }))
                  )
                    return;
                  if (
                    await run("/diarize", "POST", {
                      version,
                      request_id: crypto.randomUUID(),
                      ...(count ? { num_speakers: Number(count) } : {}),
                      ...(guest ? { editor_name: name } : {}),
                    })
                  )
                    setMessage(
                      english
                        ? "Separation queued. You can leave this page open to follow progress."
                        : "Séparation en attente. Cette page affichera le résultat du traitement.",
                    );
                }}
              >
                {english
                  ? "Separate speakers locally"
                  : "Séparer les intervenants localement"}
              </button>
            </div>
          </div>
        )}
        {message && (
          <p className={s.status} role="status">
            {message}
          </p>
        )}
      </details>
    </>
  );
}
