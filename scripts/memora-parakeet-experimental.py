"""Benchmark-only Parakeet adapter; no imports/loads of MLX until transcribe().

Run exclusively with .memora/asr-lab/bin/python after explicit GPU authorization.
Parakeet does not support a forced fr/en parameter here: language is accepted for
benchmark API compatibility but never fabricated in output. Not production wired.
"""

import gc
import importlib.util
import math
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / ".memora/models/parakeet-v3"


def source_segments(result, offset, duration):
    output = []
    for sentence in result.sentences:
        text = sentence.text.strip()
        if not text:
            continue
        start, end = float(sentence.start), float(sentence.end)
        if (
            not all(math.isfinite(v) for v in (start, end))
            or start < 0
            or start >= duration
            or end <= start
            or end > duration + 0.5
        ):
            raise RuntimeError("Invalid native Parakeet timestamps; result rejected")
        output.append(
            {
                "id": f"s{len(output) + 1}",
                "start": round(offset + start, 3),
                "end": round(offset + min(end, duration), 3),
                "text": text,
                "speaker": "Intervenant non identifié",
                "language": None,
                "language_confidence": None,
                "uncertain": True,
            }
        )
    if result.text.strip() and not output:
        raise RuntimeError("Parakeet text without native timestamps; result rejected")
    return output


def decode_audio(path):
    """Decode actual container bytes, including browser WebM/Opus with .bin suffix."""
    import av
    import numpy as np

    output = []
    resampler = av.AudioResampler(format="fltp", layout="mono", rate=16000)
    with av.open(str(path)) as container:
        for frame in container.decode(audio=0):
            for converted in resampler.resample(frame):
                output.append(converted.to_ndarray().reshape(-1))
        for converted in resampler.resample(None):
            output.append(converted.to_ndarray().reshape(-1))
    return (
        np.concatenate(output).astype(np.float32, copy=False)
        if output
        else np.empty(0, dtype=np.float32)
    )


def transcribe(path: Path, tail_seconds=None, language="auto"):
    if language not in ("auto", "fr", "en"):
        raise ValueError("Expected auto/fr/en (Parakeet ignores forced language)")
    if (
        os.environ.get("HF_HUB_OFFLINE") != "1"
        or os.environ.get("TRANSFORMERS_OFFLINE") != "1"
    ):
        raise RuntimeError(
            "Benchmark requires explicit HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1"
        )
    spec = importlib.util.spec_from_file_location(
        "parakeet_verify", ROOT / "scripts/memora-download-parakeet.py"
    )
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)
    checker.verify_local(MODEL)
    samples = decode_audio(path)
    offset = 0.0
    if tail_seconds is not None:
        if not math.isfinite(float(tail_seconds)) or tail_seconds <= 0:
            raise ValueError("tail_seconds must be positive and finite")
        skip = max(0, len(samples) - int(tail_seconds * 16000))
        offset = skip / 16000
        samples = samples[skip:]
    if not len(samples):
        return []
    import mlx.core as mx
    from mlx_audio.stt import load

    model = None
    try:
        model = load(MODEL)
        result = model.generate(
            mx.array(samples), chunk_duration=30.0, overlap_duration=2.0, verbose=False
        )
        return source_segments(result, offset, len(samples) / 16000)
    finally:
        del model
        gc.collect()
        mx.clear_cache()
