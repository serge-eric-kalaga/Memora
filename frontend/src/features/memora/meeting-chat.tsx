"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { ArrowUp, Check, Copy, MessageSquare, Sparkles } from "lucide-react";
import { useI18n } from "@/lib/i18n/use-i18n";
import { api, clock, type Access, type Segment } from "./api";
import s from "./meeting-chat.module.css";
import { readableChatAnswer } from "./chat-answer";

type Message = {
  id?: string;
  created?: string | number;
  history_omitted?: number;
  context_scope?: string;
  version: number;
  question: string;
  answer: string;
  sources: string[];
};
export type MeetingChatProps = {
  id: string;
  access: Access;
  segments: Segment[];
  seek: (start: number, sourceVersion?: number) => void;
  currentVersion: number;
  history?: Message[];
  canSeek?: boolean;
  contextScope?: string;
};

/** Identity boundary prevents draft/answers leaking into another meeting or share. */
export function MeetingChat(props: MeetingChatProps) {
  return (
    <Conversation
      key={`${props.id}:${props.access.token || "owner"}:${props.access.password || ""}:${props.contextScope || "default"}`}
      {...props}
    />
  );
}
function Conversation({
  id,
  access,
  segments,
  seek,
  currentVersion,
  history = [],
  canSeek = true,
}: MeetingChatProps) {
  const { language } = useI18n();
  const en = language === "en";
  const t = (fr: string, english: string) => (en ? english : fr);
  const [question, setQuestion] = useState("");
  const [local, setLocal] = useState<Message[]>([]);
  const [pending, setPending] = useState("");
  const [error, setError] = useState("");
  const [copied, setCopied] = useState<number | null>(null);
  const request = useRef<AbortController | null>(null);
  const scroll = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLTextAreaElement>(null);
  const messages = useMemo(() => {
    const result = [...history];
    for (const message of local)
      if (
        !result.some(
          (existing) =>
            existing.version === message.version &&
            existing.question === message.question &&
            existing.answer === message.answer,
        )
      )
        result.push(message);
    return result;
  }, [history, local]);
  useEffect(
    () => () => {
      request.current?.abort();
    },
    [currentVersion],
  );
  useEffect(() => {
    const element = scroll.current;
    if (element) {
      const exchanges = element.querySelectorAll<HTMLElement>(
        "[data-chat-exchange]",
      );
      const latest = exchanges[exchanges.length - 1];
      if (latest)
        element.scrollTop +=
          latest.getBoundingClientRect().top -
          element.getBoundingClientRect().top -
          20;
    }
  }, [messages.length, pending, error]);
  async function send() {
    const text = question.trim();
    if (text.length < 2 || request.current) return;
    const controller = new AbortController();
    request.current = controller;
    setPending(text);
    setError("");
    try {
      const response = await api<{
        answer: string;
        id?: string;
        created?: string | number;
        history_omitted?: number;
        context_scope?: string;
        version: number;
        sources?: string[];
        citations?: string[];
      }>(
        `meetings/${id}/chat`,
        {
          method: "POST",
          body: JSON.stringify({ question: text }),
          signal: controller.signal,
        },
        access,
      );
      if (controller.signal.aborted) return;
      setLocal((previous) => [
        ...previous,
        {
          id: response.id,
          created: response.created,
          history_omitted: response.history_omitted,
          context_scope: response.context_scope,
          question: text,
          answer: response.answer,
          version: response.version,
          sources: response.sources || response.citations || [],
        },
      ]);
      setQuestion("");
    } catch (failure) {
      if (!controller.signal.aborted)
        setError(
          failure instanceof Error
            ? failure.message
            : t(
                "La réponse n’a pas pu être chargée.",
                "The answer could not be loaded.",
              ),
        );
    } finally {
      if (request.current === controller) {
        request.current = null;
        setPending("");
      }
    }
  }
  return (
    <section className={s.chat} aria-label="Memora IA">
      <header className={s.header}>
        <span className={s.symbol}>
          <Sparkles size={20} />
        </span>
        <div>
          <h2>Memora IA</h2>
          <p>
            {t(
              "Votre réunion, en conversation",
              "Your meeting, in conversation",
            )}
          </p>
        </div>
        <span className={s.status}>
          {pending
            ? t("Recherche…", "Searching…")
            : t("Conversation", "Conversation")}
        </span>
      </header>
      <div
        className={s.thread}
        ref={scroll}
        tabIndex={0}
        role="region"
        aria-label={t("Historique de la conversation", "Conversation history")}
      >
        {!messages.length && !pending && (
          <div className={s.empty}>
            <MessageSquare size={30} />
            <h3>
              {t(
                "Que souhaitez-vous retrouver ?",
                "What would you like to find?",
              )}
            </h3>
            <p>
              {t(
                "Retrouvez les décisions et les points importants de cette réunion.",
                "Find the decisions and key points from this meeting.",
              )}
            </p>
            <div className={s.suggestions}>
              {[
                t(
                  "Quelles décisions avons-nous prises ?",
                  "What decisions did we make?",
                ),
                t("Quelles actions restent à faire ?", "What actions remain?"),
              ].map((text) => (
                <button
                  key={text}
                  type="button"
                  onClick={() => {
                    setQuestion(text);
                    input.current?.focus();
                  }}
                >
                  {text}
                  <ArrowUp size={15} />
                </button>
              ))}
            </div>
          </div>
        )}
        {messages.map((message, index) => (
          <article
            key={message.id || `${index}:${message.version}`}
            className={s.exchange}
            data-chat-exchange
          >
            <div className={s.questionAnchor}>
              <div className={s.question}>
                <span className={s.sr}>{t("Vous :", "You:")}</span>
                {message.question}
              </div>
            </div>
            <div className={s.answer}>
              <div className={s.answerHeader}>
                <Sparkles size={15} />
                <strong>Memora IA</strong>
                <span>
                  v{message.version}
                  {message.version !== currentVersion
                    ? ` · ${t("Ancienne source", "Earlier source")}`
                    : ""}
                </span>
              </div>
              <AnswerBody answer={readableChatAnswer(message.answer)} />
              {message.created !== undefined &&
                (() => {
                  const date = new Date(
                    typeof message.created === "number"
                      ? message.created * 1000
                      : message.created,
                  );
                  return Number.isFinite(date.getTime()) ? (
                    <time
                      className={s.timestamp}
                      dateTime={date.toISOString()}
                      title={date.toLocaleString(en ? "en-GB" : "fr-FR")}
                    >
                      {date.toLocaleTimeString(en ? "en-GB" : "fr-FR", {
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </time>
                  ) : null;
                })()}
              {!!message.history_omitted && (
                <p className={s.notice}>
                  {t(
                    "Réponse fondée sur les échanges récents.",
                    "Answer based on recent exchanges.",
                  )}
                </p>
              )}
              {message.version === currentVersion &&
              message.sources.some((source) =>
                segments.some((item) => item.id === source),
              ) ? (
                <details className={s.sourceDetails}>
                  <summary>
                    {t("Voir les sources", "View sources")}{" "}
                    <span>
                      (
                      {
                        new Set(
                          message.sources.filter((source) =>
                            segments.some((item) => item.id === source),
                          ),
                        ).size
                      }
                      )
                    </span>
                  </summary>
                  <div className={s.sources}>
                    {[...new Set(message.sources)].map((source) => {
                      const segment = segments.find(
                        (item) => item.id === source,
                      );
                      return segment && canSeek ? (
                        <button
                          type="button"
                          key={source}
                          onClick={() => seek(segment.start, message.version)}
                          aria-label={`${t("Écouter la source", "Listen to source")} ${clock(segment.start)}`}
                        >
                          <span>{clock(segment.start)}</span>
                          <span>{segment.text}</span>
                        </button>
                      ) : segment ? (
                        <div className={s.source} key={source}>
                          <span>{clock(segment.start)}</span>
                          <span>{segment.text}</span>
                        </div>
                      ) : null;
                    })}
                  </div>
                </details>
              ) : message.version !== currentVersion ? (
                <p className={s.notice}>
                  {t(
                    "Réponse conservée dans son contexte original ; citations désactivées après correction de la transcription.",
                    "Answer kept in its original context; citations disabled after transcript corrections.",
                  )}
                </p>
              ) : null}
              <button
                className={s.copy}
                type="button"
                onClick={async () => {
                  try {
                    await navigator.clipboard.writeText(
                      readableChatAnswer(message.answer),
                    );
                    setCopied(index);
                  } catch {
                    setError(
                      t(
                        "Copie indisponible dans ce navigateur.",
                        "Copy is unavailable in this browser.",
                      ),
                    );
                  }
                }}
                aria-label={t("Copier la réponse", "Copy answer")}
              >
                {copied === index ? <Check size={14} /> : <Copy size={14} />}{" "}
                {copied === index ? t("Copié", "Copied") : t("Copier", "Copy")}
              </button>
            </div>
          </article>
        ))}
        {pending && (
          <div className={s.exchange} data-chat-exchange>
            <div className={s.questionAnchor}>
              <div className={s.question}>{pending}</div>
            </div>
            <p className={s.waiting} role="status">
              <Sparkles size={16} />
              {t("Recherche dans la réunion…", "Searching the meeting…")}
            </p>
          </div>
        )}
        {error && (
          <div className={s.error} role="alert">
            <p>{error}</p>
            {question.trim() && !pending && (
              <button type="button" onClick={() => void send()}>
                {t("Réessayer", "Retry")}
              </button>
            )}
          </div>
        )}
      </div>
      <form
        className={s.composer}
        onSubmit={(event) => {
          event.preventDefault();
          void send();
        }}
      >
        <label className={s.sr} htmlFor={`meeting-chat-${id}`}>
          {t("Votre question", "Your question")}
        </label>
        <div className={s.inputRow}>
          <textarea
            ref={input}
            id={`meeting-chat-${id}`}
            rows={2}
            maxLength={2000}
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder={t(
              "Posez une question sur cette réunion…",
              "Ask a question about this meeting…",
            )}
            onKeyDown={(event) => {
              if (
                event.key === "Enter" &&
                !event.shiftKey &&
                !event.nativeEvent.isComposing
              ) {
                event.preventDefault();
                void send();
              }
            }}
          />
          <button
            type="submit"
            disabled={!!pending || question.trim().length < 2}
            aria-label={t("Poser la question", "Ask question")}
          >
            <ArrowUp size={19} />
          </button>
        </div>
        <p>
          {t(
            "Entrée pour envoyer · Maj+Entrée pour une nouvelle ligne. Vérifiez les passages sources.",
            "Enter to send · Shift+Enter for a new line. Check the source passages.",
          )}
        </p>
      </form>
    </section>
  );
}

/** Small safe formatter: no HTML interpretation, links or model-generated markup execution. */
function AnswerBody({ answer }: { answer: string }) {
  const inline = (text: string) =>
    text
      .split(/(\*\*[^*]+\*\*)/g)
      .map((part, i) =>
        part.startsWith("**") && part.endsWith("**") ? (
          <strong key={i}>{part.slice(2, -2)}</strong>
        ) : (
          part
        ),
      );
  return (
    <div className={s.answerBody}>
      {answer
        .split(/\n\s*\n/)
        .filter(Boolean)
        .map((block, i) => {
          const lines = block.split("\n");
          if (lines.every((line) => /^\s*[-*•]\s+/.test(line)))
            return (
              <ul key={i}>
                {lines.map((line, j) => (
                  <li key={j}>{inline(line.replace(/^\s*[-*•]\s+/, ""))}</li>
                ))}
              </ul>
            );
          if (lines.every((line) => /^\s*\d+[.)]\s+/.test(line)))
            return (
              <ol key={i}>
                {lines.map((line, j) => (
                  <li key={j}>{inline(line.replace(/^\s*\d+[.)]\s+/, ""))}</li>
                ))}
              </ol>
            );
          if (/^#{1,6}\s+[^\n]+$/.test(block))
            return <h3 key={i}>{inline(block.replace(/^#{1,6}\s+/, ""))}</h3>;
          return <p key={i}>{inline(block)}</p>;
        })}
    </div>
  );
}
