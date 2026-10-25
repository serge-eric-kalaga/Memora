export type MicrophoneMetrics = {
  rms: number;
  peak: number;
  dbfs: number;
  level: number;
  clipping: boolean;
};

/** Technical indicators, not a speech-recognition quality score. */
export function microphoneMetrics(
  samples: ArrayLike<number>,
): MicrophoneMetrics {
  let energy = 0;
  let peak = 0;
  for (let i = 0; i < samples.length; i++) {
    const value = Number.isFinite(samples[i]) ? samples[i] : 0;
    energy += value * value;
    peak = Math.max(peak, Math.abs(value));
  }
  const rms = samples.length ? Math.sqrt(energy / samples.length) : 0;
  const dbfs = rms > 0 ? Math.max(-60, 20 * Math.log10(rms)) : -60;
  return {
    rms,
    peak,
    dbfs,
    level: Math.max(0, Math.min(100, ((dbfs + 60) / 60) * 100)),
    clipping: peak >= 0.98,
  };
}

export function microphoneError(name: string, language: "fr" | "en"): string {
  const messages: Record<string, [string, string]> = {
    NotAllowedError: [
      "Accès refusé. Autorisez le microphone dans le navigateur puis réessayez.",
      "Access denied. Allow microphone access in your browser, then try again.",
    ],
    SecurityError: [
      "Le navigateur bloque le microphone. Utilisez localhost ou une connexion sécurisée et vérifiez les permissions.",
      "Your browser blocks the microphone. Use localhost or a secure connection and check permissions.",
    ],
    NotFoundError: [
      "Aucun microphone disponible. Branchez une entrée audio puis réessayez.",
      "No microphone is available. Connect an audio input, then try again.",
    ],
    OverconstrainedError: [
      "L’entrée choisie n’est plus disponible. Choisissez un autre microphone.",
      "The selected input is no longer available. Choose another microphone.",
    ],
    NotReadableError: [
      "Le microphone ne peut pas être ouvert. Vérifiez sa connexion et les applications qui l’utilisent.",
      "The microphone cannot be opened. Check its connection and other apps using it.",
    ],
    Unsupported: [
      "Ce navigateur ne permet pas ce test audio. Essayez un navigateur compatible sur localhost ou HTTPS.",
      "This browser does not support the audio test. Try a compatible browser on localhost or HTTPS.",
    ],
  };
  return (messages[name] || [
    "Le test audio a échoué. Arrêtez le test puis réessayez.",
    "The audio test failed. Stop the test, then try again.",
  ])[language === "fr" ? 0 : 1];
}

export type MicrophoneResources = {
  stream: MediaStream | null;
  context: AudioContext | null;
  source: MediaStreamAudioSourceNode | null;
  analyser: AnalyserNode | null;
  recorder: MediaRecorder | null;
  frame: number | null;
};

/** Does not revoke the recorded sample: stopping the test must still permit replay. */
export function releaseMicrophoneResources(
  resources: MicrophoneResources,
  cancelFrame: (id: number) => void = cancelAnimationFrame,
) {
  if (resources.frame !== null) cancelFrame(resources.frame);
  resources.frame = null;
  const recorder = resources.recorder;
  resources.recorder = null;
  if (recorder && recorder.state !== "inactive") {
    try {
      recorder.stop();
    } catch {
      /* Already ended by a device disconnect. */
    }
  }
  for (const node of [resources.source, resources.analyser]) {
    try {
      node?.disconnect();
    } catch {
      /* Already disconnected. */
    }
  }
  resources.source = resources.analyser = null;
  for (const track of resources.stream?.getTracks() || []) {
    track.onended = null;
    track.onmute = null;
    track.onunmute = null;
    track.stop();
  }
  resources.stream = null;
  const context = resources.context;
  resources.context = null;
  if (context && context.state !== "closed")
    void context.close().catch(() => undefined);
}
