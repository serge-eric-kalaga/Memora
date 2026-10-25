"use client";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import Link from "next/link";
import {
  useSession,
  sessionChannel,
  sessionSource,
} from "@/features/auth/hooks";
import { CaptureRuntime } from "./capture-runtime";
import type { Meeting } from "./api";
import { useI18n } from "@/lib/i18n/use-i18n";
import theme from "./workspace-frame.module.css";
import styles from "./capture-session.module.css";

type Page = {
  meeting: Meeting;
  target: HTMLElement;
  refresh: () => Promise<void>;
  onCaptureState: (state: string) => void;
};
type Session = { owner: string; meeting: Meeting };
type Registry = {
  register: (page: Page) => () => void;
  update: (page: Page) => void;
  meetingId?: string;
};
const Context = createContext<Registry | null>(null);
const busy = (state: string) =>
  [
    "starting",
    "recording",
    "paused",
    "saving",
    "uploading",
    "interrupted",
  ].includes(state);

export function CaptureProvider({ children }: { children: ReactNode }) {
  const auth = useSession();
  const owner = auth.data?.username;
  const sessionRef = useRef<Session | null>(null);
  const pageRef = useRef<Page | null>(null);
  const stateRef = useRef("idle");
  const [session, setSession] = useState<Session | null>(null);
  const [target, setTarget] = useState<HTMLElement | null>(null);
  const [state, setState] = useState("idle");
  const changeState = useCallback((value: string) => {
    stateRef.current = value;
    setState(value);
    if (pageRef.current?.meeting.id === sessionRef.current?.meeting.id)
      pageRef.current?.onCaptureState(value);
  }, []);
  const refresh = useCallback(async () => {
    if (pageRef.current?.meeting.id === sessionRef.current?.meeting.id)
      await pageRef.current?.refresh();
  }, []);
  const update = useCallback((page: Page) => {
    if (pageRef.current?.target !== page.target) return;
    pageRef.current = page;
    if (
      sessionRef.current?.meeting.id === page.meeting.id &&
      sessionRef.current.meeting !== page.meeting
    ) {
      sessionRef.current = { ...sessionRef.current, meeting: page.meeting };
      setSession(sessionRef.current);
    }
  }, []);
  const register = useCallback(
    (page: Page) => {
      pageRef.current = page;
      const current = sessionRef.current;
      if (
        owner &&
        (!current ||
          current.owner !== owner ||
          (current.meeting.id !== page.meeting.id && !busy(stateRef.current)))
      ) {
        const next = { owner: owner, meeting: page.meeting };
        sessionRef.current = next;
        stateRef.current = "idle";
        setState("idle");
        setSession(next);
      }
      const same = sessionRef.current?.meeting.id === page.meeting.id;
      setTarget(same ? page.target : null);
      page.onCaptureState(same ? stateRef.current : "idle");
      return () => {
        if (pageRef.current?.target === page.target) {
          pageRef.current = null;
          setTarget(null);
        }
      };
    },
    [owner],
  );
  useEffect(() => {
    if (!owner || sessionRef.current?.owner !== owner) {
      sessionRef.current = null;
      stateRef.current = "idle";
      queueMicrotask(() => {
        setSession(null);
        setTarget(null);
        setState("idle");
      });
    }
  }, [owner]);
  useEffect(() => {
    const reset = () => {
      sessionRef.current = null;
      stateRef.current = "idle";
      setSession(null);
      setTarget(null);
      setState("idle");
    };
    const accountChanged = (event: MessageEvent) => {
      if (
        event.data?.source !== sessionSource &&
        event.data?.kind !== "profile"
      )
        reset();
    };
    const channel =
      typeof BroadcastChannel !== "undefined"
        ? new BroadcastChannel(sessionChannel)
        : null;
    channel?.addEventListener("message", accountChanged);
    window.addEventListener("session-expired", reset);
    return () => {
      channel?.close();
      window.removeEventListener("session-expired", reset);
    };
  }, []);
  const visible = session && session.owner === owner;
  return (
    <Context.Provider
      value={{
        register,
        update,
        meetingId: visible ? session.meeting.id : undefined,
      }}
    >
      {children}
      {visible && !target && busy(state) && (
        <div className={styles.spacing} aria-hidden="true" />
      )}
      {visible && (
        <div className={theme.theme} style={{ display: "contents" }}>
          <CaptureRuntime
            key={`${session.owner}:${session.meeting.id}`}
            meeting={session.meeting}
            target={target}
            refresh={refresh}
            onCaptureState={changeState}
          />
        </div>
      )}
    </Context.Provider>
  );
}

export function CaptureSlot(props: Omit<Page, "target">) {
  const context = useContext(Context);
  const { language } = useI18n();
  const anchor = useRef<HTMLDivElement>(null);
  const latest = useRef(props);
  useEffect(() => {
    latest.current = props;
  }, [props]);
  const register = context?.register,
    update = context?.update;
  useEffect(() => {
    if (!anchor.current || !register) return;
    return register({ ...latest.current, target: anchor.current });
  }, [register, props.meeting.id]);
  useEffect(() => {
    if (anchor.current) update?.({ ...props, target: anchor.current });
  }, [update, props]);
  return (
    <>
      {context?.meetingId && context.meetingId !== props.meeting.id && (
        <p role="status">
          {language === "en"
            ? "A recording is already open in this tab. "
            : "Un enregistrement est déjà ouvert dans cet onglet. "}
          <Link href={`/reunions/${context.meetingId}`}>
            {language === "en"
              ? "Return to recording"
              : "Revenir à l’enregistrement"}
          </Link>
        </p>
      )}
      <div ref={anchor} />
    </>
  );
}
