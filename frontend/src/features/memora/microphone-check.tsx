"use client";

import {
  useCallback,
  useEffect,
  useId,
  useRef,
  useState,
  useSyncExternalStore,
} from "react";
import {
  microphoneError,
  microphoneMetrics,
  releaseMicrophoneResources,
  type MicrophoneResources,
} from "./microphone-check.helpers";
import s from "./microphone-check.module.css";

const subscribeCapabilities = () => () => {};
function capabilities() {
  if (
    typeof window === "undefined" ||
    typeof navigator.mediaDevices?.getUserMedia !== "function" ||
    typeof window.AudioContext !== "function"
  )
    return "none";
  return typeof MediaRecorder === "function" ? "record" : "test";
}

export type MicrophoneCheckProps = {
  language: "fr" | "en";
  selectedDeviceId: string;
  onDeviceChange: (deviceId: string) => void;
  /** Set while the meeting itself is recording; this also releases an active test. */
  disabled?: boolean;
  onActiveChange?: (active: boolean) => void;
};

export function MicrophoneCheck({
  language,
  selectedDeviceId,
  onDeviceChange,
  disabled = false,
  onActiveChange,
}: MicrophoneCheckProps) {
  const id = useId();
  const en = language === "en";
  const text = (fr: string, english: string) => (en ? english : fr);
  const capability = useSyncExternalStore(
    subscribeCapabilities,
    capabilities,
    () => "pending",
  );
  const supported = capability === "pending" ? null : capability !== "none";
  const canRecord = capability === "record";
  const [devices, setDevices] = useState<MediaDeviceInfo[]>([]);
  const [status, setStatus] = useState<"idle" | "starting" | "active">("idle");
  const [error, setError] = useState("");
  const [reading, setReading] = useState({
    level: 0,
    silent: false,
    clipped: false,
  });
  const [muted, setMuted] = useState(false);
  const [recording, setRecording] = useState(false);
  const [sampleUrl, setSampleUrl] = useState("");
  const resources = useRef<MicrophoneResources>({
    stream: null,
    context: null,
    source: null,
    analyser: null,
    recorder: null,
    frame: null,
  });
  const mounted = useRef(false);
  const generation = useRef(0);
  const sampleGeneration = useRef(0);
  const sampleUrlRef = useRef("");
  const sampleTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const testTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const activeCallback = useRef(onActiveChange);
  useEffect(() => {
    activeCallback.current = onActiveChange;
  }, [onActiveChange]);

  const clearTimers = useCallback(() => {
    if (sampleTimer.current !== null) clearTimeout(sampleTimer.current);
    if (testTimer.current !== null) clearTimeout(testTimer.current);
    sampleTimer.current = testTimer.current = null;
  }, []);
  const stop = useCallback(() => {
    generation.current++;
    clearTimers();
    releaseMicrophoneResources(resources.current);
    if (mounted.current) {
      setStatus("idle");
      setRecording(false);
      setMuted(false);
      setReading({ level: 0, silent: false, clipped: false });
      activeCallback.current?.(false);
    }
  }, [clearTimers]);
  const discardSample = useCallback(() => {
    sampleGeneration.current++;
    if (sampleUrlRef.current) URL.revokeObjectURL(sampleUrlRef.current);
    sampleUrlRef.current = "";
    if (mounted.current) setSampleUrl("");
  }, []);
  const refreshDevices = useCallback(async () => {
    try {
      const all = await navigator.mediaDevices.enumerateDevices();
      if (mounted.current)
        setDevices(all.filter((device) => device.kind === "audioinput"));
    } catch {
      /* The explicit test reports permission/device failures. */
    }
  }, []);

  const dispose = useCallback(() => {
    mounted.current = false;
    generation.current++;
    sampleGeneration.current++;
    clearTimers();
    releaseMicrophoneResources(resources.current);
    if (sampleUrlRef.current) URL.revokeObjectURL(sampleUrlRef.current);
    sampleUrlRef.current = "";
    navigator.mediaDevices?.removeEventListener?.(
      "devicechange",
      refreshDevices,
    );
    activeCallback.current?.(false);
  }, [clearTimers, refreshDevices]);
  useEffect(() => {
    mounted.current = true;
    if (typeof navigator.mediaDevices?.enumerateDevices === "function") {
      void navigator.mediaDevices
        .enumerateDevices()
        .then((all) => {
          if (mounted.current)
            setDevices(all.filter((device) => device.kind === "audioinput"));
        })
        .catch(() => undefined);
    }
    navigator.mediaDevices?.addEventListener?.("devicechange", refreshDevices);
    return dispose;
  }, [dispose, refreshDevices]);
  useEffect(() => {
    if (disabled) stop();
  }, [disabled, stop]);

  async function start() {
    if (disabled || status !== "idle") return;
    setError("");
    if (!navigator.mediaDevices?.getUserMedia || !window.AudioContext) {
      setError(microphoneError("Unsupported", language));
      return;
    }
    const token = ++generation.current;
    setStatus("starting");
    activeCallback.current?.(true);
    try {
      const context = new AudioContext();
      resources.current.context = context;
      await context.resume();
      if (!mounted.current || token !== generation.current) return;
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          ...(selectedDeviceId
            ? { deviceId: { exact: selectedDeviceId } }
            : {}),
          channelCount: { ideal: 1 },
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
      if (!mounted.current || token !== generation.current) {
        stream.getTracks().forEach((track) => track.stop());
        return;
      }
      resources.current.stream = stream;
      const source = context.createMediaStreamSource(stream);
      const analyser = context.createAnalyser();
      analyser.fftSize = 2048;
      source.connect(analyser); // Never connect to speakers: avoid acoustic feedback.
      resources.current.source = source;
      resources.current.analyser = analyser;
      for (const track of stream.getAudioTracks()) {
        track.onended = () => {
          setError(
            text(
              "Le microphone a été déconnecté. Le test est arrêté.",
              "The microphone disconnected. The test has stopped.",
            ),
          );
          stop();
        };
        track.onmute = () => {
          if (mounted.current) setMuted(true);
        };
        track.onunmute = () => {
          if (mounted.current) setMuted(false);
        };
      }
      setStatus("active");
      void refreshDevices();
      const samples = new Float32Array(analyser.fftSize);
      let last = 0;
      let silentSince = 0;
      let clippedUntil = 0;
      const update = (now: number) => {
        if (!mounted.current || token !== generation.current) return;
        if (now - last >= 100) {
          analyser.getFloatTimeDomainData(samples);
          const metrics = microphoneMetrics(samples);
          if (metrics.rms < 0.005) {
            if (!silentSince) silentSince = now;
          } else silentSince = 0;
          if (metrics.clipping) clippedUntil = now + 1500;
          setReading({
            level: metrics.level,
            silent: Boolean(silentSince && now - silentSince >= 2000),
            clipped: now < clippedUntil,
          });
          last = now;
        }
        resources.current.frame = requestAnimationFrame(update);
      };
      resources.current.frame = requestAnimationFrame(update);
      testTimer.current = setTimeout(stop, 60_000);
    } catch (cause) {
      if (mounted.current && token === generation.current) {
        setError(
          microphoneError(cause instanceof Error ? cause.name : "", language),
        );
        stop();
      }
    }
  }

  function startSample() {
    if (
      disabled ||
      status !== "active" ||
      recording ||
      !resources.current.stream ||
      typeof MediaRecorder === "undefined"
    )
      return;
    setError("");
    discardSample();
    const token = ++sampleGeneration.current;
    try {
      const mimeType = [
        "audio/webm;codecs=opus",
        "audio/mp4",
        "audio/webm",
      ].find((mime) => MediaRecorder.isTypeSupported(mime));
      const recorder = new MediaRecorder(resources.current.stream, {
        ...(mimeType ? { mimeType } : {}),
        audioBitsPerSecond: 128000,
      });
      const chunks: Blob[] = [];
      recorder.ondataavailable = (event) => {
        if (event.data.size) chunks.push(event.data);
      };
      recorder.onerror = () => {
        if (mounted.current && token === sampleGeneration.current)
          setError(
            text(
              "L’échantillon n’a pas pu être enregistré. Réessayez.",
              "The sample could not be recorded. Try again.",
            ),
          );
      };
      recorder.onstop = () => {
        if (mounted.current && token === sampleGeneration.current) {
          if (sampleTimer.current !== null) clearTimeout(sampleTimer.current);
          sampleTimer.current = null;
          setRecording(false);
          if (resources.current.recorder === recorder)
            resources.current.recorder = null;
          if (chunks.length) {
            const url = URL.createObjectURL(
              new Blob(chunks, { type: recorder.mimeType || chunks[0].type }),
            );
            if (sampleUrlRef.current) URL.revokeObjectURL(sampleUrlRef.current);
            sampleUrlRef.current = url;
            setSampleUrl(url);
          }
        }
      };
      resources.current.recorder = recorder;
      recorder.start();
      setRecording(true);
      sampleTimer.current = setTimeout(() => {
        if (recorder.state !== "inactive") recorder.stop();
      }, 10_000);
    } catch (cause) {
      setError(
        microphoneError(cause instanceof Error ? cause.name : "", language),
      );
      resources.current.recorder = null;
      setRecording(false);
    }
  }

  const missingDevice = Boolean(
    selectedDeviceId &&
    !devices.some((device) => device.deviceId === selectedDeviceId),
  );
  return (
    <section className={s.panel} aria-labelledby={`${id}-title`}>
      <div className={s.heading}>
        <h3 id={`${id}-title`}>
          {text("Vérifier le microphone", "Check your microphone")}
        </h3>
        <span className={status === "active" ? s.live : s.local}>
          {status === "active"
            ? text("Microphone actif", "Microphone active")
            : text("Test local", "Local test")}
        </span>
      </div>
      <p className={s.help} id={`${id}-notice`}>
        {text(
          "Le microphone s’active uniquement après votre clic. Ce test et l’échantillon restent dans cet onglet, sans envoi. Le test s’arrête après une minute.",
          "The microphone only activates after your click. This test and its sample stay in this tab without uploading. The test stops after one minute.",
        )}
      </p>
      <label className={s.label} htmlFor={`${id}-device`}>
        {text("Entrée audio", "Audio input")}
      </label>
      <select
        id={`${id}-device`}
        className={s.select}
        value={selectedDeviceId}
        onChange={(event) => onDeviceChange(event.target.value)}
        disabled={disabled || status !== "idle"}
        aria-describedby={`${id}-notice`}
      >
        <option value="">
          {text("Microphone par défaut", "Default microphone")}
        </option>
        {devices
          .filter((device) => device.deviceId)
          .map((device, index) => (
            <option value={device.deviceId} key={device.deviceId}>
              {device.label ||
                `${text("Microphone", "Microphone")} ${index + 1}`}
            </option>
          ))}
        {missingDevice && (
          <option value={selectedDeviceId}>
            {text(
              "Entrée sélectionnée indisponible",
              "Selected input unavailable",
            )}
          </option>
        )}
      </select>
      <div className={s.buttons}>
        <button
          type="button"
          className={s.primary}
          onClick={() => void start()}
          disabled={disabled || supported !== true || status !== "idle"}
        >
          {status === "starting"
            ? text("Autorisation en attente…", "Waiting for permission…")
            : text("Tester le microphone", "Test microphone")}
        </button>
        {status !== "idle" && (
          <button type="button" className={s.button} onClick={stop}>
            {text("Arrêter le test", "Stop test")}
          </button>
        )}
      </div>
      {supported === false && (
        <p className={s.warning}>{microphoneError("Unsupported", language)}</p>
      )}
      {error && (
        <p className={s.error} role="alert">
          {error}
        </p>
      )}
      {status === "active" && (
        <div className={s.monitor}>
          <label htmlFor={`${id}-level`}>
            {text("Niveau d’entrée", "Input level")}
          </label>
          <meter
            id={`${id}-level`}
            min={0}
            max={100}
            low={15}
            high={90}
            optimum={65}
            value={reading.level}
            className={s.meter}
          >
            {Math.round(reading.level)}%
          </meter>
          <p
            className={
              reading.clipped || reading.silent || muted ? s.warning : s.help
            }
            role="status"
          >
            {muted
              ? text(
                  "L’entrée audio est suspendue ou coupée.",
                  "The audio input is suspended or muted.",
                )
              : reading.clipped
                ? text(
                    "Saturation possible : éloignez le microphone ou réduisez le gain.",
                    "Possible clipping: move the microphone away or lower the gain.",
                  )
                : reading.silent
                  ? text(
                      "Signal très faible ou silence : parlez normalement et vérifiez l’entrée choisie.",
                      "Very low signal or silence: speak normally and check the selected input.",
                    )
                  : text(
                      "Parlez normalement. Ce niveau ne garantit pas la précision de la transcription.",
                      "Speak normally. This level does not guarantee transcription accuracy.",
                    )}
          </p>
          {canRecord ? (
            <div className={s.buttons}>
              <button
                type="button"
                className={s.button}
                onClick={startSample}
                disabled={recording}
              >
                {text(
                  "Enregistrer un échantillon (10 s max.)",
                  "Record a sample (10 s max.)",
                )}
              </button>
              {recording && (
                <button
                  type="button"
                  className={s.button}
                  onClick={() => {
                    const recorder = resources.current.recorder;
                    if (recorder && recorder.state !== "inactive")
                      recorder.stop();
                  }}
                >
                  {text("Terminer l’échantillon", "Finish sample")}
                </button>
              )}
            </div>
          ) : (
            <p className={s.help}>
              {text(
                "L’enregistrement d’échantillon n’est pas pris en charge par ce navigateur.",
                "Sample recording is not supported by this browser.",
              )}
            </p>
          )}
        </div>
      )}
      {sampleUrl && (
        <div className={s.sample}>
          <p className={s.sampleLabel} id={`${id}-sample-label`}>
            {text("Réécouter votre échantillon", "Listen to your sample")}
          </p>
          <audio
            id={`${id}-sample`}
            aria-labelledby={`${id}-sample-label`}
            controls
            src={sampleUrl}
            preload="metadata"
          />
          <button type="button" className={s.button} onClick={discardSample}>
            {text("Effacer l’échantillon", "Discard sample")}
          </button>
        </div>
      )}
      {disabled && (
        <p className={s.help}>
          {text(
            "Test désactivé pendant l’enregistrement de la réunion.",
            "Testing is disabled while the meeting is recording.",
          )}
        </p>
      )}
    </section>
  );
}
