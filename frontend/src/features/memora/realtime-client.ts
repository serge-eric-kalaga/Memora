import { accessHeaders, type Access } from "./api";

type Listener = () => void;
const feeds = new Map<string, { listeners: Set<Listener>; close: () => void }>();

/** One connection per scope in a tab. Missed events are recovered by the initial
 * refresh after each reconnect. Credentials are headers, never URL parameters. */
export function subscribeUpdates(meeting: string | undefined, access: Access, listener: Listener) {
  const key = JSON.stringify([meeting, access.token, access.password]);
  let feed = feeds.get(key);
  if (!feed) {
    const listeners = new Set<Listener>();
    let disposed = false, terminal = false, attempt = 0;
    let controller: AbortController | undefined;
    let retry: ReturnType<typeof setTimeout> | undefined;
    let fallback: ReturnType<typeof setInterval> | undefined;
    let pending: ReturnType<typeof setTimeout> | undefined;
    let watchdog: ReturnType<typeof setTimeout> | undefined;
    const refresh = () => {
      if (disposed || pending) return;
      pending = setTimeout(() => {
        pending = undefined;
        listeners.forEach((fn) => fn());
      }, 150);
    };
    const degraded = () => {
      if (!fallback && !terminal) fallback = setInterval(refresh, 15000);
    };
    const stopFallback = () => {
      clearInterval(fallback);
      fallback = undefined;
    };
    const connect = async () => {
      if (disposed || terminal || !navigator.onLine) return;
      controller = new AbortController();
      const active = controller;
      const armWatchdog = () => {
        clearTimeout(watchdog);
        watchdog = setTimeout(() => active.abort(), 45000);
      };
      try {
        armWatchdog();
        const response = await fetch(`/mapi/events${meeting ? `?meeting=${encodeURIComponent(meeting)}` : ""}`, {
          headers: accessHeaders(access),
          cache: "no-store",
          signal: active.signal,
        });
        if ([401, 403, 404].includes(response.status)) {
          terminal = true;
          stopFallback();
          refresh(); // Normal loader clears content after revoked guest access.
          return;
        }
        if (!response.ok || !response.body || !response.headers.get("content-type")?.includes("text/event-stream")) {
          throw new Error("Stream unavailable");
        }
        stopFallback();
        attempt = 0;
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        try {
          while (!disposed) {
            const { value, done } = await reader.read();
            if (done) break;
            armWatchdog();
            buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");
            if (buffer.length > 65536) throw new Error("Invalid event frame");
            let boundary: number;
            while ((boundary = buffer.indexOf("\n\n")) !== -1) {
              const frame = buffer.slice(0, boundary);
              buffer = buffer.slice(boundary + 2);
              if (/^event: refresh$/m.test(frame)) refresh();
              if (/^event: unavailable$/m.test(frame)) {
                refresh();
                throw new Error("Stream closed");
              }
            }
          }
        } finally {
          await reader.cancel().catch(() => {});
          reader.releaseLock();
        }
      } catch {
        // Keep the last displayed state; the regular loader reports access/errors.
      } finally {
        clearTimeout(watchdog);
        active.abort();
        if (!disposed && !terminal) {
          degraded();
          retry = setTimeout(() => void connect(), Math.min(30000, 1000 * 2 ** Math.min(attempt++, 5)) + Math.random() * 500);
        }
      }
    };
    const online = () => {
      clearTimeout(retry);
      // Closing the previous stream lets its finally schedule a single reconnect.
      if (controller && !controller.signal.aborted) controller.abort();
      else void connect();
    };
    const offline = () => controller?.abort();
    window.addEventListener("online", online);
    window.addEventListener("offline", offline);
    feed = {
      listeners,
      close: () => {
        disposed = true;
        controller?.abort();
        clearTimeout(retry);
        clearTimeout(pending);
        clearTimeout(watchdog);
        stopFallback();
        window.removeEventListener("online", online);
        window.removeEventListener("offline", offline);
      },
    };
    feeds.set(key, feed);
    void connect();
    if (!navigator.onLine) degraded();
  }
  feed.listeners.add(listener);
  return () => {
    feed.listeners.delete(listener);
    if (!feed.listeners.size) {
      feed.close();
      feeds.delete(key);
    }
  };
}
