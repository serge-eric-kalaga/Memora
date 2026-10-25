"""Optional local Parakeet adapter. No network download or eager MLX imports.

Native TDT timing, fixed benchmarked chunk30/overlap2. Language is unknown because
this runtime exposes no reliable language label. uncertain=True means unquantified
provider confidence, not proof every sentence is erroneous. No forced language.
Factory must serialize calls with the application-wide ASR/LLM inference lock.
"""

import gc
import hashlib
import importlib
import json
import math
import os
import threading
from pathlib import Path

DEFAULT_MODEL = Path(__file__).resolve().parents[3] / ".memora/models/parakeet-v3"
REPO = "mlx-community/parakeet-tdt-0.6b-v3"
REVISION = "ed2b7e8c15f9aaa0b5772e2efb986255eaef7e15"
WEIGHTS_SHA = "05e01c7f396c298cf7d23f61da7b504adeab698f0aaeafd9c82d198625464592"
WEIGHTS_BYTES = 2508288736
ASSETS = {
    "README.md": {
        "bytes": 1081,
        "sha256": "724e3ba46903986ff6caeb8fddb7495c06b5a7a8d908f11e43cc0a7e136b5e23",
    },
    "config.json": {
        "bytes": 244093,
        "sha256": "f320f1292511f34ec47f513755fe20fd01dbfc09a925d42730e66059a6e1ef4c",
    },
    "tokenizer.model": {
        "bytes": 360916,
        "sha256": "eacec2b0a77f336d4a2ca4a25a7047575d3c2b74de47e997f4c205126ed3135e",
    },
    "tokenizer.vocab": {
        "bytes": 101024,
        "sha256": "41130ff456706304a1adec782ccc9e003c4d417e8e324353d281be958cac4e17",
    },
    "vocab.txt": {
        "bytes": 46772,
        "sha256": "3cde1409fd78783a79b29ed4d32da57c746993856f7c8263bcb905d2e5839db7",
    },
}
_verify_lock = threading.Lock()
_verified = {}


def _fingerprint(model):
    result = []
    for name in ("memora-model.json", "model.safetensors", *ASSETS):
        path = model / name
        if not path.is_file() or path.resolve().parent != model:
            raise RuntimeError(
                "Modèle Parakeet incomplet ou fichier externe ; aucun téléchargement automatique."
            )
        st = path.stat()
        result.append(
            (name, st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)
        )
    return tuple(result)


def _sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while block := source.read(8 * 1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def verify_model(model):
    model = Path(model).expanduser().resolve()
    with _verify_lock:
        before = _fingerprint(model)
        if _verified.get(model) == before:
            return model
        meta = json.loads((model / "memora-model.json").read_text())
        expected = {
            "repo": REPO,
            "revision": REVISION,
            "bytes": WEIGHTS_BYTES,
            "sha256": WEIGHTS_SHA,
            "license": "CC-BY-4.0",
        }
        if any(meta.get(k) != v for k, v in expected.items()):
            raise RuntimeError("Provenance Parakeet incompatible ; modèle non chargé.")
        for name, item in {
            "model.safetensors": {"bytes": WEIGHTS_BYTES, "sha256": WEIGHTS_SHA},
            **ASSETS,
        }.items():
            path = model / name
            if path.stat().st_size != item["bytes"] or _sha(path) != item["sha256"]:
                raise RuntimeError("Intégrité Parakeet incorrecte ; modèle non chargé.")
        if _fingerprint(model) != before:
            raise RuntimeError(
                "Modèle Parakeet modifié pendant vérification ; réessayer."
            )
        _verified.clear()
        _verified[model] = before
    return model


def _runtime():
    return importlib.import_module("mlx.core"), importlib.import_module(
        "mlx_audio.stt"
    ).load


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
                "language": "unknown",
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
        raise ValueError(
            "Langue attendue auto/fr/en ; Parakeet ne force pas la langue."
        )
    if tail_seconds is not None and (
        not math.isfinite(float(tail_seconds)) or float(tail_seconds) <= 0
    ):
        raise ValueError("tail_seconds doit être positif et fini")
    model_path = verify_model(
        os.environ.get("MEMORA_PARAKEET_MODEL_PATH") or DEFAULT_MODEL
    )
    samples = decode_audio(path)
    import numpy as np

    if not np.all(np.isfinite(samples)):
        raise ValueError("Échantillons audio non finis.")
    offset = 0.0
    if tail_seconds is not None:
        skip = max(0, len(samples) - int(float(tail_seconds) * 16000))
        offset = skip / 16000
        samples = samples[skip:]
    if not len(samples):
        return []
    mx, load = _runtime()
    model = None
    try:
        # Pass verified local Path, never a Hub identifier or remote-code loader.
        model = load(model_path, model_type="parakeet")
        result = model.generate(
            mx.array(samples), chunk_duration=30.0, overlap_duration=2.0, verbose=False
        )
        return source_segments(result, offset, len(samples) / 16000)
    finally:
        del model
        gc.collect()
        mx.clear_cache()
