export type SignalState =
  | "recording"
  | "paused"
  | "missing"
  | "ended"
  | "muted"
  | "suspended"
  | "unsupported"
  | "silence"
  | "clipping"
  | "inactive";

export function recordingSignalState(
  state: string,
  tracks: Pick<MediaStreamTrack, "readyState" | "muted" | "enabled">[],
  context: string,
  rms: number,
  clipping: boolean,
  quietMs: number,
): SignalState {
  if (state === "paused") return "paused";
  if (state !== "recording") return "inactive";
  if (!tracks.length) return "missing";
  const live = tracks.filter((track) => track.readyState === "live");
  if (!live.length) return "ended";
  if (live.every((track) => track.muted || !track.enabled)) return "muted";
  if (context !== "running") return "suspended";
  if (clipping) return "clipping";
  if (rms < 0.003 && quietMs >= 4000) return "silence";
  return "recording";
}

/** Disconnect only this visualizer's nodes; ownership of tracks remains with recorder. */
export function releaseRecordingSignal(
  context: AudioContext | null,
  nodes: { disconnect(): void }[],
  frame: number | null,
  cancel: (id: number) => void,
) {
  if (frame !== null) cancel(frame);
  for (const node of nodes) {
    try {
      node.disconnect();
    } catch {
      /* Already disconnected. */
    }
  }
  if (context && context.state !== "closed")
    void context.close().catch(() => undefined);
}
