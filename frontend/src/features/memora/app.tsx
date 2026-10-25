"use client";
import { useMemoraText } from "./i18n";
import { describeSegmentLanguage } from "./language";
import { useI18n } from "@/lib/i18n/use-i18n";
import {
  useCallback,
  useEffect,
  useEffectEvent,
  useId,
  useSyncExternalStore,
  useRef,
  useState,
} from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  AudioLines,
  Plus,
  Upload,
  Mic,
  Search,
  ArrowUpRight,
  FileText,
  Archive,
  Settings,
  Bell,
  Play,
  Pause,
  Square,
  RefreshCw,
  Share2,
  Download,
  Check,
  X,
  Send,
  ShieldCheck,
  Sparkles,
  CalendarDays,
  Clock3,
} from "lucide-react";
import { useSession } from "@/features/auth/hooks";
import {
  api,
  ApiError,
  accessHeaders,
  clock,
  labels,
  type Meeting,
  type Segment,
  type Access,
  type Report,
  type Item,
  type Share,
} from "./api";
import { saveChunk, pendingChunks, removeChunk } from "./storage";
import s from "./memora.module.css";
const btn = s.button,
  primary = `${s.button} ${s.primary}`;
function ErrorBox({ error }: { error: string }) {
  return error ? (
    <div className={s.error} role="alert">
      {error}
    </div>
  ) : null;
}
const subscribeHydration = () => () => {};
function AuthGate({ children }: { children: React.ReactNode }) {
  const tr = useMemoraText();
  const session = useSession();
  const hydrated = useSyncExternalStore(
    subscribeHydration,
    () => true,
    () => false,
  );
  if (!hydrated || session.isPending)
    return <div className={s.loading}>{tr("Chargement de votre espace…")}</div>;
  if (session.isError)
    return (
      <div className={s.card}>
        <ErrorBox error={tr("Le service de connexion est indisponible.")} />
        <button className={btn} onClick={() => void session.refetch()}>
          {tr("Réessayer la connexion")}
        </button>
      </div>
    );
  if (!session.data)
    return (
      <div className={`${s.card} ${s.login}`}>
        <AudioLines size={45} />
        <h1>{tr("Vos réunions, en clair.")}</h1>
        <p>
          {tr(
            "Enregistrez, transcrivez et retrouvez chaque décision grâce à une IA locale.",
          )}
        </p>
        <div className={s.actions}>
          <Link className={primary} href="/connexion">
            {tr("Se connecter")}
          </Link>
          <Link className={btn} href="/inscription">
            {tr("Créer un compte")}
          </Link>
        </div>
        {session.isError && (
          <p>{tr("Le service de connexion est indisponible.")}</p>
        )}
      </div>
    );
  return children;
}
function Navigation() {
  const tr = useMemoraText();
  return (
    <nav className={s.nav} aria-label={tr("Espace réunions")}>
      <Link className={btn} href="/">
        <AudioLines size={16} />
        {tr("Réunions")}
      </Link>
      <Link className={btn} href="/parametres">
        <Settings size={16} />
        {tr("Paramètres")}
      </Link>
    </nav>
  );
}
function Modal({
  title,
  close,
  children,
}: {
  title: string;
  close: () => void;
  children: React.ReactNode;
}) {
  const tr = useMemoraText();
  const dialog = useRef<HTMLElement>(null);
  const onClose = useEffectEvent(close);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const panel = dialog.current;
    (
      panel?.querySelector<HTMLElement>("[data-dialog-autofocus]") ||
      panel?.querySelector<HTMLElement>("button,input,textarea,select,a[href]")
    )?.focus();
    const key = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
      }
      if (event.key === "Tab" && panel) {
        const nodes = Array.from(
          panel.querySelectorAll<HTMLElement>(
            "button:not(:disabled),input:not(:disabled),textarea,select,a[href]",
          ),
        );
        const first = nodes[0],
          last = nodes[nodes.length - 1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last?.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first?.focus();
        }
      }
    };
    document.addEventListener("keydown", key);
    return () => {
      document.removeEventListener("keydown", key);
      previous?.focus();
    };
  }, []);
  return (
    <div className={s.overlay} onClick={close}>
      <section
        ref={dialog}
        className={s.modal}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onClick={(e) => e.stopPropagation()}
      >
        <div className={s.row}>
          <h2>{title}</h2>
          <button className={btn} onClick={close} aria-label={tr("Fermer")}>
            <X size={17} />
          </button>
        </div>
        {children}
      </section>
    </div>
  );
}
export function Dashboard() {
  return (
    <main className={s.app}>
      <AuthGate>
        <DashboardContent />
      </AuthGate>
    </main>
  );
}
function DashboardContent() {
  const tr = useMemoraText();
  const { language } = useI18n();
  const router = useRouter();
  const [meetings, setMeetings] = useState<Meeting[]>([]),
    [error, setError] = useState(""),
    [loading, setLoading] = useState(true),
    [query, setQuery] = useState(""),
    [filter, setFilter] = useState("active"),
    [create, setCreate] = useState(false),
    [title, setTitle] = useState(""),
    [transcriptionLanguage, setTranscriptionLanguage] = useState<string | null>(
      null,
    ),
    [busy, setBusy] = useState(false),
    [notices, setNotices] = useState<
      {
        id: string;
        message?: string;
        title?: string;
        meeting?: string;
        data?: {
          text?: string;
        };
        seen?: boolean;
      }[]
    >([]),
    [showNotices, setShowNotices] = useState(false),
    [showMail, setShowMail] = useState(false);
  const load = useCallback(async () => {
    try {
      const data = await api<
        | Meeting[]
        | {
            items: Meeting[];
          }
      >("meetings?include_archived=true");
      setMeetings(Array.isArray(data) ? data : data.items);
      setError("");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => {
    queueMicrotask(() => void load());
    const timer = setInterval(() => {
      void load();
      void api<typeof notices>("notifications")
        .then(setNotices)
        .catch(() => {});
    }, 5000);
    void api<typeof notices>("notifications")
      .then(setNotices)
      .catch(() => {});
    return () => clearInterval(timer);
  }, [load]);
  async function createMeeting(mode: string) {
    setBusy(true);
    try {
      const m = await api<Meeting>("meetings", {
        method: "POST",
        body: JSON.stringify({
          title: title.trim() || tr("Nouvelle réunion"),
          mode,
          transcription_language: transcriptionLanguage || language,
        }),
      });
      router.push(`/reunions/${m.id}`);
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  }
  const visible = meetings.filter(
    (m) =>
      (filter === "archives" ? m.archived : !m.archived) &&
      (filter !== "ready" || m.state === "ready") &&
      m.title.toLowerCase().includes(query.toLowerCase()),
  );
  return (
    <>
      <div className={s.top}>
        <div>
          <div className={s.eyebrow}>{tr("VOTRE MÉMOIRE COLLECTIVE")}</div>
          <h1>{tr("Mes réunions")}</h1>
          <p className={s.sub}>
            {tr("Moins de notes. Plus de présence. Aucune décision oubliée.")}
          </p>
        </div>
        <div className={s.actions}>
          <button
            className={btn}
            onClick={() => setShowNotices(!showNotices)}
            aria-label={tr("Notifications")}
          >
            <Bell size={18} />
            {notices.filter((n) => !n.seen).length || ""}
          </button>
          <button className={btn} onClick={() => setShowMail(true)}>
            <Send size={17} />
            Emails
          </button>
          <button className={primary} onClick={() => setCreate(true)}>
            <Plus size={18} />
            {tr("Nouvelle réunion")}
          </button>
        </div>
      </div>
      <Navigation />
      {showMail && (
        <Modal title={tr("Suivi des emails")} close={() => setShowMail(false)}>
          <MailStatus />
        </Modal>
      )}
      {showNotices && (
        <section className={s.card}>
          <h2>{tr("Notifications")}</h2>
          {!notices.length ? (
            <p className={s.muted}>
              {tr("Aucune notification pour le moment.")}
            </p>
          ) : (
            notices.map((n) => (
              <button
                className={s.notification}
                key={n.id}
                onClick={async () => {
                  await api(`notifications/${n.id}`, {
                    method: "PATCH",
                    body: JSON.stringify({ read: true }),
                  });
                  if (n.meeting) router.push(`/reunions/${n.meeting}`);
                }}
              >
                {n.data?.text ||
                  n.message ||
                  n.title ||
                  tr("Votre rapport est disponible")}
              </button>
            ))
          )}
        </section>
      )}
      <div className={s.stats}>
        {[
          [tr("Réunions"), meetings.filter((m) => !m.archived).length],
          [
            tr("Rapports disponibles"),
            meetings.filter((m) => m.state === "ready" && !m.archived).length,
          ],
          [
            tr("En préparation"),
            meetings.filter(
              (m) =>
                !m.archived &&
                ["queued", "analyzing", "transcribing"].includes(m.state),
            ).length,
          ],
        ].map(([label, value]) => (
          <div className={`${s.card} ${s.stat}`} key={label}>
            <span className={s.muted}>{label}</span>
            <strong>{value}</strong>
          </div>
        ))}
      </div>
      <div className={s.toolbar}>
        <div className={s.actions}>
          {[
            ["active", tr("Toutes")],
            ["ready", tr("Terminées")],
            ["archives", tr("Archives")],
          ].map(([key, label]) => (
            <button
              key={key}
              className={filter === key ? primary : btn}
              onClick={() => setFilter(key)}
            >
              {label}
            </button>
          ))}
        </div>
        <label className={`${s.actions} ${s.search}`}>
          <Search size={18} />
          <input
            className={s.input}
            aria-label={tr("Rechercher une réunion")}
            placeholder={tr("Rechercher une réunion…")}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </label>
      </div>
      <ErrorBox error={error} />
      {loading ? (
        <div className={s.loading}>{tr("Chargement des réunions…")}</div>
      ) : visible.length ? (
        <div className={s.meetingList}>
          <div className={s.listHeader} aria-hidden="true">
            <span>{tr("Réunion")}</span>
            <span>{tr("Date de création")}</span>
            <span>{tr("Durée")}</span>
            <span>{tr("Source")}</span>
            <span>{tr("État")}</span>
            <span />
          </div>
          {visible.map((m) => (
            <Link
              href={`/reunions/${m.id}`}
              key={m.id}
              className={s.meetingRow}
            >
              <div className={s.meetingIdentity}>
                <span
                  className={`${s.meetingIcon} ${m.mode === "import" ? s.importIcon : ""}`}
                >
                  {m.mode === "import" ? (
                    <Upload size={20} />
                  ) : (
                    <Mic size={20} />
                  )}
                </span>
                <div>
                  <h2>{m.title}</h2>
                  <p className={s.muted}>
                    {m.meeting_date
                      ? `${tr("Réunion du")} ${m.meeting_date}`
                      : tr("Date de réunion non renseignée")}
                  </p>
                </div>
              </div>
              <div className={s.meetingDate}>
                <span>
                  {new Date(m.created).toLocaleDateString("fr-FR", {
                    day: "numeric",
                    month: "short",
                    year: "numeric",
                  })}
                </span>
                <small>
                  {m.mode === "import" ? tr("Importé le") : tr("Créée le")}
                </small>
              </div>
              <span className={s.meetingDuration}>{clock(m.duration)}</span>
              <span className={s.meetingMode}>
                {m.mode === "import"
                  ? tr("Audio importé")
                  : tr("Enregistrement direct")}
              </span>
              <span
                className={`${s.badge} ${m.state === "ready" ? s.readyBadge : ""}`}
              >
                {tr(labels[m.state] || m.state)}
              </span>
              <ArrowUpRight size={17} className={s.meetingArrow} />
            </Link>
          ))}
          <div className={s.listFooter}>
            {visible.length} {tr("réunions dans cette vue")}
          </div>
        </div>
      ) : (
        <div className={`${s.card} ${s.empty}`}>
          <AudioLines size={40} />
          <h2>
            {query
              ? tr("Aucune réunion trouvée")
              : filter === "archives"
                ? tr("Vos archives sont vides")
                : tr("Une réunion à retenir ?")}
          </h2>
          <p className={s.muted}>
            {tr(
              "Enregistrez une conversation ou importez un fichier audio pour commencer.",
            )}
          </p>
        </div>
      )}
      {create && (
        <Modal title={tr("Nouvelle réunion")} close={() => setCreate(false)}>
          <label className={s.field}>
            <span>{tr("Titre de la réunion")}</span>
            <input
              data-dialog-autofocus
              className={s.input}
              maxLength={200}
              placeholder={tr("Ex. Point équipe du lundi")}
              value={title}
              onChange={(e) => setTitle(e.target.value)}
            />
          </label>
          <AudioLanguage
            value={transcriptionLanguage || language}
            onChange={setTranscriptionLanguage}
          />
          <p className={s.muted}>
            {tr(
              "L’enregistrement ne commence qu’après votre action explicite. Informez les participants avant de commencer.",
            )}
          </p>
          <div className={s.actions} style={{ marginTop: 24 }}>
            <button
              disabled={busy}
              className={primary}
              onClick={() => void createMeeting("recording")}
            >
              <Mic size={18} />
              {tr("Enregistrer")}
            </button>
            <button
              disabled={busy}
              className={btn}
              onClick={() => void createMeeting("import")}
            >
              <Upload size={18} />
              {tr("Importer un audio")}
            </button>
          </div>
        </Modal>
      )}
    </>
  );
}
export function MeetingPage({
  id,
  access = {},
  initial,
}: {
  id: string;
  access?: Access;
  initial?: Meeting;
}) {
  return (
    <main className={`${s.app} ${s.meetingApp}`}>
      {access.token ? (
        <MeetingContent id={id} access={access} initial={initial} />
      ) : (
        <AuthGate>
          <MeetingContent id={id} access={access} />
        </AuthGate>
      )}
    </main>
  );
}
function MeetingContent({
  id,
  access,
  initial,
}: {
  id: string;
  access: Access;
  initial?: Meeting;
}) {
  const tr = useMemoraText();
  const router = useRouter();
  const [editorName, setEditorName] = useState("");
  const [captureState, setCaptureState] = useState("idle");
  const [editVersion, setEditVersion] = useState(0);
  const [selectedStart, setSelectedStart] = useState<number | null>(null);
  const [selectedTranscriptVersion, setSelectedTranscriptVersion] = useState<
    number | null
  >(null);
  const [historicalTranscript, setHistoricalTranscript] = useState<{
    version: number;
    segments: Segment[];
  } | null>(null);
  const transcriptPanel = useRef<HTMLElement>(null);
  const [renaming, setRenaming] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [retranscriptionLanguage, setRetranscriptionLanguage] = useState<
    string | null
  >(null);
  const [meeting, setMeeting] = useState<Meeting | null>(initial || null),
    [error, setError] = useState(""),
    [tab, setTab] = useState("report"),
    [busy, setBusy] = useState(false),
    [shareOpen, setShareOpen] = useState(false),
    [editing, setEditing] = useState(false),
    [segments, setSegments] = useState<Segment[]>([]),
    [selectedReportId, setSelectedReportId] = useState(""),
    [audioUrl, setAudioUrl] = useState(""),
    [audioExtension, setAudioExtension] = useState("bin");
  const audio = useRef<HTMLAudioElement>(null);
  const load = useCallback(async () => {
    try {
      setMeeting(
        await api<Meeting>(
          `meetings/${id}`,
          {},
          { token: access.token, password: access.password },
        ),
      );
    } catch (e) {
      if (
        access.token &&
        e instanceof ApiError &&
        [401, 403, 404].includes(e.status)
      ) {
        audio.current?.pause();
        setAudioUrl("");
        setMeeting(null);
      }
      setError((e as Error).message);
    }
  }, [id, access.token, access.password]);
  useEffect(() => {
    queueMicrotask(() => void load());
    const timer = setInterval(() => void load(), 3500);
    return () => clearInterval(timer);
  }, [load]);
  useEffect(() => {
    if (!meeting?.audio_available || !meeting.duration) return;
    const controller = new AbortController();
    let url = "";
    fetch(`/mapi/meetings/${id}/audio`, {
      headers: accessHeaders({
        token: access.token,
        password: access.password,
      }),
      signal: controller.signal,
    })
      .then(async (r) => {
        if (!r.ok) throw Error(tr("Audio indisponible"));
        const blob = await r.blob();
        const extensions: Record<string, string> = {
          "audio/wav": "wav",
          "audio/x-wav": "wav",
          "audio/webm": "webm",
          "video/webm": "webm",
          "audio/mpeg": "mp3",
          "audio/mp3": "mp3",
          "audio/mp4": "m4a",
          "video/mp4": "m4a",
          "audio/ogg": "ogg",
          "application/ogg": "ogg",
          "audio/flac": "flac",
          "audio/x-flac": "flac",
        };
        setAudioExtension(extensions[blob.type.split(";")[0]] || "bin");
        url = URL.createObjectURL(blob);
        setAudioUrl(url);
      })
      .catch((e) => {
        if (e.name !== "AbortError") setError(e.message);
      });
    return () => {
      controller.abort();
      if (url) URL.revokeObjectURL(url);
    };
  }, [
    id,
    meeting?.audio_available,
    meeting?.duration,
    access.token,
    access.password,
    tr,
  ]);
  useEffect(() => {
    if (
      !selectedTranscriptVersion ||
      selectedTranscriptVersion === meeting?.version
    )
      return;
    let ignore = false;
    void api<{ version: number; segments: Segment[] }>(
      `meetings/${id}/transcript?version=${selectedTranscriptVersion}`,
      {},
      { token: access.token, password: access.password },
    )
      .then((data) => {
        if (!ignore) setHistoricalTranscript(data);
      })
      .catch((e) => {
        if (!ignore) setError(e.message);
      });
    return () => {
      ignore = true;
    };
  }, [
    id,
    selectedTranscriptVersion,
    meeting?.version,
    access.token,
    access.password,
  ]);
  useEffect(() => {
    if (selectedStart === null || tab !== "transcript") return;
    const frame = requestAnimationFrame(() =>
      transcriptPanel.current
        ?.querySelector<HTMLElement>(`[data-segment-start="${selectedStart}"]`)
        ?.scrollIntoView({ behavior: "smooth", block: "center" }),
    );
    return () => cancelAnimationFrame(frame);
  }, [selectedStart, tab, meeting?.version, historicalTranscript]);
  async function action(path: string, method = "POST", body?: unknown) {
    setBusy(true);
    setError("");
    try {
      await api(
        `meetings/${id}${path}`,
        {
          method,
          ...(body === undefined ? {} : { body: JSON.stringify(body) }),
        },
        access,
      );
      await load();
      return true;
    } catch (e) {
      setError((e as Error).message);
      return false;
    } finally {
      setBusy(false);
    }
  }
  function seek(start: number, sourceVersion?: number) {
    if (!access.token || meeting?.permissions?.transcript) {
      setSelectedStart(start);
      setSelectedTranscriptVersion(
        sourceVersion && sourceVersion !== meeting?.version
          ? sourceVersion
          : null,
      );
      setTab("transcript");
    }
    if (audio.current) {
      audio.current.currentTime = start;
      void audio.current.play().catch(() => {});
    }
  }
  if (!meeting)
    return (
      <>
        <ErrorBox error={error} />
        {!error && (
          <div className={s.loading}>{tr("Ouverture de la réunion…")}</div>
        )}
      </>
    );
  const reports = meeting.reports || [],
    report =
      reports.find((r) => r.id === (selectedReportId || meeting.report_id)) ||
      reports[0],
    permissions = meeting.permissions || {};
  const currentTab =
    tab === "report" && access.token && !permissions.report
      ? permissions.transcript
        ? "transcript"
        : permissions.chat
          ? "chat"
          : "audio"
      : tab;
  const canEdit =
    !access.token || permissions.edit_transcript || permissions.edit;
  const canChat = !access.token || permissions.chat;
  const canAudio = !access.token || permissions.audio;
  const canTranscript = !access.token || permissions.transcript;
  const chapterReport = reports.find((r) => r.id === meeting.report_id);
  const chapters = canTranscript
    ? (chapterReport?.data.topics || []).flatMap((item) => {
        if (typeof item === "string") return [];
        const source = (meeting.segments || []).find((segment) =>
          item.sources?.includes(segment.id),
        );
        return source ? [{ text: item.text, start: source.start }] : [];
      })
    : [];
  const viewedTranscriptVersion = selectedTranscriptVersion || meeting.version;
  const isHistoricalTranscript = viewedTranscriptVersion !== meeting.version;
  const viewedSegments = isHistoricalTranscript
    ? historicalTranscript?.version === viewedTranscriptVersion
      ? historicalTranscript.segments
      : []
    : meeting.segments?.length
      ? meeting.segments
      : meeting.live_segments || [];
  return (
    <>
      <div className={s.top}>
        <div>
          <Link className={s.muted} href="/">
            {tr("← Toutes les réunions")}
          </Link>
          <div className={s.eyebrow} style={{ marginTop: 18 }}>
            {tr("ESPACE RÉUNION")}
          </div>
          {renaming ? (
            <form
              onSubmit={async (e) => {
                e.preventDefault();
                if (await action("", "PATCH", { title: newTitle.trim() }))
                  setRenaming(false);
              }}
            >
              <label className={s.field}>
                <span>{tr("Titre de la réunion")}</span>
                <input
                  autoFocus
                  required
                  minLength={1}
                  maxLength={200}
                  className={s.input}
                  value={newTitle}
                  onChange={(e) => setNewTitle(e.target.value)}
                />
              </label>
              <div className={s.actions}>
                <button className={primary} disabled={busy || !newTitle.trim()}>
                  {tr("Enregistrer le titre")}
                </button>
                <button
                  type="button"
                  className={btn}
                  onClick={() => setRenaming(false)}
                >
                  {tr("Annuler")}
                </button>
              </div>
            </form>
          ) : (
            <h1>{meeting.title}</h1>
          )}
          {!access.token && !renaming && (
            <button
              className={s.time}
              onClick={() => {
                setNewTitle(meeting.title);
                setRenaming(true);
              }}
            >
              {tr("Modifier le titre")}
            </button>
          )}
          <p className={`${s.sub} ${s.meetingMeta}`}>
            <span>
              <CalendarDays size={14} />
              {meeting.mode === "import"
                ? tr("Importé le")
                : tr("Créée le")}{" "}
              {new Date(meeting.created).toLocaleString("fr-FR")}
            </span>
            <span>
              <Clock3 size={14} />
              {clock(meeting.duration)}
            </span>
            <span>
              {meeting.mode === "import" ? (
                <Upload size={14} />
              ) : (
                <Mic size={14} />
              )}{" "}
              {meeting.mode === "import"
                ? tr("Audio importé")
                : tr("Enregistrement direct")}
            </span>
            <span className={s.badge}>
              {tr(labels[meeting.state] || meeting.state)}
            </span>
            {!access.token && (
              <button
                className={s.time}
                onClick={() => setShareOpen(true)}
                title={tr(
                  "Tous les liens configurés, y compris les liens expirés ou révoqués.",
                )}
              >
                {tr("Liens de partage :")} {(meeting.shares || []).length}
              </button>
            )}
          </p>
        </div>
        {!access.token && (
          <div className={s.actions}>
            <button className={primary} onClick={() => setShareOpen(true)}>
              <Share2 size={16} />
              {tr("Partager")}
            </button>
            <button
              className={btn}
              disabled={busy}
              onClick={() =>
                void action("", "PATCH", { archived: !meeting.archived })
              }
            >
              <Archive size={16} />
              {meeting.archived ? tr("Restaurer") : tr("Archiver")}
            </button>
          </div>
        )}
      </div>
      {!access.token && <Navigation />}
      <ErrorBox error={error || meeting.error || ""} />
      {meeting.archived && (
        <div className={s.notice}>
          {tr(
            "Cette réunion est archivée. Ses liens de partage restent actifs jusqu’à leur expiration ou révocation.",
          )}
        </div>
      )}
      {!access.token &&
        ["draft", "recording", "paused", "interrupted"].includes(
          meeting.state,
        ) && (
          <Recorder
            meeting={meeting}
            refresh={load}
            onCaptureState={setCaptureState}
          />
        )}
      {["queued", "transcribing", "analyzing"].includes(meeting.state) && (
        <div className={s.notice} role="status">
          <RefreshCw size={16} /> {labels[meeting.state]}
          {tr(
            "… Vous pouvez quitter cette page. Une notification vous avertira à la fin.",
          )}
        </div>
      )}
      {(meeting.version > 0 ||
        (meeting.audio_available && Boolean(meeting.duration))) &&
        canEdit && (
          <div className={s.actions}>
            <button
              className={btn}
              disabled={
                busy ||
                ["queued", "transcribing", "analyzing"].includes(meeting.state)
              }
              onClick={() =>
                void action("/analyze", "POST", {
                  request_id: crypto.randomUUID(),
                })
              }
            >
              <RefreshCw size={16} />
              {reports.length
                ? tr("Régénérer le rapport")
                : tr("Lancer / reprendre l’analyse")}
            </button>
          </div>
        )}
      {meeting.report_version !== undefined &&
        meeting.version > meeting.report_version &&
        reports.length > 0 && (
          <div className={s.notice}>
            {tr(
              "La transcription a été corrigée. Le rapport est à actualiser ; le chat utilise la transcription courante.",
            )}
          </div>
        )}
      <div className={s.tabs}>
        {[
          ...(!access.token || permissions.report
            ? [["report", tr("Rapport")]]
            : []),
          ...(canTranscript ? [["transcript", "Transcription"]] : []),
          ...(canChat ? [["chat", tr("Chat IA")]] : []),
        ].map(([key, label]) => (
          <button
            className={`${s.tab} ${currentTab === key ? s.active : ""}`}
            key={key}
            onClick={() => {
              setTab(key);
              if (
                key === "chat" &&
                window.matchMedia("(max-width: 1100px)").matches
              )
                requestAnimationFrame(() =>
                  document
                    .getElementById("meeting-chat-panel")
                    ?.scrollIntoView({
                      behavior: "smooth",
                      block: "start",
                    }),
                );
            }}
          >
            {label}
          </button>
        ))}
      </div>
      <div className={s.two}>
        <div>
          {(currentTab === "report" || currentTab === "chat") &&
            (!access.token || permissions.report) && (
              <section className={`${s.card} ${s.report}`}>
                <div className={s.row}>
                  <h2>{tr("Compte rendu")}</h2>
                  {reports.length > 0 && (
                    <select
                      className={s.select}
                      style={{ width: "auto" }}
                      aria-label={tr("Version du rapport")}
                      value={report?.id || ""}
                      onChange={(e) => setSelectedReportId(e.target.value)}
                    >
                      {reports.map((r) => (
                        <option key={r.id} value={r.id}>
                          {tr("Version")}
                          {r.revision || r.version} · source v{r.version}
                          {r.id === meeting.report_id
                            ? tr(" · Courante")
                            : tr(" · Historique")}{" "}
                          · {new Date(r.created).toLocaleDateString("fr-FR")}
                        </option>
                      ))}
                    </select>
                  )}
                </div>
                {report ? (
                  <ReportView
                    report={report}
                    currentVersion={meeting.version}
                    segments={meeting.segments || []}
                    seek={seek}
                  />
                ) : (
                  <div className={s.empty}>
                    <FileText size={36} />
                    <h2>{tr("Votre compte rendu se prépare ici")}</h2>
                    <p className={s.muted}>
                      {tr(
                        "Ajoutez un audio puis lancez l’analyse. Aucun résultat n’est inventé en attendant.",
                      )}
                    </p>
                  </div>
                )}
              </section>
            )}
          {currentTab === "transcript" && (
            <section ref={transcriptPanel} className={s.card}>
              <div className={s.row}>
                <h2>
                  Transcription{" "}
                  <span className={s.badge}>v{viewedTranscriptVersion}</span>
                </h2>
                {canEdit &&
                  meeting.version > 0 &&
                  !editing &&
                  !isHistoricalTranscript && (
                    <button
                      className={btn}
                      onClick={() => {
                        setSegments(structuredClone(meeting.segments || []));
                        setEditVersion(meeting.version);
                        setEditing(true);
                      }}
                    >
                      {tr("Corriger")}
                    </button>
                  )}
              </div>
              {meeting.version > 0 && (
                <label className={s.field}>
                  <span>{tr("Version de la transcription")}</span>
                  <select
                    className={s.select}
                    value={viewedTranscriptVersion}
                    onChange={(e) =>
                      setSelectedTranscriptVersion(
                        Number(e.target.value) === meeting.version
                          ? null
                          : Number(e.target.value),
                      )
                    }
                  >
                    <option value={meeting.version}>
                      v{meeting.version} · {tr("Courante")}
                    </option>
                    {(meeting.transcript_versions || [])
                      .filter((v) => v.version !== meeting.version)
                      .map((v) => (
                        <option value={v.version} key={v.version}>
                          v{v.version} · {tr("Historique")} ·{" "}
                          {new Date(v.created).toLocaleString("fr-FR")}
                        </option>
                      ))}
                  </select>
                </label>
              )}
              {isHistoricalTranscript && (
                <div className={s.notice}>
                  {tr(
                    "Version historique en lecture seule. Les corrections s’effectuent uniquement sur la transcription courante.",
                  )}
                </div>
              )}
              {isHistoricalTranscript &&
                historicalTranscript?.version !== viewedTranscriptVersion && (
                  <p className={s.muted}>
                    {tr("Chargement de la transcription historique…")}
                  </p>
                )}
              {editing && !isHistoricalTranscript ? (
                <>
                  {access.token && (
                    <label className={s.field}>
                      <span>{tr("Votre nom (éditeur invité)")}</span>
                      <input
                        required
                        minLength={2}
                        className={s.input}
                        value={editorName}
                        onChange={(e) => setEditorName(e.target.value)}
                      />
                    </label>
                  )}
                  <p className={s.muted}>
                    {tr(
                      "Les corrections créent une nouvelle version. Les anciennes analyses sont conservées.",
                    )}
                  </p>
                  {segments.map((seg, i) => (
                    <div key={seg.id} className={s.segment}>
                      <label className={s.field}>
                        <span>
                          {tr("Intervenant ·")}
                          {clock(seg.start)}
                        </span>
                        <input
                          aria-label={`Intervenant ${i + 1}`}
                          className={s.input}
                          value={seg.speaker || ""}
                          onChange={(e) =>
                            setSegments(
                              segments.map((v, j) =>
                                i === j ? { ...v, speaker: e.target.value } : v,
                              ),
                            )
                          }
                        />
                      </label>
                      <textarea
                        aria-label={`Passage ${i + 1}`}
                        className={s.textarea}
                        value={seg.text}
                        onChange={(e) =>
                          setSegments(
                            segments.map((v, j) =>
                              i === j ? { ...v, text: e.target.value } : v,
                            ),
                          )
                        }
                      />
                    </div>
                  ))}
                  <div className={s.actions}>
                    <button
                      className={primary}
                      disabled={
                        busy || (!!access.token && editorName.trim().length < 2)
                      }
                      onClick={async () => {
                        if (
                          await action("/transcript", "PUT", {
                            version: editVersion,
                            segments,
                            ...(access.token
                              ? { editor_name: editorName }
                              : {}),
                          })
                        )
                          setEditing(false);
                      }}
                    >
                      {tr("Enregistrer les corrections")}
                    </button>
                    <button className={btn} onClick={() => setEditing(false)}>
                      {tr("Annuler")}
                    </button>
                  </div>
                </>
              ) : (
                viewedSegments.map((seg) => (
                  <div
                    data-segment-start={seg.start}
                    className={`${s.segment} ${selectedStart === seg.start ? s.selectedSegment : ""}`}
                    key={seg.id}
                  >
                    <div className={s.actions}>
                      <button
                        className={s.time}
                        onClick={() => seek(seg.start, viewedTranscriptVersion)}
                      >
                        {clock(seg.start)} → {clock(seg.end)}
                      </button>
                      <strong>
                        {seg.speaker || tr("Intervenant non identifié")}
                      </strong>
                      {seg.language && <SegmentLanguage segment={seg} />}
                      {seg.uncertain && (
                        <span className={s.badge}>
                          {tr("Passage incertain")}
                        </span>
                      )}
                    </div>
                    <p>{seg.text}</p>
                  </div>
                ))
              )}
              {!meeting.segments?.length && !meeting.live_segments?.length && (
                <p className={s.muted}>
                  {tr("Les passages apparaîtront après transcription.")}
                </p>
              )}
            </section>
          )}
        </div>
        <aside className={s.sidebar}>
          <section className={`${s.card} ${s.audioPanel}`}>
            <div className={s.eyebrow}>{tr("SOURCE ORIGINALE")}</div>
            <h2>{tr("Audio de la réunion")}</h2>
            {canAudio && audioUrl ? (
              <>
                <audio
                  ref={audio}
                  className={s.audio}
                  src={audioUrl}
                  controls
                  preload="metadata"
                />
                <a
                  className={btn}
                  download={`${meeting.title}.${audioExtension}`}
                  href={audioUrl}
                >
                  <Download size={16} />
                  {tr("Télécharger")}
                </a>
              </>
            ) : (
              <p className={s.muted}>
                {canAudio
                  ? tr("L’audio sera disponible après sauvegarde.")
                  : tr("L’audio n’est pas inclus dans ce partage.")}
              </p>
            )}
            {chapters.length > 0 && (
              <nav
                className={s.chapters}
                aria-label={tr("Repères de la réunion")}
              >
                <h3>{tr("Repères de la réunion")}</h3>
                {chapters.map((chapter, i) => (
                  <button
                    key={i}
                    className={
                      selectedStart === chapter.start ? s.chapterActive : ""
                    }
                    onClick={() => seek(chapter.start, chapterReport?.version)}
                  >
                    <span>{clock(chapter.start)}</span>
                    <strong>{chapter.text}</strong>
                  </button>
                ))}
              </nav>
            )}
            <p className={s.sub}>
              <ShieldCheck size={16} />
              {tr(
                "Traitement IA local. Vérifiez les passages incertains et les décisions importantes.",
              )}
            </p>
            {!access.token && meeting.audio_available && (
              <div className={s.retranscribe}>
                <AudioLanguage
                  value={
                    retranscriptionLanguage ||
                    meeting.transcription_language ||
                    "auto"
                  }
                  onChange={setRetranscriptionLanguage}
                />
                <button
                  className={btn}
                  disabled={
                    busy ||
                    ["queued", "transcribing", "analyzing"].includes(
                      meeting.state,
                    )
                  }
                  onClick={async () => {
                    if (
                      window.confirm(
                        tr(
                          "Retranscrire l’audio crée une nouvelle version de transcription et relance l’analyse. Les corrections courantes ne seront plus la version active ; elles resteront consultables dans l’historique, comme les anciens rapports. Continuer ?",
                        ),
                      )
                    )
                      await action("/retranscribe", "POST", {
                        request_id: crypto.randomUUID(),
                        language:
                          retranscriptionLanguage ||
                          meeting.transcription_language ||
                          "auto",
                      });
                  }}
                >
                  <RefreshCw size={14} />
                  {tr("Retranscrire l’audio")}
                </button>
                <p className={s.muted}>
                  {tr(
                    "Choisissez la langue parlée et réécoutez les passages difficiles avant de relancer.",
                  )}
                </p>
              </div>
            )}
            {!access.token && (
              <>
                <hr
                  style={{
                    border: "none",
                    borderTop: "1px solid var(--line)",
                    margin: "25px 0",
                  }}
                />
                <button
                  className={`${btn} ${s.danger}`}
                  disabled={
                    busy ||
                    ["recording", "paused", "uploading", "saving"].includes(
                      captureState,
                    )
                  }
                  title={tr(
                    "Terminez l’enregistrement ou interrompez le transfert avant de supprimer la réunion.",
                  )}
                  onClick={async () => {
                    if (
                      window.confirm(
                        tr(
                          "Supprimer définitivement cette réunion et ses fichiers ?",
                        ),
                      )
                    ) {
                      if (await action("", "DELETE")) {
                        try {
                          const local = await pendingChunks(id);
                          await Promise.all(
                            local.map((chunk) => removeChunk(chunk.key)),
                          );
                        } catch {
                          setError(
                            tr(
                              "Réunion supprimée sur le serveur. Le stockage local du navigateur n’a pas pu être nettoyé ; effacez les données locales de cette application.",
                            ),
                          );
                          return;
                        }
                        router.push("/");
                      }
                    }
                  }}
                >
                  {tr("Supprimer définitivement")}
                </button>
              </>
            )}
          </section>
          {canChat && (
            <div
              id="meeting-chat-panel"
              className={`${s.chatPane} ${currentTab === "chat" ? s.showChat : ""}`}
            >
              <Chat
                key={meeting.version}
                history={meeting.chat || []}
                currentVersion={meeting.version}
                id={id}
                access={access}
                segments={meeting.segments || []}
                seek={seek}
              />
            </div>
          )}
        </aside>
      </div>
      {shareOpen && (
        <ShareDialog
          meeting={meeting}
          close={() => setShareOpen(false)}
          refresh={load}
        />
      )}
    </>
  );
}
function ReportView({
  currentVersion,
  report,
  segments,
  seek,
}: {
  report: Report;
  currentVersion: number;
  segments: Segment[];
  seek: (start: number, sourceVersion?: number) => void;
}) {
  const tr = useMemoraText();
  const data = report.data;
  const historical = report.version !== currentVersion;
  return (
    <>
      {historical && (
        <div className={s.notice}>
          {tr("Rapport historique — source")} v{report.version} ·{" "}
          {tr("Transcription actuelle")} v{currentVersion}.{" "}
          {tr(
            "Les repères audio sont conservés ; le texte affiché peut avoir été corrigé depuis cette analyse.",
          )}
        </div>
      )}
      <div className={s.notice}>
        {tr(
          "Vérifiez le compte rendu et les passages sources : la transcription automatique peut contenir des erreurs, même sans signal d’incertitude.",
        )}
      </div>
      <h3>{tr("Résumé")}</h3>
      <div style={{ whiteSpace: "pre-wrap" }}>
        {Array.isArray(data.summary)
          ? data.summary.map((item, i) => (
              <p key={i}>
                {item.text}
                <Citations
                  ids={item.sources || []}
                  historical={historical}
                  sourceVersion={report.version}
                  segments={segments}
                  seek={seek}
                />
              </p>
            ))
          : data.summary}
      </div>
      {(
        [
          [tr("Sujets abordés"), data.topics],
          [tr("Décisions"), data.decisions],
          [tr("Actions à suivre"), data.actions],
          [tr("Questions ouvertes"), data.open_questions],
        ] as [string, (Item | string)[]][]
      ).map(([title, items], sectionIndex) => (
        <section key={title}>
          <h3>{title}</h3>
          {items?.length ? (
            <ul>
              {items.map((item, i) => (
                <li key={i}>
                  {typeof item === "string" ? (
                    item
                  ) : (
                    <>
                      {item.text}
                      {sectionIndex === 2 && item.owner && (
                        <div className={s.muted}>
                          {tr("Responsable :")}
                          {item.owner}
                        </div>
                      )}
                      {sectionIndex === 2 && item.deadline && (
                        <div className={s.muted}>
                          {tr("Échéance :")}
                          {item.deadline}
                        </div>
                      )}
                      <Citations
                        ids={item.sources || []}
                        historical={historical}
                        sourceVersion={report.version}
                        segments={segments}
                        seek={seek}
                      />
                    </>
                  )}
                </li>
              ))}
            </ul>
          ) : (
            <p className={s.muted}>
              {tr("Aucun élément établi dans la transcription.")}
            </p>
          )}
        </section>
      ))}
      {data.limitations && (
        <div className={s.notice}>
          {Array.isArray(data.limitations)
            ? data.limitations.join(" · ")
            : data.limitations}
        </div>
      )}
    </>
  );
}
function Citations({
  sourceVersion,
  historical = false,
  ids,
  segments,
  seek,
}: {
  ids: string[];
  historical?: boolean;
  sourceVersion?: number;
  segments: Segment[];
  seek: (start: number, sourceVersion?: number) => void;
}) {
  return (
    <div className={s.actions}>
      {ids.map((id) => {
        const segment = segments.find((v) => v.id === id);
        return segment ? (
          <button
            className={s.time}
            key={id}
            onClick={() => seek(segment.start, sourceVersion)}
            title={
              historical ? "Repère audio — source historique" : segment.text
            }
          >
            {clock(segment.start)} · {segment.speaker || "Source"}
          </button>
        ) : null;
      })}
    </div>
  );
}
function Chat({
  currentVersion,
  history,
  id,
  access,
  segments,
  seek,
}: {
  currentVersion: number;
  history?: {
    version: number;
    question: string;
    answer: string;
    sources: string[];
  }[];
  id: string;
  access: Access;
  segments: Segment[];
  seek: (start: number, sourceVersion?: number) => void;
}) {
  const tr = useMemoraText();
  const [question, setQuestion] = useState(""),
    [messages, setMessages] = useState<
      {
        version: number;
        question: string;
        answer: string;
        sources: string[];
      }[]
    >(history || []),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  return (
    <section className={`${s.card} ${s.chat}`}>
      <div>
        <h2>{tr("Interrogez votre réunion")}</h2>
        <p className={s.muted}>
          {tr(
            "Des réponses fondées sur la transcription, avec accès aux passages sources.",
          )}
        </p>
      </div>
      {!messages.length && (
        <div className={s.chatEmpty}>
          <div className={s.chatSymbol}>
            <Sparkles size={21} />
          </div>
          <p>
            {tr(
              "Retrouvez une décision, une action ou le passage qui vous manque.",
            )}
          </p>
          <div className={s.chatExamples}>
            {[
              "Quelles décisions avons-nous prises ?",
              "Quelles actions restent à faire ?",
            ].map((prompt) => (
              <button
                type="button"
                key={prompt}
                onClick={() => setQuestion(tr(prompt))}
              >
                {tr(prompt)}{" "}
                <ArrowUpRight
                  size={11}
                  style={{ display: "inline", marginLeft: 5 }}
                />
              </button>
            ))}
          </div>
        </div>
      )}
      {messages.map((m, i) => (
        <div key={i}>
          <div className={`${s.bubble} ${s.question}`}>{m.question}</div>
          <div className={s.bubble}>
            <div className={s.badge}>
              v{m.version}
              {m.version !== currentVersion
                ? ` · ${tr("Ancienne source")}`
                : ""}
            </div>
            <p>{m.answer}</p>
            {m.version === currentVersion ? (
              <Citations ids={m.sources} segments={segments} seek={seek} />
            ) : (
              <p className={s.muted}>
                {tr(
                  "Réponse conservée dans son contexte original ; citations désactivées après correction de la transcription.",
                )}
              </p>
            )}
          </div>
        </div>
      ))}
      <ErrorBox error={error} />
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          if (!question.trim()) return;
          setBusy(true);
          setError("");
          try {
            const result = await api<{
              answer: string;
              version: number;
              sources?: string[];
              citations?: string[];
            }>(
              `meetings/${id}/chat`,
              { method: "POST", body: JSON.stringify({ question }) },
              access,
            );
            setMessages([
              ...messages,
              {
                question,
                version: result.version,
                answer: result.answer,
                sources: result.sources || result.citations || [],
              },
            ]);
            setQuestion("");
          } catch (e) {
            setError((e as Error).message);
          } finally {
            setBusy(false);
          }
        }}
      >
        <label className={s.field}>
          <span>{tr("Votre question")}</span>
          <textarea
            className={s.textarea}
            maxLength={2000}
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder={tr("Quelles décisions avons-nous prises ?")}
          />
        </label>
        <button disabled={busy || !question.trim()} className={primary}>
          <Send size={16} />
          {busy ? tr("Recherche dans la réunion…") : tr("Poser la question")}
        </button>
      </form>
    </section>
  );
}
function Recorder({
  meeting,
  refresh,
  onCaptureState,
}: {
  meeting: Meeting;
  refresh: () => Promise<void>;
  onCaptureState: (value: string) => void;
}) {
  const tr = useMemoraText();
  const { language } = useI18n();
  const [state, setState] = useState("idle"),
    [elapsed, setElapsed] = useState(0),
    [captureLanguage, setCaptureLanguage] = useState<string | null>(
      meeting.transcription_language || null,
    ),
    [selectedFile, setSelectedFile] = useState<{
      name: string;
      size: number;
    } | null>(null),
    [warning, setWarning] = useState(""),
    [error, setError] = useState(""),
    [saved, setSaved] = useState(0),
    [progress, setProgress] = useState(0),
    [pending, setPending] = useState(0),
    [chunkCount, setChunkCount] = useState(meeting.chunks?.length || 0);
  const changeState = useCallback(
    (value: string) => {
      setState(value);
      onCaptureState(value);
    },
    [onCaptureState],
  );
  const recorder = useRef<MediaRecorder | null>(null),
    stream = useRef<MediaStream | null>(null),
    seq = useRef(meeting.chunk_count || meeting.chunks?.length || 0),
    chain = useRef(Promise.resolve()),
    active = useRef(false),
    lastTick = useRef(0),
    fileInput = useRef<HTMLInputElement>(null),
    importController = useRef<AbortController | null>(null);
  const onDurationLimit = useEffectEvent(() =>
    setError(
      tr(
        "Durée maximale atteinte. Finalisez l’audio sauvegardé pour lancer l’analyse.",
      ),
    ),
  );
  useEffect(() => {
    const timer = setInterval(() => {
      if (active.current)
        setElapsed((v) => {
          const now = Date.now();
          const next =
            v + Math.max(1, Math.round((now - lastTick.current) / 1000));
          lastTick.current = now;
          const limit = (meeting.settings?.max_duration_minutes || 120) * 60;
          if (next >= limit - 60 && next < limit)
            queueMicrotask(() =>
              setWarning(
                "La limite de durée approche : moins d’une minute restante.",
              ),
            );
          if (next >= (meeting.settings?.max_duration_minutes || 120) * 60) {
            active.current = false;
            if (recorder.current && recorder.current.state !== "inactive")
              recorder.current.stop();
            queueMicrotask(() => {
              changeState("interrupted");
              onDurationLimit();
            });
          }
          return next;
        });
    }, 1000);
    return () => {
      clearInterval(timer);
      active.current = false;
      if (recorder.current && recorder.current.state !== "inactive")
        recorder.current.stop();
      stream.current?.getTracks().forEach((t) => t.stop());
    };
  }, [meeting.settings?.max_duration_minutes, changeState]);
  useEffect(() => {
    const visibility = () => {
      if (document.hidden && active.current)
        setWarning(
          "L’application est en arrière-plan. La veille, le verrouillage ou le navigateur peuvent interrompre le microphone ; vérifiez l’enregistrement au retour.",
        );
    };
    document.addEventListener("visibilitychange", visibility);
    return () => document.removeEventListener("visibilitychange", visibility);
  }, []);
  useEffect(() => {
    void pendingChunks(meeting.id).then((chunks) => {
      setPending(chunks.length);
      if (chunks.length) {
        seq.current = Math.max(seq.current, ...chunks.map((c) => c.seq + 1));
        setChunkCount(seq.current);
      }
    });
  }, [meeting.id]);
  useEffect(() => {
    function warn(e: BeforeUnloadEvent) {
      if (
        state === "recording" ||
        state === "paused" ||
        state === "uploading" ||
        pending
      ) {
        e.preventDefault();
        e.returnValue = "";
      }
    }
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [state, pending]);
  useEffect(() => () => importController.current?.abort(), []);
  async function sync(signal?: AbortSignal) {
    const chunks = await pendingChunks(meeting.id);
    setPending(chunks.length);
    for (const chunk of chunks) {
      await api(`meetings/${meeting.id}/chunks?seq=${chunk.seq}`, {
        method: "POST",
        headers: {
          "Content-Type": chunk.blob.type || "application/octet-stream",
        },
        body: chunk.blob,
        signal,
      });
      await removeChunk(chunk.key);
      setSaved((v) => v + 1);
      setPending((v) => Math.max(0, v - 1));
    }
  }
  function queue(blob: Blob) {
    const current = seq.current++;
    setChunkCount(seq.current);
    chain.current = chain.current
      .catch(() => {})
      .then(async () => {
        await saveChunk(meeting.id, current, blob);
        setPending((v) => v + 1);
        try {
          await sync();
        } catch (e) {
          setError(`Audio conservé sur cet appareil. ${(e as Error).message}`);
        }
      })
      .catch((e) => {
        setError(
          `Sauvegarde locale impossible : ${e.message}. Gardez cette page ouverte et vérifiez le stockage du navigateur.`,
        );
      });
  }
  async function start() {
    setError("");
    try {
      if (!navigator.mediaDevices?.getUserMedia)
        throw Error(
          tr(
            "Microphone indisponible. Utilisez HTTPS ou localhost, ou importez un fichier audio.",
          ),
        );
      if (seq.current > 0)
        throw Error(
          tr(
            "Un enregistrement existe déjà. Finalisez-le avant de créer une nouvelle réunion pour enregistrer à nouveau.",
          ),
        );
      try {
        stream.current = await navigator.mediaDevices.getUserMedia({
          audio: {
            channelCount: { ideal: 1 },
            sampleRate: { ideal: 48000 },
            echoCancellation: { ideal: true },
            noiseSuppression: { ideal: true },
            autoGainControl: { ideal: true },
          },
        });
      } catch (captureError) {
        if (
          captureError instanceof DOMException &&
          ["OverconstrainedError", "NotSupportedError"].includes(
            captureError.name,
          )
        )
          stream.current = await navigator.mediaDevices.getUserMedia({
            audio: true,
          });
        else throw captureError;
      }
      const type = ["audio/webm;codecs=opus", "audio/mp4", "audio/webm"].find(
        (v) => MediaRecorder.isTypeSupported(v),
      );
      const media = new MediaRecorder(stream.current, {
        audioBitsPerSecond: 128000,
        ...(type ? { mimeType: type } : {}),
      });
      recorder.current = media;
      for (const track of stream.current.getAudioTracks())
        track.onended = () => {
          active.current = false;
          if (media.state !== "inactive") media.stop();
          changeState("interrupted");
          setError(
            tr(
              "Le microphone a été déconnecté ou son autorisation retirée. Finalisez les fragments sauvegardés ; créez ensuite une autre réunion pour enregistrer à nouveau.",
            ),
          );
          void api(`meetings/${meeting.id}`, {
            method: "PATCH",
            body: JSON.stringify({ state: "interrupted" }),
          }).catch(() => {});
        };
      media.ondataavailable = (e) => {
        if (e.data.size)
          for (let offset = 0; offset < e.data.size; offset += 2 * 1024 * 1024)
            queue(e.data.slice(offset, offset + 2 * 1024 * 1024, e.data.type));
      };
      media.onerror = () => {
        setError(
          tr(
            "L’enregistrement a été interrompu. Les fragments sauvegardés peuvent être repris.",
          ),
        );
        changeState("interrupted");
        active.current = false;
      };
      media.onstop = () => {
        active.current = false;
        stream.current?.getTracks().forEach((t) => t.stop());
      };
      await api(`meetings/${meeting.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          state: "recording",
          mime_type: media.mimeType,
          transcription_language: captureLanguage || language,
        }),
      });
      media.start(10000);
      active.current = true;
      lastTick.current = Date.now();
      changeState("recording");
    } catch (e) {
      stream.current?.getTracks().forEach((t) => t.stop());
      setError((e as Error).message);
    }
  }
  async function finalize() {
    setError("");
    changeState("saving");
    try {
      if (recorder.current && recorder.current.state !== "inactive") {
        await new Promise<void>((resolve) => {
          recorder.current!.addEventListener("stop", () => resolve(), {
            once: true,
          });
          recorder.current!.stop();
        });
      }
      active.current = false;
      await chain.current;
      await sync();
      await api(`meetings/${meeting.id}/finalize`, {
        method: "POST",
        body: JSON.stringify({ expected_chunks: seq.current }),
      });
      changeState("done");
      await refresh();
    } catch (e) {
      setError((e as Error).message);
      changeState("interrupted");
    }
  }
  async function importFile(file: File) {
    setSelectedFile({ name: file.name, size: file.size });
    setError("");
    if (!/\.(mp3|wav|m4a|mp4|ogg|webm|flac|aac)$/i.test(file.name)) {
      setError(
        tr(
          "Format non pris en charge : MP3, WAV, M4A, MP4, OGG, WebM, FLAC ou AAC attendu.",
        ),
      );
      return;
    }
    importController.current?.abort();
    const controller = new AbortController();
    importController.current = controller;
    changeState("uploading");
    try {
      const settings =
        meeting.settings ||
        (await api<{
          max_upload_mb?: number;
        }>("settings"));
      if (file.size > (settings.max_upload_mb || 500) * 1024 * 1024)
        throw Error(tr("Ce fichier dépasse la limite d’import configurée."));
      const size = 2 * 1024 * 1024;
      await api(`meetings/${meeting.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          mime_type: file.type || "application/octet-stream",
          filename: file.name,
          transcription_language: captureLanguage || language,
        }),
        signal: controller.signal,
      });
      for (let offset = 0; offset < file.size; offset += size) {
        controller.signal.throwIfAborted();
        const index = offset / size;
        await saveChunk(
          meeting.id,
          index,
          file.slice(offset, offset + size, file.type),
        );
        setPending((v) => v + 1);
        await sync(controller.signal);
        controller.signal.throwIfAborted();
        seq.current = index + 1;
        setChunkCount(index + 1);
        setProgress(
          Math.round((Math.min(file.size, offset + size) / file.size) * 100),
        );
      }
      controller.signal.throwIfAborted();
      await finalize();
    } catch (e) {
      if (importController.current !== controller) return;
      setError(
        controller.signal.aborted
          ? tr(
              "Transfert interrompu. Les fragments sauvegardés sont conservés. Sélectionnez le même fichier pour reprendre et terminer l’import.",
            )
          : (e as Error).message,
      );
      changeState("interrupted");
    }
  }
  return (
    <section className={s.recorder}>
      <div className={s.eyebrow}>
        {meeting.mode === "import"
          ? tr("IMPORT AUDIO")
          : tr("ENREGISTREMENT AUDIO")}
      </div>
      <h2>
        {state === "recording"
          ? tr("Vous êtes à l’écoute.")
          : state === "paused"
            ? tr("Prenez votre temps.")
            : tr("Chaque échange compte.")}
      </h2>
      <p className={s.muted}>
        {tr(
          "Informez les participants. Le microphone est activé uniquement lorsque vous cliquez sur Enregistrer. Durée maximale :",
        )}{" "}
        {meeting.settings?.max_duration_minutes || 120}
        {tr("min ; import :")} {meeting.settings?.max_upload_mb || 250}
        {tr("Mo.")}
      </p>
      {["idle", "interrupted"].includes(state) && (
        <div style={{ maxWidth: 330, margin: "20px auto", textAlign: "left" }}>
          <AudioLanguage
            value={captureLanguage || language}
            onChange={setCaptureLanguage}
          />
        </div>
      )}
      {meeting.mode === "import" && (
        <p className={s.muted}>
          {tr(
            "Formats proposés : MP3, WAV, M4A, MP4, OGG, WebM, FLAC et AAC. Le contenu réel est vérifié avant traitement.",
          )}
        </p>
      )}
      <ErrorBox error={error} />
      {warning && (
        <div className={s.notice} role="status">
          {tr(warning)}
        </div>
      )}
      {meeting.mode !== "import" && (
        <p className={s.muted}>
          {tr(
            "La veille, le verrouillage ou le changement d’onglet peuvent suspendre l’enregistrement selon le navigateur. Gardez cette page active et vérifiez les fragments sauvegardés.",
          )}
        </p>
      )}
      {meeting.mode !== "import" && (
        <div className={s.timer}>
          {state === "recording" && <span className={s.pulse} />}{" "}
          {clock(elapsed)}
        </div>
      )}
      {meeting.mode === "import" && (selectedFile || meeting.filename) && (
        <div className={s.notice} style={{ overflowWrap: "anywhere" }}>
          <strong>{tr("Fichier sélectionné")}</strong>
          <p>{selectedFile?.name || meeting.filename}</p>
          {selectedFile && (
            <p>
              {(selectedFile.size / (1024 * 1024)).toLocaleString(undefined, {
                maximumFractionDigits: 2,
              })}{" "}
              {tr("Mo")}
            </p>
          )}
        </div>
      )}
      {state === "uploading" && (
        <>
          <progress className={s.progress} max={100} value={progress} />
          <p>
            {progress}
            {tr("% importés")}
          </p>
        </>
      )}
      <div
        className={s.actions}
        style={{ justifyContent: "center", marginTop: 20 }}
      >
        {["idle", "interrupted"].includes(state) &&
          meeting.mode !== "import" &&
          chunkCount === 0 && (
            <button className={primary} onClick={() => void start()}>
              <Mic size={18} />
              {tr("Enregistrer")}
            </button>
          )}
        {state === "uploading" && (
          <button
            className={btn}
            onClick={() => {
              importController.current?.abort();
            }}
          >
            {tr("Interrompre le transfert")}
          </button>
        )}
        {state === "recording" && (
          <button
            className={btn}
            onClick={() => {
              recorder.current?.pause();
              active.current = false;
              changeState("paused");
              void api(`meetings/${meeting.id}`, {
                method: "PATCH",
                body: JSON.stringify({ state: "paused" }),
              }).catch(() => {});
            }}
          >
            <Pause size={18} />
            Pause
          </button>
        )}
        {state === "paused" && (
          <button
            className={primary}
            onClick={() => {
              recorder.current?.resume();
              active.current = true;
              lastTick.current = Date.now();
              changeState("recording");
              void api(`meetings/${meeting.id}`, {
                method: "PATCH",
                body: JSON.stringify({ state: "recording" }),
              }).catch(() => {});
            }}
          >
            <Play size={18} />
            {tr("Reprendre")}
          </button>
        )}
        {meeting.mode !== "import" &&
          ["recording", "paused", "interrupted"].includes(state) && (
            <button className={primary} onClick={() => void finalize()}>
              <Square size={16} />
              {tr("Terminer et analyser")}
            </button>
          )}
        {["idle", "interrupted"].includes(state) &&
          meeting.mode === "import" && (
            <button
              className={primary}
              onClick={() => fileInput.current?.click()}
            >
              <Upload size={18} />
              {chunkCount > 0
                ? tr("Reprendre avec le même fichier")
                : tr("Choisir un fichier audio")}
            </button>
          )}
        {(pending > 0 || (state === "idle" && chunkCount > 0)) && (
          <>
            <button
              className={btn}
              onClick={() =>
                void sync()
                  .then(() => setError(""))
                  .catch((e) => setError(e.message))
              }
            >
              <RefreshCw size={16} />
              {tr("Reprendre la sauvegarde")}
            </button>
            {meeting.mode !== "import" && (
              <button className={primary} onClick={() => void finalize()}>
                {tr("Finaliser l’audio sauvegardé")}
              </button>
            )}
          </>
        )}
      </div>
      <input
        ref={fileInput}
        hidden
        type="file"
        accept="audio/*,.mp4,.m4a,.webm,.flac"
        onChange={(e) => {
          const f = e.target.files?.[0];
          e.target.value = "";
          if (f) void importFile(f);
        }}
      />
      <p className={s.sub}>
        {state === "saving"
          ? tr("Sauvegarde et préparation de l’analyse…")
          : `${saved} fragments confirmés · ${pending} en attente locale`}
      </p>
      {meeting.live_segments?.length ? (
        <div className={s.card} style={{ textAlign: "left", marginTop: 20 }}>
          <h3>
            {tr("Transcription en direct")} · {tr("Provisoire")}
          </h3>
          <p className={s.muted}>
            {tr(
              "Ces passages provisoires seront remplacés par la transcription finale après l’arrêt.",
            )}
          </p>
          {meeting.live_segments.slice(-4).map((segment) => (
            <p key={segment.id}>
              <span className={s.muted}>{clock(segment.start)} </span>
              {segment.text}
            </p>
          ))}
        </div>
      ) : (
        state === "recording" && (
          <p className={s.muted}>
            {tr(
              "La transcription apparaîtra progressivement après traitement des fragments.",
            )}
          </p>
        )
      )}
    </section>
  );
}
function ShareDialog({
  meeting,
  close,
  refresh,
}: {
  meeting: Meeting;
  close: () => void;
  refresh: () => Promise<void>;
}) {
  const tr = useMemoraText();
  const currentReport =
    (meeting.reports || []).find((r) => r.id === meeting.report_id) ||
    meeting.reports?.[0];
  const originalSummary = currentReport
    ? Array.isArray(currentReport.data.summary)
      ? currentReport.data.summary.map((i) => i.text).join("\n")
      : currentReport.data.summary
    : "";
  const [summary, setSummary] = useState(originalSummary.slice(0, 2000));
  const [sendPassword, setSendPassword] = useState(false);
  const [password, setPassword] = useState(""),
    [days, setDays] = useState(7),
    [hasExpiration, setHasExpiration] = useState(true),
    [permissions, setPermissions] = useState({
      report: true,
      transcript: true,
      audio: true,
      chat: true,
      edit: false,
    }),
    [shares, setShares] = useState<Share[]>(meeting.shares || []),
    [selected, setSelected] = useState<Share | null>(null),
    [emails, setEmails] = useState(""),
    [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [busy, setBusy] = useState(false);
  useEffect(() => {
    void api<Share[]>(`meetings/${meeting.id}/shares`)
      .then(setShares)
      .catch((e) => setError(e.message));
  }, [meeting.id]);
  const link = selected
    ? `${window.location.origin}/partage/${selected.token}`
    : "";
  return (
    <Modal title={tr("Partager cette réunion")} close={close}>
      <p className={s.muted}>
        {tr(
          "Toute personne disposant du lien et, s’il est défini, du mot de passe peut accéder aux contenus autorisés. Les adresses email ne constituent pas une liste de contrôle d’accès.",
        )}
      </p>
      <ErrorBox error={error} />
      {notice && <div className={s.notice}>{notice}</div>}
      <label className={s.field}>
        <span>{tr("Mot de passe (facultatif)")}</span>
        <input
          type="password"
          autoComplete="new-password"
          minLength={8}
          className={s.input}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder={tr("Au moins 8 caractères")}
        />
      </label>
      <label className={s.check}>
        <input
          type="checkbox"
          checked={hasExpiration}
          onChange={(e) => setHasExpiration(e.target.checked)}
        />
        {tr("Définir une expiration")}
      </label>
      {!hasExpiration && (
        <p className={s.muted}>
          {tr(
            "Ce lien restera actif jusqu’à sa révocation ou la suppression de la réunion.",
          )}
        </p>
      )}
      <label className={s.field}>
        <span>{tr("Expiration dans (jours)")}</span>
        <input
          type="number"
          min={1}
          max={365}
          className={s.input}
          disabled={!hasExpiration}
          value={days}
          onChange={(e) => setDays(Number(e.target.value))}
        />
      </label>
      <div className={s.field}>
        <span>{tr("Contenus et droits invités")}</span>
        {Object.entries({
          report: tr("Consulter le rapport"),
          transcript: tr("Consulter la transcription"),
          audio: tr("Écouter / télécharger l’audio"),
          chat: tr("Interroger le chat IA"),
          edit: tr("Corriger la transcription"),
        }).map(([key, label]) => (
          <label className={s.check} key={key}>
            <input
              type="checkbox"
              checked={permissions[key as keyof typeof permissions]}
              onChange={(e) =>
                setPermissions({ ...permissions, [key]: e.target.checked })
              }
            />
            {label}
          </label>
        ))}
      </div>
      <button
        className={primary}
        disabled={busy}
        onClick={async () => {
          setBusy(true);
          setError("");
          try {
            const share = await api<Share>(`meetings/${meeting.id}/shares`, {
              method: "POST",
              body: JSON.stringify({
                password: password || null,
                expires_at: hasExpiration
                  ? Date.now() / 1000 + days * 86400
                  : null,
                permissions,
              }),
            });
            setShares([...shares, share]);
            setSelected(share);
            await refresh();
          } catch (e) {
            setError((e as Error).message);
          } finally {
            setBusy(false);
          }
        }}
      >
        <Share2 size={16} />
        {tr("Créer le lien")}
      </button>
      {selected && (
        <>
          <label className={s.field}>
            <span>{tr("Lien de partage")}</span>
            <input className={s.input} readOnly value={link} />
          </label>
          <button
            className={btn}
            onClick={() =>
              void navigator.clipboard
                .writeText(link)
                .then(() =>
                  setNotice(
                    tr("Lien copié. Transmettez le mot de passe séparément."),
                  ),
                )
                .catch(() =>
                  setError(
                    tr(
                      "Copie impossible. Sélectionnez et copiez le lien manuellement.",
                    ),
                  ),
                )
            }
          >
            {tr("Copier le lien")}
          </button>
          <label className={s.field}>
            <span>{tr("Destinataires email (séparés par virgules)")}</span>
            <input
              className={s.input}
              value={emails}
              onChange={(e) => setEmails(e.target.value)}
              placeholder="equipe@example.test, direction@example.test"
            />
          </label>
          {selected.permissions?.report && (
            <label className={s.field}>
              <span>
                {tr("Résumé inclus dans l’email (aperçu modifiable)")}
              </span>
              <textarea
                className={s.textarea}
                maxLength={2000}
                value={summary}
                onChange={(e) => setSummary(e.target.value)}
              />
            </label>
          )}
          {selected.password_protected && (
            <>
              <label className={s.check}>
                <input
                  type="checkbox"
                  checked={sendPassword}
                  onChange={(e) => setSendPassword(e.target.checked)}
                />
                {tr("Inclure le mot de passe dans le même email")}
              </label>
              <p className={s.muted}>
                {tr(
                  "Le destinataire pourra retransmettre le lien et le mot de passe. Vous pouvez aussi transmettre le mot de passe séparément.",
                )}
              </p>
              {sendPassword && (
                <label className={s.field}>
                  <span>{tr("Mot de passe du lien sélectionné")}</span>
                  <input
                    className={s.input}
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    autoComplete="new-password"
                  />
                </label>
              )}
            </>
          )}
          <button
            className={btn}
            disabled={busy || !emails.trim() || (sendPassword && !password)}
            onClick={async () => {
              setBusy(true);
              try {
                await api(
                  `meetings/${meeting.id}/shares/${selected.token}/invite`,
                  {
                    method: "POST",
                    body: JSON.stringify({
                      emails: emails.split(/[,;\s]+/).filter(Boolean),
                      summary: selected.permissions?.report ? summary : "",
                      ...(sendPassword ? { password } : {}),
                    }),
                  },
                );
                setNotice(
                  tr(
                    "Invitation mise en file. Consultez le suivi des emails pour confirmer la remise au serveur local de capture.",
                  ),
                );
              } catch (e) {
                setError((e as Error).message);
              } finally {
                setBusy(false);
              }
            }}
          >
            <Send size={16} />
            {tr("Envoyer le résumé et le lien")}
          </button>
        </>
      )}
      {shares.length > 0 && (
        <div style={{ marginTop: 25 }}>
          <h3>{tr("Liens existants")}</h3>
          {shares.map((share) => (
            <div className={s.segment} key={share.token}>
              <div className={s.row}>
                <span className={s.muted}>
                  {share.password_protected ? tr("Protégé") : tr("Ouvert")} ·{" "}
                  {share.revoked
                    ? tr("Révoqué")
                    : share.expires_at
                      ? new Date(share.expires_at).toLocaleDateString("fr-FR")
                      : tr("Sans expiration")}
                </span>
                {!share.revoked && (
                  <div className={s.actions}>
                    <button className={btn} onClick={() => setSelected(share)}>
                      {tr("Sélectionner")}
                    </button>
                    <button
                      className={`${btn} ${s.danger}`}
                      onClick={async () => {
                        try {
                          await api(
                            `meetings/${meeting.id}/shares/${share.token}`,
                            { method: "DELETE" },
                          );
                          setShares(
                            shares.map((v) =>
                              v.token === share.token
                                ? { ...v, revoked: true }
                                : v,
                            ),
                          );
                          if (selected?.token === share.token)
                            setSelected(null);
                          await refresh();
                        } catch (e) {
                          setError((e as Error).message);
                        }
                      }}
                    >
                      {tr("Révoquer")}
                    </button>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </Modal>
  );
}
export function SharedPage({ token }: { token: string }) {
  const tr = useMemoraText();
  const [password, setPassword] = useState(""),
    [access, setAccess] = useState<Access | null>(null),
    [meeting, setMeeting] = useState<Meeting | null>(null),
    [error, setError] = useState(""),
    [loading, setLoading] = useState(true);
  const open = useCallback(
    async (pass: string) => {
      setLoading(true);
      try {
        const data = await api<
          | Meeting
          | {
              meeting: Meeting;
              permissions: Record<string, boolean>;
            }
        >(`share/${token}`, {}, { password: pass });
        setMeeting(
          "meeting" in data
            ? { ...data.meeting, permissions: data.permissions }
            : data,
        );
        setAccess({ token, password: pass });
        setError("");
      } catch (e) {
        setError((e as Error).message);
      } finally {
        setLoading(false);
      }
    },
    [token],
  );
  useEffect(() => {
    queueMicrotask(() => void open(""));
  }, [open]);
  if (meeting && access)
    return <MeetingPage id={meeting.id} access={access} initial={meeting} />;
  return (
    <main className={s.app}>
      <div className={`${s.card} ${s.login}`}>
        <ShieldCheck size={40} />
        <h1>{tr("Réunion partagée")}</h1>
        {loading ? (
          <p>{tr("Vérification du lien…")}</p>
        ) : (
          <>
            <ErrorBox error={error} />
            <p className={s.muted}>
              {tr(
                "Si ce lien est protégé, saisissez le mot de passe transmis par l’organisateur. Un lien expiré ou révoqué ne permet plus l’accès.",
              )}
            </p>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                void open(password);
              }}
            >
              <label className={s.field}>
                <span>{tr("Mot de passe du partage")}</span>
                <input
                  type="password"
                  className={s.input}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete="current-password"
                />
              </label>
              <button className={primary}>{tr("Accéder à la réunion")}</button>
            </form>
          </>
        )}
      </div>
    </main>
  );
}
export function SettingsPage() {
  return (
    <main className={s.app}>
      <AuthGate>
        <SettingsContent />
      </AuthGate>
    </main>
  );
}
function SettingsContent() {
  const tr = useMemoraText();
  const [settings, setSettings] = useState<Record<string, unknown> | null>(
      null,
    ),
    [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [busy, setBusy] = useState(false);
  useEffect(() => {
    void api<Record<string, unknown>>("settings")
      .then(setSettings)
      .catch((e) => setError(e.message));
  }, []);
  const fields: Record<
    string,
    {
      label: string;
      min: number;
      max: number;
    }
  > = {
    max_duration_minutes: {
      label: tr("Durée maximale d’une réunion (minutes)"),
      min: 1,
      max: 240,
    },
    max_upload_mb: {
      label: tr("Taille maximale d’import (Mo)"),
      min: 1,
      max: 500,
    },
    audio_retention_days: {
      label: tr("Conservation des fichiers audio (jours)"),
      min: 1,
      max: 365,
    },
  };
  return (
    <>
      <div className={s.top}>
        <div>
          <div className={s.eyebrow}>{tr("VOTRE ESPACE")}</div>
          <h1>{tr("Paramètres de l’application")}</h1>
          <p className={s.sub}>
            {tr("Des limites explicites, adaptées aux ressources disponibles.")}
          </p>
        </div>
      </div>
      <Navigation />
      <ErrorBox error={error} />
      {notice && <div className={s.notice}>{notice}</div>}
      {settings && (
        <form
          className={s.card}
          style={{ maxWidth: 760 }}
          onSubmit={async (e) => {
            e.preventDefault();
            setBusy(true);
            setError("");
            try {
              const updated = await api<Record<string, unknown>>("settings", {
                method: "PUT",
                body: JSON.stringify(settings),
              });
              setSettings({
                ...updated,
                can_administer: settings.can_administer,
              });
              setNotice(tr("Paramètres sauvegardés."));
            } catch (e) {
              setError((e as Error).message);
            } finally {
              setBusy(false);
            }
          }}
        >
          <h2>{tr("Enregistrement et conservation")}</h2>
          <div className={s.notice}>
            {tr(
              "Ces paramètres s’appliquent aux nouvelles réunions. Les réunions existantes conservent leurs limites et échéances de rétention initiales ; aucune purge rétroactive n’est lancée ici.",
            )}
          </div>
          <p className={s.muted}>
            {tr(
              "La modification est soumise aux droits administratifs contrôlés par le serveur.",
            )}
          </p>
          {Object.entries(fields).map(([key, f]) => (
            <label key={key} className={s.field}>
              <span>{f.label}</span>
              <input
                className={s.input}
                type="number"
                required
                min={f.min}
                max={f.max}
                value={Number(
                  settings[key] ??
                    (key === "max_duration_minutes"
                      ? 120
                      : key === "max_upload_mb"
                        ? 500
                        : 30),
                )}
                onChange={(e) =>
                  setSettings({ ...settings, [key]: Number(e.target.value) })
                }
              />
            </label>
          ))}
          <label className={s.check}>
            <input
              type="checkbox"
              checked={Boolean(settings.allow_guest_edit)}
              onChange={(e) =>
                setSettings({ ...settings, allow_guest_edit: e.target.checked })
              }
            />
            {tr(
              "Autoriser l’organisateur à accorder la correction aux invités",
            )}
          </label>
          <p className={s.sub}>
            {tr(
              "Les droits de chaque lien restent configurables lors du partage. L’archivage conserve la réunion ; la suppression retire ses données et révoque ses accès.",
            )}
          </p>
          <label className={s.field}>
            <span>{tr("Langue des rapports")}</span>
            <select
              className={s.select}
              value={String(settings.report_language || "fr")}
              onChange={(e) =>
                setSettings({ ...settings, report_language: e.target.value })
              }
            >
              <option value="fr">{tr("Français")}</option>
              <option value="en">English</option>
            </select>
          </label>
          <label className={s.check}>
            <input
              type="checkbox"
              checked={Boolean(settings.email_notifications)}
              onChange={(e) =>
                setSettings({
                  ...settings,
                  email_notifications: e.target.checked,
                })
              }
            />
            {tr("Notification email à la disponibilité du rapport")}
          </label>
          <button
            className={primary}
            disabled={busy || settings.can_administer === false}
            style={{ marginTop: 20 }}
          >
            <Check size={16} />
            {busy ? tr("Sauvegarde…") : tr("Enregistrer les paramètres")}
          </button>
        </form>
      )}
    </>
  );
}
function MailStatus() {
  const tr = useMemoraText();
  const [messages, setMessages] = useState<
      {
        id: string;
        recipient: string;
        subject: string;
        state: string;
        error?: string;
      }[]
    >([]),
    [error, setError] = useState("");
  const load = useCallback(
    () =>
      api<typeof messages>("mail")
        .then(setMessages)
        .catch((e) => setError(e.message)),
    [],
  );
  useEffect(() => {
    void load();
    const timer = setInterval(() => void load(), 4000);
    return () => clearInterval(timer);
  }, [load]);
  return (
    <>
      <p className={s.muted}>
        {tr(
          "En environnement local, les messages sont capturés sans envoi externe. « Remis » confirme la réception SMTP de capture, sans preuve de délivrabilité en production.",
        )}
      </p>
      <p className={s.sub}>
        <a
          className={s.link}
          href="http://127.0.0.1:8025"
          target="_blank"
          rel="noreferrer"
        >
          {tr("Ouvrir la boîte de capture locale ↗")}
        </a>
      </p>
      <ErrorBox error={error} />
      {!messages.length ? (
        <p className={s.sub}>{tr("Aucun email demandé.")}</p>
      ) : (
        messages.map((message) => (
          <div className={s.segment} key={message.id}>
            <strong>{message.subject}</strong>
            <p>{message.recipient}</p>
            <span className={s.badge}>
              {{
                sent: tr("Remis au serveur"),
                queued: tr("En attente"),
                sending: tr("En cours"),
                failed: tr("Échec"),
              }[message.state] || message.state}
            </span>
            {message.error && <p className={s.error}>{message.error}</p>}
            {message.state === "failed" && (
              <button
                className={btn}
                onClick={() =>
                  void api(`mail/${encodeURIComponent(message.id)}/retry`, {
                    method: "POST",
                  })
                    .then(load)
                    .catch((e) => setError(e.message))
                }
              >
                {tr("Réessayer")}
              </button>
            )}
          </div>
        ))
      )}
    </>
  );
}

function AudioLanguage({
  value,
  onChange,
}: {
  value: string;
  onChange: (value: string) => void;
}) {
  const tr = useMemoraText();
  const fieldId = useId();
  return (
    <div className={s.field}>
      <label htmlFor={fieldId} className={s.fieldLabel}>
        {tr("Langue de l’audio")}
      </label>
      <select
        id={fieldId}
        aria-describedby={`${fieldId}-help`}
        className={s.select}
        value={value}
        onChange={(e) => onChange(e.target.value)}
      >
        <option value="auto">{tr("Automatique · français / anglais")}</option>
        <option value="fr">{tr("Français")}</option>
        <option value="en">English</option>
      </select>
      <small id={`${fieldId}-help`} className={`${s.muted} ${s.languageHelp}`}>
        {tr(
          "Choisissez Français ou English pour un audio monolingue, Automatique pour une alternance de langues.",
        )}
      </small>
    </div>
  );
}

function SegmentLanguage({ segment }: { segment: Segment }) {
  const tr = useMemoraText();
  const { label, hint } = describeSegmentLanguage(segment, tr);
  return (
    <span className={s.badge} title={hint}>
      {label}
    </span>
  );
}
