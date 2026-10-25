export type Segment = {
  id: string;
  start: number;
  end: number;
  text: string;
  speaker: string;
  speaker_id?: string | null;
  speaker_confidence?: number | null;
  speaker_uncertain?: boolean;
  speaker_provenance?: Record<string, unknown>;
  language?: string;
  language_scope?:
    | "initial_window_detection"
    | "speech_region_detection"
    | "forced";
  language_confidence?: number | null;
  uncertain?: boolean;
};
export type Item = {
  text: string;
  sources?: string[];
  owner?: string | null;
  deadline?: string | null;
};
export type Report = {
  id: string;
  revision?: number;
  version: number;
  created: string;
  human_reviews?: HumanReview[];
  reviews_stale?: boolean;
  data: {
    summary: string | Item[];
    topics: (Item | string)[];
    decisions: (Item | string)[];
    actions: (Item | string)[];
    open_questions: (Item | string)[];
    limitations?: string[] | string;
  };
};
export type HumanReview = {
  id: string;
  report: string;
  category: "actions" | "decisions";
  item_index: number;
  revision: number;
  transcript_version: number;
  author: string;
  editor_name: string | null;
  created: string;
  status: "proposed" | "confirmed" | "cancelled" | "needs_review";
  corrections: { text?: string; owner?: string; deadline?: string };
  provenance: "human_review";
};
export type Share = {
  token: string;
  expires_at?: string;
  revoked?: boolean;
  permissions?: Record<string, boolean>;
  password_protected?: boolean;
};
export type Meeting = {
  id: string;
  title: string;
  mode: string;
  meeting_date?: string | null;
  transcription_language?: "auto" | "fr" | "en";
  state: string;
  created: string;
  version: number;
  report_version?: number;
  report_id?: string;
  transcript_versions?: { version: number; author: string; created: string }[];
  chat?: {
    question: string;
    answer: string;
    sources: string[];
    version: number;
  }[];
  segments: Segment[];
  live_segments?: Segment[];
  reports: Report[];
  jobs?: { state: string; error?: string }[];
  shares?: Share[];
  audio_available?: boolean;
  duration?: number;
  archived?: boolean;
  diarization?: {
    engine?: string;
    speaker_count?: number;
    warnings?: string[];
    overlap_supported?: boolean;
  };
  automatic_diarization?: { state?: string; source_version?: number };
  error?: string;
  permissions?: Record<string, boolean>;
  chunks?: { seq: number; bytes: number }[];
  chunk_count?: number;
  mime_type?: string;
  filename?: string;
  settings?: { max_duration_minutes: number; max_upload_mb: number };
};
export type Access = { token?: string; password?: string };
function normalize(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(normalize);
  if (value && typeof value === "object") {
    const item = value as Record<string, unknown>,
      result: Record<string, unknown> = {};
    for (const [key, v] of Object.entries(item))
      result[key] =
        ["created", "expires_at"].includes(key) && typeof v === "number"
          ? new Date(v * 1000).toISOString()
          : normalize(v);
    if (
      typeof item.id === "string" &&
      "permissions" in item &&
      !("title" in item)
    ) {
      result.token = item.id;
      result.password_protected = item.protected;
    }
    return result;
  }
  return value;
}
export function accessHeaders(access: Access = {}) {
  let guestSession = "";
  if (access.token && typeof window !== "undefined") {
    try {
      guestSession =
        sessionStorage.getItem("memora-guest-session") || crypto.randomUUID();
      sessionStorage.setItem("memora-guest-session", guestSession);
    } catch {
      /* Private browsing may disable persistence; backend still checks share rights. */
    }
  }
  return {
    ...(guestSession ? { "X-Guest-Session": guestSession } : {}),
    ...(access.token ? { "X-Share-Token": access.token } : {}),
    ...(access.password ? { "X-Share-Password": access.password } : {}),
  };
}
export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}
export async function api<T>(
  path: string,
  init: RequestInit = {},
  access: Access = {},
): Promise<T> {
  const response = await fetch(`/mapi/${path}`, {
    ...init,
    headers: {
      ...(typeof init.body === "string"
        ? { "Content-Type": "application/json" }
        : {}),
      ...accessHeaders(access),
      ...init.headers,
    },
    cache: "no-store",
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new ApiError(
      response.status,
      typeof body.detail === "string"
        ? body.detail
        : body.message || `Demande refusée (${response.status})`,
    );
  }
  if (response.status === 204) return null as T;
  const result = await response.json();
  return normalize(result.data === undefined ? result : result.data) as T;
}
export function clock(seconds: number = 0) {
  return `${Math.floor(seconds / 60)
    .toString()
    .padStart(2, "0")}:${Math.floor(seconds % 60)
    .toString()
    .padStart(2, "0")}`;
}
export const labels: Record<string, string> = {
  draft: "Brouillon",
  recording: "Enregistrement",
  paused: "En pause",
  interrupted: "Interrompue",
  queued: "En attente",
  transcribing: "Transcription",
  analyzing: "Analyse en cours",
  ready: "Terminée",
  failed: "À reprendre",
};
