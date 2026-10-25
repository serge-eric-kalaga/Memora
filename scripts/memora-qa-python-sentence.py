"""Synthetic phrase reference and recorded synthetic stream, one local base model."""

import importlib.util
import json
import time
import wave
from pathlib import Path

from faster_whisper import WhisperModel
from faster_whisper.audio import decode_audio

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "capture_metrics", ROOT / "scripts/memora-qa-capture.py"
)
metrics = importlib.util.module_from_spec(spec)
spec.loader.exec_module(metrics)
phrase = "Aujourd'hui nous allons parler du langage python."
fixture = ROOT / "backend/test/fixtures/memora/python-sentence.aiff"
samples = decode_audio(str(fixture), sampling_rate=16000)
with wave.open(str(fixture.with_suffix(".wav")), "wb") as out:
    out.setnchannels(1)
    out.setsampwidth(2)
    out.setframerate(16000)
    out.writeframes((samples * 32767).astype("<i2").tobytes())
model = WhisperModel(
    "base",
    device="cpu",
    compute_type="int8",
    cpu_threads=2,
    download_root=str(ROOT / ".memora/models"),
    local_files_only=True,
)
results = []
for language in (None, "fr"):
    t = time.monotonic()
    segments, _info = model.transcribe(
        samples,
        language=language,
        multilingual=language is None,
        beam_size=5,
        vad_filter=True,
        condition_on_previous_text=False,
    )
    text = " ".join(s.text.strip() for s in segments)
    row = {
        "case": "python-sentence",
        "language_mode": language or "auto",
        "duration": round(len(samples) / 16000, 3),
        "seconds": round(time.monotonic() - t, 3),
        "actual_synthetic": text,
        **metrics.metrics(phrase, text),
    }
    results.append(row)
    print(json.dumps(row, ensure_ascii=False), flush=True)
path = ROOT / ".memora/capture-qa/browser-pause-resume.webm"
if path.exists():
    t = time.monotonic()
    audio = decode_audio(str(path), sampling_rate=16000)
    segments, _info = model.transcribe(
        audio,
        beam_size=5,
        multilingual=True,
        vad_filter=True,
        condition_on_previous_text=False,
    )
    text = " ".join(s.text.strip() for s in segments)
    expected = metrics.EXPECTED["english"]
    row = {
        "case": "browser-pause-resume",
        "duration": round(len(audio) / 16000, 3),
        "seconds": round(time.monotonic() - t, 3),
        "actual_synthetic": text,
        **metrics.metrics(expected, text),
    }
    results.append(row)
    print(json.dumps(row, ensure_ascii=False), flush=True)
(ROOT / ".agents/logs/python-sentence-qa.json").write_text(
    json.dumps(results, ensure_ascii=False, indent=2)
)
