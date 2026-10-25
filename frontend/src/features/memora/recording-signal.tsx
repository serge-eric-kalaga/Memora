"use client";

import { useEffect, useRef, useState } from "react";
import { microphoneMetrics } from "./microphone-check.helpers";
import {
  recordingSignalState,
  releaseRecordingSignal,
  type SignalState,
} from "./recording-signal.helpers";
import s from "./recording-signal.module.css";

export type RecordingSignalProps = {
  stream: MediaStream | null;
  state: string;
  language: "fr" | "en";
};
const labels: Record<SignalState, [string, string]> = {
  recording: ["Enregistrement en cours", "Recording in progress"],
  paused: ["Enregistrement en pause", "Recording paused"],
  missing: ["Aucune entrée audio connectée", "No audio input connected"],
  ended: ["Entrée audio déconnectée", "Audio input disconnected"],
  muted: ["Entrée audio muette ou désactivée", "Audio input muted or disabled"],
  suspended: [
    "Analyse audio suspendue par le navigateur",
    "Audio analysis suspended by browser",
  ],
  unsupported: [
    "Visualisation audio indisponible dans ce navigateur",
    "Audio visualization unavailable in this browser",
  ],
  silence: [
    "Signal très faible depuis 4 secondes : vérifiez le microphone",
    "Very quiet for 4 seconds: check the microphone",
  ],
  clipping: [
    "Niveau proche de la saturation : éloignez le microphone",
    "Level near clipping: move microphone away",
  ],
  inactive: ["Visualisation audio arrêtée", "Audio visualization stopped"],
};

export function RecordingSignal({
  stream,
  state,
  language,
}: RecordingSignalProps) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const contextRef = useRef<AudioContext | null>(null);
  const historyRef = useRef<number[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const [view, setView] = useState<{
    status: SignalState;
    level: number;
    dbfs: number;
    peak: number;
  }>({ status: "inactive", level: 0, dbfs: -60, peak: 0 });
  useEffect(() => {
    if (streamRef.current !== stream) {
      streamRef.current = stream;
      historyRef.current = [];
    }
    let frame: number | null = null;
    let context: AudioContext | null = null;
    const nodes: AudioNode[] = [];
    let disposed = false;
    let lastDraw = -Infinity,
      lastPublish = -Infinity,
      quietSince: number | null = null;
    const tracks = stream?.getAudioTracks() || [];
    const initial: SignalState =
      state === "paused"
        ? "paused"
        : state !== "recording"
          ? "inactive"
          : !tracks.length
            ? "missing"
            : "unsupported";
    const publish = (status: SignalState, level = 0, dbfs = -60, peak = 0) => {
      if (!disposed) setView({ status, level, dbfs, peak });
    };
    const clear = () => {
      const ctx = canvas.current?.getContext("2d");
      if (ctx && canvas.current)
        ctx.clearRect(0, 0, canvas.current.width, canvas.current.height);
    };
    if (
      !tracks.length ||
      !["recording", "paused"].includes(state) ||
      typeof window.AudioContext !== "function"
    ) {
      const timer = window.setTimeout(() => {
        publish(initial);
        clear();
      }, 0);
      return () => {
        disposed = true;
        window.clearTimeout(timer);
      };
    }
    try {
      context = new AudioContext();
      contextRef.current = context;
      const source = context.createMediaStreamSource(stream!);
      const analyser = context.createAnalyser();
      analyser.fftSize = 1024;
      source.connect(analyser);
      nodes.push(source, analyser);
      const samples = new Float32Array(analyser.fftSize);
      const tick = (now: number) => {
        if (disposed) return;
        frame = requestAnimationFrame(tick);
        if (now - lastDraw < 50) return;
        lastDraw = now;
        analyser.getFloatTimeDomainData(samples);
        const metrics = microphoneMetrics(samples);
        const active =
          state === "recording" &&
          context?.state === "running" &&
          tracks.some((t) => t.readyState === "live" && t.enabled && !t.muted);
        if (active && metrics.rms < 0.003) quietSince ??= now;
        else quietSince = null;
        const status = recordingSignalState(
          state,
          tracks,
          context?.state || "closed",
          metrics.rms,
          metrics.clipping,
          quietSince === null ? 0 : now - quietSince,
        );
        const visible = active && status !== "paused";
        const element = canvas.current,
          ctx = element?.getContext("2d");
        if (element && ctx) {
          const width = Math.max(
              1,
              Math.round(element.clientWidth * devicePixelRatio),
            ),
            height = Math.round(56 * devicePixelRatio);
          if (element.width !== width || element.height !== height) {
            element.width = width;
            element.height = height;
          }
          ctx.clearRect(0, 0, width, height);
          ctx.strokeStyle = metrics.clipping && visible ? "#b45309" : "#7c83ff";
          ctx.lineWidth = 2 * devicePixelRatio;
          ctx.lineCap = "round";
          ctx.beginPath();
          // One real peak per 50ms: a 15-second window moves right to left.
          // Pausing freezes this history; resuming appends without clearing it.
          if (state === "recording" && context?.state === "running") {
            historyRef.current.push(active ? Math.min(1, metrics.peak) : 0);
            if (historyRef.current.length > 300) historyRef.current.shift();
          }
          const history = historyRef.current;
          for (let bar = 0; bar < history.length; bar++) {
            const amplitude = Math.sqrt(history[bar]);
            if (amplitude === 0) continue;
            const x = width - ((history.length - bar - 0.5) * width) / 300;
            const half = amplitude * height * 0.46;
            ctx.moveTo(x, height / 2 - half);
            ctx.lineTo(x, height / 2 + half);
          }
          ctx.stroke();
        }
        if (now - lastPublish >= 250) {
          lastPublish = now;
          publish(
            status,
            visible ? metrics.level : 0,
            visible ? metrics.dbfs : -60,
            visible ? metrics.peak : 0,
          );
        }
      };
      frame = requestAnimationFrame(tick);
    } catch {
      const timer = window.setTimeout(() => publish("unsupported"), 0);
      return () => {
        disposed = true;
        window.clearTimeout(timer);
        releaseRecordingSignal(context, nodes, frame, cancelAnimationFrame);
        contextRef.current = null;
      };
    }
    return () => {
      disposed = true;
      releaseRecordingSignal(context, nodes, frame, cancelAnimationFrame);
      contextRef.current = null;
    };
  }, [stream, state]);
  const en = language === "en";
  return (
    <section
      className={s.signal}
      aria-label={
        en ? "Recording audio signal" : "Signal audio de l’enregistrement"
      }
    >
      <div className={s.heading}>
        <strong role="status" aria-live="polite">
          {labels[view.status][en ? 1 : 0]}
        </strong>
      </div>
      <canvas ref={canvas} className={s.wave} aria-hidden="true" />
      <meter
        className={s.meter}
        min={0}
        max={100}
        value={view.level}
        aria-label={en ? "Captured audio level" : "Niveau audio capté"}
      />
      {view.status === "suspended" && (
        <button
          type="button"
          onClick={() =>
            void contextRef.current?.resume().catch(() => undefined)
          }
        >
          {en
            ? "Resume audio visualization"
            : "Reprendre la visualisation audio"}
        </button>
      )}
    </section>
  );
}
