"use client";

import { Download, FileText, LoaderCircle } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Modal } from "@/components/ui/modal";
import { useI18n } from "@/lib/i18n/use-i18n";
import { accessHeaders, type Access } from "./api";
import s from "./export-button.module.css";

type Format = "txt" | "pdf" | "docx" | "md" | "srt" | "vtt";
type Target = {
  meetingId: string;
  version?: number;
  reportId?: string;
  label: string;
};
const descriptions: Record<Format, [string, string]> = {
  txt: ["Texte simple, facile à copier", "Plain text, easy to copy"],
  pdf: [
    "Document mis en page, prêt à partager",
    "Formatted document, ready to share",
  ],
  docx: ["Document modifiable dans Word", "Editable Word document"],
  md: ["Texte structuré en Markdown", "Structured Markdown text"],
  srt: ["Sous-titres avec repères temporels", "Subtitles with timestamps"],
  vtt: ["Sous-titres pour les lecteurs web", "Subtitles for web players"],
};

function downloadName(header: string | null, fallback: string, format: Format) {
  const encoded = header?.match(/filename\*=UTF-8''([^;]+)/i)?.[1];
  const quoted = header?.match(/filename="([^"]+)"/i)?.[1];
  let name = quoted || fallback;
  if (encoded) {
    try {
      name = decodeURIComponent(encoded);
    } catch {
      /* Use the safe fallback. */
    }
  }
  name = name.replace(/[\u0000-\u001f\u007f/\\]/g, "-").slice(0, 170);
  return name.toLowerCase().endsWith(`.${format}`) ? name : `${name}.${format}`;
}

export function ExportButton({
  meetingId,
  content,
  version,
  reportId,
  label,
  access,
  disabled = false,
}: {
  meetingId: string;
  content: "transcript" | "report";
  version?: number;
  reportId?: string;
  label: string;
  access: Access;
  disabled?: boolean;
}) {
  const { language } = useI18n();
  const en = language === "en";
  const [target, setTarget] = useState<Target | null>(null);
  const [format, setFormat] = useState<Format>("pdf");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const request = useRef<AbortController | null>(null);
  const urls = useRef(new Set<string>());
  useEffect(
    () => () => {
      request.current?.abort();
      for (const url of urls.current) URL.revokeObjectURL(url);
      urls.current.clear();
    },
    [],
  );
  const formats: Format[] =
    content === "transcript"
      ? ["pdf", "docx", "txt", "srt", "vtt"]
      : ["pdf", "docx", "txt", "md"];
  const title =
    content === "transcript"
      ? en
        ? "Export transcript"
        : "Exporter la transcription"
      : en
        ? "Export report"
        : "Exporter le rapport";
  function close() {
    request.current?.abort();
    request.current = null;
    setTarget(null);
    setBusy(false);
  }
  async function download() {
    if (!target || busy || request.current) return;
    const controller = new AbortController();
    request.current = controller;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const query = new URLSearchParams({ content, format });
      if (target.version !== undefined)
        query.set("version", String(target.version));
      if (target.reportId) query.set("report_id", target.reportId);
      const response = await fetch(
        `/mapi/meetings/${encodeURIComponent(target.meetingId)}/export?${query}`,
        {
          headers: accessHeaders(access),
          cache: "no-store",
          signal: controller.signal,
        },
      );
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(
          typeof body.detail === "string"
            ? body.detail
            : body.message ||
              (en
                ? "The export could not be downloaded. Try again."
                : "Le téléchargement a échoué. Réessayez."),
        );
      }
      const blob = await response.blob();
      if (controller.signal.aborted) return;
      const url = URL.createObjectURL(blob);
      urls.current.add(url);
      const link = document.createElement("a");
      link.href = url;
      link.download = downloadName(
        response.headers.get("content-disposition"),
        `memora-${content}`,
        format,
      );
      document.body.append(link);
      link.click();
      link.remove();
      setTimeout(() => {
        URL.revokeObjectURL(url);
        urls.current.delete(url);
      }, 60000);
      setMessage(en ? "Download started." : "Téléchargement lancé.");
    } catch (e) {
      if (!controller.signal.aborted) setError((e as Error).message);
    } finally {
      if (request.current === controller) {
        request.current = null;
        setBusy(false);
      }
    }
  }
  return (
    <>
      <button
        type="button"
        className={s.trigger}
        disabled={disabled}
        aria-label={title}
        onClick={() => {
          setTarget({ meetingId, version, reportId, label });
          setFormat("pdf");
          setError("");
          setMessage("");
        }}
      >
        <Download size={15} aria-hidden="true" />
        {en ? "Export" : "Exporter"}
      </button>
      <Modal
        open={target !== null}
        onClose={close}
        title={title}
        description={
          en
            ? "Download the selected version in the format you need."
            : "Téléchargez la version sélectionnée dans le format qui vous convient."
        }
      >
        <div className={s.source}>
          <FileText size={17} aria-hidden="true" />
          <span>{target?.label}</span>
        </div>
        <fieldset className={s.formats} disabled={busy}>
          <legend>{en ? "File format" : "Format du fichier"}</legend>
          {formats.map((value) => (
            <label
              key={value}
              className={`${s.option} ${format === value ? s.selected : ""}`}
            >
              <input
                type="radio"
                name={`export-format-${content}`}
                value={value}
                checked={format === value}
                onChange={() => {
                  setFormat(value);
                  setMessage("");
                  setError("");
                }}
              />
              <span className={s.extension}>{value.toUpperCase()}</span>
              <span>{descriptions[value][en ? 1 : 0]}</span>
            </label>
          ))}
        </fieldset>
        {error && (
          <p className={s.error} role="alert">
            {error}
          </p>
        )}
        {message && (
          <p className={s.message} role="status">
            {message}
          </p>
        )}
        <div className={s.actions}>
          <button type="button" className={s.cancel} onClick={close}>
            {en ? "Close" : "Fermer"}
          </button>
          <button
            type="button"
            className={s.download}
            disabled={busy}
            onClick={() => void download()}
          >
            {busy ? (
              <LoaderCircle size={16} className="spin" aria-hidden="true" />
            ) : (
              <Download size={16} aria-hidden="true" />
            )}
            {busy
              ? en
                ? "Preparing…"
                : "Préparation…"
              : en
                ? "Download"
                : "Télécharger"}
          </button>
        </div>
      </Modal>
    </>
  );
}
