"use client";
import { useState } from "react";
import {
  api,
  type Access,
  type HumanReview,
  type Item,
  type Segment,
} from "./api";
import s from "./report-review.module.css";

export function ReportReview({
  meetingId,
  reportId,
  version,
  category,
  index,
  item,
  review,
  segments,
  editable,
  stale,
  access,
  english,
  refresh,
}: {
  meetingId: string;
  reportId: string;
  version: number;
  category: "actions" | "decisions";
  index: number;
  item: Item;
  review?: HumanReview;
  segments: Segment[];
  editable: boolean;
  stale: boolean;
  access: Access;
  english: boolean;
  refresh: () => Promise<void>;
}) {
  const [open, setOpen] = useState(false);
  const [status, setStatus] = useState<HumanReview["status"]>(
    review?.status || "proposed",
  );
  const [text, setText] = useState(review?.corrections.text ?? item.text);
  const [owner, setOwner] = useState(
    review?.corrections.owner ?? item.owner ?? "",
  );
  const [deadline, setDeadline] = useState(
    review?.corrections.deadline ?? item.deadline ?? "",
  );
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [history, setHistory] = useState<HumanReview[] | null>(null);
  const labels = english
    ? {
        proposed: "Proposed",
        confirmed: "Confirmed",
        cancelled: "Cancelled",
        needs_review: "Needs review",
      }
    : {
        proposed: "Proposé",
        confirmed: "Confirmé",
        cancelled: "Annulé",
        needs_review: "À vérifier",
      };
  async function save() {
    setBusy(true);
    setError("");
    try {
      await api(
        `meetings/${meetingId}/reports/${reportId}/reviews/${category}/${index}`,
        {
          method: "PUT",
          body: JSON.stringify({
            transcript_version: version,
            expected_revision: review?.revision || 0,
            status,
            corrections: {
              ...(text !== item.text ? { text } : {}),
              ...(category === "actions" && owner !== (item.owner ?? "")
                ? { owner }
                : {}),
              ...(category === "actions" && deadline !== (item.deadline ?? "")
                ? { deadline }
                : {}),
            },
            ...(access.token ? { editor_name: name } : {}),
          }),
        },
        access,
      );
      await refresh();
      setOpen(false);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function showHistory() {
    setError("");
    try {
      const result = await api<{ history: HumanReview[] }>(
        `meetings/${meetingId}/reports/${reportId}/reviews`,
        {},
        access,
      );
      setHistory(
        result.history.filter(
          (entry) => entry.category === category && entry.item_index === index,
        ),
      );
    } catch (e) {
      setError((e as Error).message);
    }
  }
  return (
    <div className={s.review} data-testid={`human-review-${category}-${index}`}>
      <div className={s.footer}>
        <span className={s.caption}>
          {english ? "Human review" : "Validation humaine"}
        </span>
        <span className={s.badge} data-status={review?.status || "unreviewed"}>
          {review
            ? labels[review.status]
            : english
              ? "Not reviewed"
              : "Non relu"}
        </span>
        {review && (
          <time className={s.date} dateTime={review.created}>
            {new Date(review.created).toLocaleString(
              english ? "en-GB" : "fr-FR",
            )}
          </time>
        )}
        <div className={s.controls}>
          {review && (
            <button className={s.button} onClick={() => void showHistory()}>
              {english ? "Review history" : "Historique des validations"}
            </button>
          )}
          {editable && !stale && (
            <button
              className={s.button}
              aria-expanded={open}
              onClick={() => setOpen(!open)}
            >
              {open
                ? english
                  ? "Close review"
                  : "Fermer la validation"
                : english
                  ? "Review this item"
                  : "Valider cet élément"}
            </button>
          )}
        </div>
      </div>
      {review && (
        <div className={s.corrections}>
          {stale && (
            <p className={s.warning}>
              {english
                ? "Review refers to an earlier transcript. Recheck the source."
                : "Cette validation porte sur une ancienne transcription. Vérifiez à nouveau la source."}
            </p>
          )}
          {review.corrections.text !== undefined && (
            <p>{review.corrections.text}</p>
          )}
          {(review.corrections.owner !== undefined ||
            review.corrections.deadline !== undefined) && (
            <dl className={s.metadata}>
              {review.corrections.owner !== undefined && (
                <div>
                  <dt>{english ? "Reviewed owner" : "Responsable corrigé"}</dt>
                  <dd>{review.corrections.owner || "—"}</dd>
                </div>
              )}
              {review.corrections.deadline !== undefined && (
                <div>
                  <dt>{english ? "Reviewed deadline" : "Échéance corrigée"}</dt>
                  <dd>{review.corrections.deadline || "—"}</dd>
                </div>
              )}
            </dl>
          )}
        </div>
      )}
      {open && editable && !stale && (
        <form
          className={s.form}
          onSubmit={(event) => {
            event.preventDefault();
            void save();
          }}
        >
          <p className={s.help}>
            {english
              ? "The original AI result stays above. This review is recorded separately."
              : "Le résultat IA original reste affiché au-dessus. Cette validation est enregistrée séparément."}
          </p>
          {(item.sources || []).map((id) => {
            const source = segments.find((segment) => segment.id === id);
            return source ? (
              <blockquote key={id}>
                {source.speaker ? `${source.speaker} : ` : ""}
                {source.text}
              </blockquote>
            ) : null;
          })}
          <label className={s.field}>
            {english ? "Status" : "Statut"}
            <select
              className={s.select}
              aria-label={english ? "Status" : "Statut"}
              value={status}
              onChange={(event) =>
                setStatus(event.target.value as HumanReview["status"])
              }
            >
              {Object.entries(labels).map(([value, label]) => (
                <option value={value} key={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label className={s.field}>
            {english ? "Reviewed wording" : "Texte après relecture"}
            <textarea
              className={s.textarea}
              required
              maxLength={3000}
              value={text}
              onChange={(event) => setText(event.target.value)}
            />
          </label>
          {category === "actions" && (
            <div className={s.formGrid}>
              <label className={s.field}>
                {english ? "Owner" : "Responsable"}
                <input
                  className={s.input}
                  maxLength={100}
                  value={owner}
                  onChange={(event) => setOwner(event.target.value)}
                />
              </label>
              <label className={s.field}>
                {english
                  ? "Deadline, as established"
                  : "Échéance, telle qu’établie"}
                <input
                  className={s.input}
                  maxLength={200}
                  value={deadline}
                  onChange={(event) => setDeadline(event.target.value)}
                />
              </label>
            </div>
          )}
          {access.token && (
            <label className={s.field}>
              {english ? "Your name" : "Votre nom"}
              <input
                required
                minLength={2}
                maxLength={100}
                className={s.input}
                value={name}
                onChange={(event) => setName(event.target.value)}
              />
            </label>
          )}
          <button className={`${s.button} ${s.primary}`} disabled={busy}>
            {busy
              ? english
                ? "Saving…"
                : "Enregistrement…"
              : english
                ? "Save human review"
                : "Enregistrer la validation humaine"}
          </button>
        </form>
      )}
      {history && (
        <ol className={s.history}>
          {history.map((entry) => (
            <li key={entry.id}>
              {labels[entry.status]} ·{" "}
              {new Date(entry.created).toLocaleString(
                english ? "en-GB" : "fr-FR",
              )}{" "}
              · v{entry.revision}
              {entry.editor_name ? ` · ${entry.editor_name}` : ""}
            </li>
          ))}
        </ol>
      )}
      {error && (
        <p role="alert" className={s.error}>
          {error}
        </p>
      )}
    </div>
  );
}
