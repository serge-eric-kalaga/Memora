"use client";
import {
  useCallback,
  useEffect,
  useEffectEvent,
  useRef,
  useState,
} from "react";
import { createPortal } from "react-dom";
import Link from "next/link";
import { Mic, Pause, Play, Square, Upload, RefreshCw } from "lucide-react";
import { useMemoraText } from "./i18n";
import { useI18n } from "@/lib/i18n/use-i18n";
import { MicrophoneCheck } from "./microphone-check";
import { useRecordingContinuity } from "./use-recording-continuity";
import { RecordingSignal } from "./recording-signal";
import { AudioLanguage } from "./audio-language";
import { api, clock, type Meeting } from "./api";
import { saveChunk, pendingChunks, removeChunk } from "./storage";
import s from "./memora.module.css";
import bar from "./capture-session.module.css";
const btn = s.button,
  primary = `${s.button} ${s.primary}`;
function ErrorBox({ error }: { error: string }) {
  return error ? (
    <div className={s.error} role="alert">
      {error}
    </div>
  ) : null;
}
export function CaptureRuntime({
  meeting,
  refresh,
  onCaptureState,
  target,
}: {
  target: HTMLElement | null;
  meeting: Meeting;
  refresh: () => Promise<void>;
  onCaptureState: (value: string) => void;
}) {
  const tr = useMemoraText();
  const { language } = useI18n();
  const [captureStream, setCaptureStream] = useState<MediaStream | null>(null);
  const [selectedDeviceId, setSelectedDeviceId] = useState("");
  const [microphoneTestActive, setMicrophoneTestActive] = useState(false);
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
  const mounted = useRef(true),
    acquiring = useRef(false);
  useEffect(() => {
    if (!target) queueMicrotask(() => setMicrophoneTestActive(false));
  }, [target]);
  const recorder = useRef<MediaRecorder | null>(null),
    stream = useRef<MediaStream | null>(null),
    seq = useRef(meeting.chunk_count || meeting.chunks?.length || 0),
    chain = useRef(Promise.resolve()),
    stopRequested = useRef(false),
    active = useRef(false),
    lastTick = useRef(0),
    fileInput = useRef<HTMLInputElement>(null),
    importController = useRef<AbortController | null>(null);
  useRecordingContinuity(
    meeting.id,
    state,
    recorder,
    setWarning,
    language === "en",
  );
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
            stopRequested.current = true;
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
      stopRequested.current = true;
      active.current = false;
      if (recorder.current && recorder.current.state !== "inactive")
        recorder.current.stop();
      stream.current?.getTracks().forEach((t) => t.stop());
    };
  }, [meeting.settings?.max_duration_minutes, changeState]);
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
  useEffect(() => {
    mounted.current = true;
    const stop = () => {
      mounted.current = false;
      stopRequested.current = true;
      active.current = false;
      const media = recorder.current;
      if (media && media.state !== "inactive") {
        try {
          media.requestData();
          media.stop();
        } catch {
          /* Last confirmed chunks remain in IndexedDB. */
        }
      }
      stream.current?.getTracks().forEach((track) => track.stop());
    };
    window.addEventListener("pagehide", stop);
    return () => {
      window.removeEventListener("pagehide", stop);
      stop();
    };
  }, []);

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
  function pause() {
    if (recorder.current?.state !== "recording") return;
    recorder.current.pause();
    active.current = false;
    changeState("paused");
    void api(`meetings/${meeting.id}`, {
      method: "PATCH",
      body: JSON.stringify({ state: "paused" }),
    }).catch(() => {});
  }
  function resume() {
    if (recorder.current?.state !== "paused") return;
    recorder.current.resume();
    active.current = true;
    lastTick.current = Date.now();
    changeState("recording");
    void api(`meetings/${meeting.id}`, {
      method: "PATCH",
      body: JSON.stringify({ state: "recording" }),
    }).catch(() => {});
  }
  async function start() {
    if (
      acquiring.current ||
      (recorder.current && recorder.current.state !== "inactive")
    )
      return;
    acquiring.current = true;
    changeState("starting");
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
            ...(selectedDeviceId
              ? { deviceId: { exact: selectedDeviceId } }
              : {}),
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
      if (!mounted.current) {
        stream.current?.getTracks().forEach((track) => track.stop());
        return;
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
          stopRequested.current = true;
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
        stopRequested.current = true;
        setError(
          tr(
            "L’enregistrement a été interrompu. Les fragments sauvegardés peuvent être repris.",
          ),
        );
        changeState("interrupted");
        active.current = false;
      };
      media.onstop = () => {
        if (!stopRequested.current) {
          void api(`meetings/${meeting.id}`, {
            method: "PATCH",
            body: JSON.stringify({ state: "interrupted" }),
          }).catch(() => undefined);
          changeState("interrupted");
          setError(
            language === "en"
              ? "Recording stopped unexpectedly. Saved audio is preserved; check it before finalizing."
              : "L’enregistrement s’est arrêté de façon inattendue. Les fragments sauvegardés sont conservés ; vérifiez-les avant de finaliser.",
          );
        }
        active.current = false;
        setCaptureStream(null);
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
      if (!mounted.current) {
        stream.current?.getTracks().forEach((track) => track.stop());
        return;
      }
      stopRequested.current = false;
      media.start(10000);
      setCaptureStream(stream.current);
      active.current = true;
      lastTick.current = Date.now();
      changeState("recording");
    } catch (e) {
      stream.current?.getTracks().forEach((t) => t.stop());
      setCaptureStream(null);
      setError((e as Error).message);
      if (mounted.current) changeState("idle");
    } finally {
      acquiring.current = false;
    }
  }
  async function finalize() {
    setError("");
    changeState("saving");
    stopRequested.current = true;
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
  const fullControls = (
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
      <p className={s.recorderMessage}>
        {state === "recording"
          ? language === "en"
            ? "Your meeting is being recorded. You can pause at any time."
            : "Votre réunion est en cours d’enregistrement. Vous pouvez mettre en pause à tout moment."
          : state === "paused"
            ? language === "en"
              ? "Recording is paused. Resume whenever you’re ready."
              : "L’enregistrement est en pause. Reprenez quand vous êtes prêt."
            : state === "saving"
              ? language === "en"
                ? "Saving your audio. Please keep this page open."
                : "Nous sauvegardons votre audio. Gardez cette page ouverte encore un instant."
              : state === "uploading"
                ? language === "en"
                  ? "Your audio is being imported. You can follow its progress below."
                  : "Votre audio est en cours d’import. Suivez son avancement ci-dessous."
                : state === "interrupted"
                  ? language === "en"
                    ? "The recording or import was interrupted. Follow the instructions below to continue."
                    : "L’enregistrement ou l’import a été interrompu. Suivez les indications ci-dessous pour poursuivre."
                  : state === "done"
                    ? language === "en"
                      ? "Your audio has been sent for analysis."
                      : "Votre audio a été transmis pour analyse."
                    : meeting.mode === "import"
                      ? language === "en"
                        ? "Add your meeting audio to find its key takeaways."
                        : "Ajoutez l’audio de votre réunion pour en retrouver l’essentiel."
                      : language === "en"
                        ? "Ready to begin? Let everyone know, then start recording."
                        : "Prêt à commencer ? Prévenez les participants, puis lancez l’enregistrement."}
      </p>
      <details className={s.recorderHelp}>
        <summary>
          {language === "en"
            ? meeting.mode === "import"
              ? "Import tips"
              : "Recording tips"
            : meeting.mode === "import"
              ? "Conseils pour importer un audio"
              : "Conseils pour enregistrer"}
        </summary>
        {meeting.mode === "import" ? (
          <p>
            {language === "en"
              ? "Maximum file size:"
              : "Taille maximale du fichier :"}{" "}
            {meeting.settings?.max_upload_mb || 250}{" "}
            {language === "en" ? "MB" : "Mo"}. MP3, WAV, M4A, MP4, OGG, WebM,
            FLAC, AAC.
          </p>
        ) : (
          <>
            <p>
              {language === "en"
                ? "Let participants know before recording. Your microphone starts only when you select Record."
                : "Informez les participants avant de commencer. Le microphone s’active uniquement lorsque vous choisissez Enregistrer."}
            </p>
            <p>
              {language === "en"
                ? "You can navigate within Memora or switch tabs. Keep this browser tab open; reloading, sleep or closing the lid can interrupt recording."
                : "Vous pouvez naviguer dans Memora ou changer d’onglet. Gardez cet onglet ouvert ; actualisation, veille ou fermeture du capot peuvent interrompre la capture."}
            </p>
            <p>
              {language === "en"
                ? "Maximum recording time:"
                : "Durée maximale d’enregistrement :"}{" "}
              {meeting.settings?.max_duration_minutes || 120} min.
            </p>
          </>
        )}
      </details>
      {["idle", "interrupted"].includes(state) && (
        <div style={{ maxWidth: 330, margin: "20px auto", textAlign: "left" }}>
          <AudioLanguage
            value={captureLanguage || language}
            onChange={setCaptureLanguage}
          />
        </div>
      )}
      {meeting.mode !== "import" && chunkCount === 0 && (
        <MicrophoneCheck
          language={language === "en" ? "en" : "fr"}
          selectedDeviceId={selectedDeviceId}
          onDeviceChange={setSelectedDeviceId}
          onActiveChange={setMicrophoneTestActive}
          disabled={!["idle", "interrupted"].includes(state)}
        />
      )}
      <ErrorBox error={error} />
      {warning && (
        <div className={s.notice} role="status">
          {tr(warning)}
        </div>
      )}
      {meeting.mode !== "import" && (
        <div className={s.timer}>
          {state === "recording" && <span className={s.pulse} />}{" "}
          {clock(elapsed)}
        </div>
      )}
      {captureStream && ["recording", "paused"].includes(state) && (
        <RecordingSignal
          stream={captureStream}
          state={state}
          language={language === "en" ? "en" : "fr"}
        />
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
            <button
              className={primary}
              disabled={microphoneTestActive}
              onClick={() => void start()}
            >
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
          <button className={btn} onClick={pause}>
            <Pause size={18} />
            Pause
          </button>
        )}
        {state === "paused" && (
          <button className={primary} onClick={resume}>
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
  const ongoing = [
    "starting",
    "recording",
    "paused",
    "saving",
    "uploading",
    "interrupted",
  ].includes(state);
  return (
    <>
      {target ? createPortal(fullControls, target) : null}
      {!target && ongoing && (
        <aside
          data-testid="persistent-capture-bar"
          className={bar.bar}
          aria-label={
            language === "en" ? "Current recording" : "Enregistrement en cours"
          }
        >
          <div className={bar.identity}>
            <strong>{meeting.title}</strong>
            <span role="status">
              {clock(elapsed)} ·{" "}
              {state === "recording"
                ? language === "en"
                  ? "Recording"
                  : "Enregistrement"
                : state === "paused"
                  ? language === "en"
                    ? "Paused"
                    : "En pause"
                  : state === "saving"
                    ? language === "en"
                      ? "Saving"
                      : "Sauvegarde"
                    : state === "interrupted"
                      ? language === "en"
                        ? "Interrupted · audio preserved"
                        : "Interrompu · audio conservé"
                      : state === "uploading"
                        ? `${progress}%`
                        : language === "en"
                          ? "Microphone permission"
                          : "Autorisation du micro"}
            </span>
          </div>
          <div className={bar.controls}>
            {state === "recording" && (
              <button className={btn} onClick={pause}>
                <Pause size={16} />
                Pause
              </button>
            )}
            {state === "paused" && (
              <button className={btn} onClick={resume}>
                <Play size={16} />
                {tr("Reprendre")}
              </button>
            )}
            {["recording", "paused", "interrupted"].includes(state) &&
              meeting.mode !== "import" && (
                <button className={primary} onClick={() => void finalize()}>
                  <Square size={15} />
                  {tr("Terminer et analyser")}
                </button>
              )}
            <Link className={btn} href={`/reunions/${meeting.id}`}>
              {language === "en" ? "Open meeting" : "Retour à la réunion"}
            </Link>
          </div>
          {error && (
            <p className={bar.message} role="alert">
              {error}
            </p>
          )}
          {warning && (
            <p className={bar.message} role="status">
              {tr(warning)}
            </p>
          )}
        </aside>
      )}
    </>
  );
}
