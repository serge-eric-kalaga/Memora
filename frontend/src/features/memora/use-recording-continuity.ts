"use client";

import { useEffect, useEffectEvent, useState, type RefObject } from "react";
import { api } from "./api";

/** Capture remains owned by Recorder; visibility changes never pause or stop it. */
export function useRecordingContinuity(
  meetingId: string,
  state: string,
  recorder: RefObject<MediaRecorder | null>,
  onWarning: (message: string) => void,
  english: boolean,
) {
  const [protection, setProtection] = useState<"native" | "screen" | "none">(
    "none",
  );
  const warn = useEffectEvent(() =>
    onWarning(
      english
        ? "The browser was suspended or slowed down. Check the recorded audio before continuing."
        : "Le navigateur a été suspendu ou ralenti. Vérifiez l’audio enregistré avant de poursuivre.",
    ),
  );
  const enabled = state === "recording" || state === "paused";
  useEffect(() => {
    if (!enabled) return;
    let disposed = false;
    let lock: WakeLockSentinel | null = null;
    let pendingLock = false;
    let native = false;
    let pendingLease = false;
    let leaseRequest: Promise<{ supported: boolean; active: boolean }> | null =
      null;
    let lastHeartbeat = Date.now();
    const update = () => {
      if (!disposed)
        setProtection(
          native ? "native" : lock && !lock.released ? "screen" : "none",
        );
    };
    async function wakeScreen() {
      if (
        disposed ||
        pendingLock ||
        (lock && !lock.released) ||
        document.hidden ||
        !navigator.wakeLock
      )
        return;
      pendingLock = true;
      try {
        const acquired = await navigator.wakeLock.request("screen");
        if (disposed) {
          await acquired.release();
          return;
        }
        lock = acquired;
        acquired.addEventListener("release", update, { once: true });
      } catch {
        /* Optional protection: capture and progressive saving continue. */
      } finally {
        pendingLock = false;
        update();
      }
    }
    async function heartbeat() {
      if (disposed || pendingLease) return;
      pendingLease = true;
      try {
        leaseRequest = api<{ supported: boolean; active: boolean }>(
          `meetings/${meetingId}/capture-awake`,
          {
            method: "POST",
            body: JSON.stringify({ active: true }),
          },
        );
        const result = await leaseRequest;
        native = result.supported && result.active;
      } catch {
        native = false;
      } finally {
        pendingLease = false;
        update();
      }
    }
    function flush() {
      const media = recorder.current;
      if (media?.state === "recording") {
        try {
          media.requestData();
        } catch {
          /* Stop can race a visibility event. */
        }
      }
    }
    function visibility() {
      // Flush before backgrounding; do not make the audio capture depend on RAF.
      flush();
      if (!document.hidden) {
        if (Date.now() - lastHeartbeat > 75000) warn();
        void wakeScreen();
      }
      lastHeartbeat = Date.now();
      void heartbeat();
    }
    void wakeScreen();
    void heartbeat();
    const interval = window.setInterval(() => {
      lastHeartbeat = Date.now();
      void heartbeat();
    }, 30000);
    document.addEventListener("visibilitychange", visibility);
    window.addEventListener("pagehide", flush);
    window.addEventListener("pageshow", visibility);
    return () => {
      disposed = true;
      window.clearInterval(interval);
      document.removeEventListener("visibilitychange", visibility);
      window.removeEventListener("pagehide", flush);
      window.removeEventListener("pageshow", visibility);
      if (lock && !lock.released) void lock.release().catch(() => undefined);
      // A pending acquire completes before release, avoiding an abandoned lease.
      void (async () => {
        await leaseRequest?.catch(() => undefined);
        await api(`meetings/${meetingId}/capture-awake`, {
          method: "POST",
          body: JSON.stringify({ active: false }),
          keepalive: true,
        }).catch(() => undefined);
      })();
    };
  }, [enabled, meetingId, recorder]);
  return enabled ? protection : "none";
}
