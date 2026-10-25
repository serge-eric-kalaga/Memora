"use client";

import { useEffect, useRef, useState } from "react";
import { Check, Copy, FileCode2, Terminal } from "lucide-react";
import { useI18n } from "@/lib/i18n/use-i18n";
import styles from "./code-block.module.css";

type Language = "typescript" | "tsx" | "python" | "bash";

/** Coloration légère de documentation : conserver le texte exact, sans HTML injecté. */
function highlight(code: string, language: Language) {
  const pattern =
    language === "python" || language === "bash"
      ? /(#.*$|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|\b(?:from|import|def|return|async|await|as|if|else|in|True|False|None)\b|\b\d+\b)/gm
      : /(\/\/.*$|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|\b(?:import|from|export|const|let|type|interface|function|return|async|await|if|else|null|true|false)\b|\b\d+\b)/gm;
  return code.split(pattern).map((part, index) => {
    const kind =
      part.startsWith("#") || part.startsWith("//")
        ? "comment"
        : /^["']/.test(part)
          ? "string"
          : /^\d+$/.test(part)
            ? "number"
            : /^(from|import|def|return|async|await|as|if|else|in|True|False|None|export|const|let|type|interface|function|null|true|false)$/.test(
                  part,
                )
              ? "keyword"
              : undefined;
    return kind ? (
      <span key={index} className={styles[kind]}>
        {part}
      </span>
    ) : (
      part
    );
  });
}

/** Bloc autonome : copie du texte brut, retour local et nettoyage du délai au démontage. */
export function CodeBlock({
  code,
  language,
  label,
}: {
  code: string;
  language: Language;
  label: string;
}) {
  const { t } = useI18n();
  const [status, setStatus] = useState<"idle" | "copied" | "error">("idle");
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pending = useRef(false);
  useEffect(
    () => () => {
      if (timer.current) clearTimeout(timer.current);
    },
    [],
  );
  async function copy() {
    if (pending.current) return;
    pending.current = true;
    if (timer.current) clearTimeout(timer.current);
    try {
      await navigator.clipboard.writeText(code);
      setStatus("copied");
    } catch {
      setStatus("error");
    } finally {
      pending.current = false;
      timer.current = setTimeout(() => setStatus("idle"), 2400);
    }
  }
  const Icon = language === "bash" ? Terminal : FileCode2;
  const feedback =
    status === "copied"
      ? t("Copié !")
      : status === "error"
        ? t("Copie impossible")
        : "";
  return (
    <figure className={styles.block}>
      <figcaption className={styles.header}>
        <span className={styles.file}>
          <Icon size={16} aria-hidden="true" />
          <span>{label}</span>
        </span>
        <span className={styles.actions}>
          <span className={styles.language}>
            {language === "typescript"
              ? "TS"
              : language === "bash"
                ? "Shell"
                : language === "python"
                  ? "Python"
                  : "TSX"}
          </span>
          <button
            type="button"
            onClick={copy}
            className={styles.copy}
            data-copied={status === "copied"}
            aria-label={t("Copier le code : {{label}}", { label })}
          >
            {status === "copied" ? (
              <Check size={14} aria-hidden="true" />
            ) : (
              <Copy size={14} aria-hidden="true" />
            )}
            <span>{status === "copied" ? t("Copié !") : t("Copier")}</span>
          </button>
        </span>
      </figcaption>
      <pre tabIndex={0} aria-label={label}>
        <code>{highlight(code, language)}</code>
      </pre>
      <span
        role="status"
        aria-live="polite"
        className={status === "error" ? styles.error : styles.srOnly}
      >
        {feedback}
      </span>
    </figure>
  );
}
