"""Local MLX Whisper adapter; no downloads and no FFmpeg subprocess.

Auto language detection is performed independently per VAD speech region.
It remains a dominant language label per region, not per-word identification.
All app MLX calls must use this module's lock because its ModelHolder is global.
"""

import gc
import importlib
import math
import os
import threading
from pathlib import Path

import numpy as np

_lock = threading.Lock()
_SAMPLE_RATE = 16000
_DEFAULT_MODEL = (
    Path(__file__).resolve().parents[3] / ".memora/models/mlx-large-v3-turbo"
)


def _decode_audio(path):
    from faster_whisper.audio import decode_audio

    return decode_audio(str(path), sampling_rate=_SAMPLE_RATE)


def _speech_regions(audio):
    from faster_whisper.vad import VadOptions, get_speech_timestamps

    return get_speech_timestamps(
        audio,
        vad_options=VadOptions(min_silence_duration_ms=300, speech_pad_ms=200),
        sampling_rate=_SAMPLE_RATE,
    )


def _runtime():
    # Lazy imports allow API startup and other engines without loading Metal/model.
    return (
        importlib.import_module("mlx_whisper.transcribe"),
        importlib.import_module("mlx.core"),
    )


def _number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def transcribe(path: Path, tail_seconds=None, language="auto"):
    """Return original-language, source-timed segments; release GPU model per call.

    ``language`` can be auto/fr/en. Auto detects a dominant language independently
    per speech region; switching inside a continuous region remains uncertain.
    Tail mode is provisional live context; final callers must pass the whole file.
    """
    if language not in ("auto", "fr", "en"):
        raise ValueError("Langue de transcription attendue : auto, fr ou en.")
    if tail_seconds is not None:
        tail_seconds = _number(tail_seconds)
        if tail_seconds is None or tail_seconds <= 0:
            raise ValueError("Durée de contexte audio strictement positive requise.")
    with _lock:
        audio = np.asarray(_decode_audio(path), dtype=np.float32)
        offset = 0
        if tail_seconds and len(audio) > tail_seconds * _SAMPLE_RATE:
            offset = len(audio) - max(1, int(tail_seconds * _SAMPLE_RATE))
            audio = audio[offset:]
        if not len(audio) or np.max(np.abs(audio), initial=0) < 0.001:
            return []
        if not np.all(np.isfinite(audio)):
            raise ValueError("Échantillons audio non finis.")
        # Full large-v3 is evaluated for explicitly French final audio only.
        # Keep the multilingual/live model separate: larger is not universally
        # more faithful, particularly for unrequested bilingual translation.
        configured_model = os.environ.get("MEMORA_MLX_MODEL_PATH", str(_DEFAULT_MODEL))
        if language == "fr" and tail_seconds is None:
            configured_model = (
                os.environ.get("MEMORA_MLX_FR_MODEL_PATH") or configured_model
            )
        model_path = Path(configured_model).expanduser().resolve()
        weights = [model_path / "weights.safetensors", model_path / "weights.npz"]
        if not (model_path / "config.json").is_file() or not any(
            p.is_file() and p.stat().st_size > 0 for p in weights
        ):
            # MLX treats a missing local path as an HF repo. Reject before loading
            # its runtime so this adapter can never trigger an implicit download.
            raise RuntimeError(
                "Modèle MLX local incomplet. Terminez son installation avant la transcription haute précision."
            )
        regions = _speech_regions(audio)
        if not regions:
            return []
        runtime, mx = _runtime()
        try:
            output = []
            has_text = False
            invalid_timestamps = False
            for region in regions:
                region_audio = audio[region["start"] : region["end"]]
                result = runtime.transcribe(
                    region_audio,
                    path_or_hf_repo=str(model_path),
                    verbose=None,
                    task="transcribe",
                    language=None if language == "auto" else language,
                    temperature=(0.0, 0.2, 0.4),
                    condition_on_previous_text=False,
                    word_timestamps=False,
                    compression_ratio_threshold=2.4,
                    logprob_threshold=-1.0,
                    no_speech_threshold=0.6,
                    fp16=True,
                )
                duration = len(region_audio) / _SAMPLE_RATE
                label = (
                    language
                    if language != "auto"
                    else result.get("language", "unknown")
                )
                region_has_text = bool(str(result.get("text", "")).strip())
                has_text = has_text or region_has_text
                region_output_start = len(output)
                for segment in result.get("segments", []):
                    text = str(segment.get("text", "")).strip()
                    if not text:
                        continue
                    has_text = True
                    start, end = (
                        _number(segment.get("start")),
                        _number(segment.get("end")),
                    )
                    if start is None or end is None:
                        invalid_timestamps = True
                        continue
                    start, end = max(0.0, start), min(duration, end)
                    if end <= start:
                        invalid_timestamps = True
                        continue
                    logprob = _number(segment.get("avg_logprob"))
                    silence = _number(segment.get("no_speech_prob"))
                    compression = _number(segment.get("compression_ratio"))
                    output.append(
                        {
                            "id": f"s{len(output) + 1}",
                            "start": round(
                                (offset + region["start"]) / _SAMPLE_RATE + start, 2
                            ),
                            "end": round(
                                (offset + region["start"]) / _SAMPLE_RATE + end, 2
                            ),
                            "text": text,
                            "speaker": "Intervenant non identifié",
                            "language": label,
                            "language_scope": "forced"
                            if language != "auto"
                            else "speech_region_detection",
                            "language_confidence": None,
                            "uncertain": logprob is None
                            or logprob < -0.5
                            or silence is None
                            or silence >= 0.6
                            or (compression is not None and compression > 2.4)
                            or label not in ("fr", "en"),
                        }
                    )
                if region_has_text and len(output) == region_output_start:
                    invalid_timestamps = True
            if invalid_timestamps or (has_text and not output):
                raise RuntimeError(
                    "Horodatages MLX invalides : transcription non publiée."
                )
            return output
        finally:
            # The library otherwise retains this model globally between calls.
            # Unload before returning to make room for local report/chat models.
            runtime.ModelHolder.model = None
            runtime.ModelHolder.model_path = None
            gc.collect()
            mx.clear_cache()
