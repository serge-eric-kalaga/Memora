"""Synthetic-only language drift comparison. No app/personal audio or configuration mutation."""

import argparse
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import time
import unicodedata
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / ".memora/qa/asr-language-drift"
CORPUS = ROOT / "backend/test/fixtures/memora/asr-language-drift-v1.json"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def normalized(text):
    return " ".join(
        re.sub(r"[^\w\s]", " ", unicodedata.normalize("NFC", text.casefold())).split()
    )


def distance(a, b):
    row = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        nxt = [i]
        for j, y in enumerate(b, 1):
            nxt.append(min(row[j] + 1, nxt[-1] + 1, row[j - 1] + (x != y)))
        row = nxt
    return row[-1]


def prepare():
    from faster_whisper.audio import decode_audio

    corpus = json.loads(CORPUS.read_text())
    cases = []
    clips = []
    for case in corpus["cases"]:
        path = FOLDER / (case["id"] + ".aiff")
        subprocess.run(
            ["say", "-v", corpus["voice"], "-r", "165", "-o", str(path), case["text"]],
            check=True,
            capture_output=True,
        )
        audio = decode_audio(str(path), sampling_rate=16000)
        if len(audio) < 8000 or np.max(np.abs(audio)) < 0.001:
            raise ValueError("Invalid empty TTS")
        clips.append(audio)
        cases.append({**case, "path": str(path), "duration": len(audio) / 16000})
    parts = []
    texts = []
    length = 0
    index = 0
    while length + len(clips[index % 3]) + 6400 < 90 * 16000:
        parts.extend([clips[index % 3], np.zeros(6400, dtype=np.float32)])
        texts.append(corpus["cases"][index % 3]["text"])
        length += len(clips[index % 3]) + 6400
        index += 1
    audio = np.concatenate([*parts, np.zeros(90 * 16000 - length, dtype=np.float32)])
    path = FOLDER / "french-long90.wav"
    with wave.open(str(path), "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(16000)
        target.writeframes((audio * 32767).astype("<i2").tobytes())
    cases.append(
        {
            "id": "french-long90",
            "path": str(path),
            "text": " ".join(texts),
            "duration": 90.0,
        }
    )
    (FOLDER / "references.json").write_text(
        json.dumps(
            {
                "corpus_sha256": hashlib.sha256(CORPUS.read_bytes()).hexdigest(),
                "cases": cases,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    print("Synthetic references prepared, no inference", flush=True)


def verify_mlx(folder):
    manifest = json.loads((folder / "memora-model.json").read_text())
    weights = folder / (
        "weights.safetensors"
        if (folder / "weights.safetensors").exists()
        else "weights.npz"
    )
    digest = hashlib.sha256()
    with weights.open("rb") as source:
        while block := source.read(8 * 1024 * 1024):
            digest.update(block)
    assert (
        digest.hexdigest() == manifest["sha256"]
        and weights.stat().st_size == manifest["bytes"]
    )
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--cases", nargs="*")
    parser.add_argument(
        "--engines", nargs="*", default=["parakeet", "turbo-fr", "full-fr"]
    )
    parser.add_argument(
        "--output", type=Path, default=ROOT / ".agents/logs/asr-language-drift-v1.json"
    )
    args = parser.parse_args()
    if args.prepare:
        prepare()
        return
    if not args.run:
        print("No inference. Use --prepare, then --run explicitly.")
        return
    if args.output.exists():
        raise ValueError("Refusing overwrite")
    os.environ.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1")
    reference = FOLDER / "references.json"
    cases = json.loads(reference.read_text())["cases"]
    output = {
        "synthetic_only": True,
        "reference_sha256": hashlib.sha256(reference.read_bytes()).hexdigest(),
        "results": [],
    }
    for engine in args.engines:
        if engine == "parakeet":
            module = load("drift_parakeet", ROOT / "backend/api/memora/asr_parakeet.py")
            module.verify_model(ROOT / ".memora/models/parakeet-v3")
            model = "parakeet-v3"
        else:
            module = load("drift_whisper", ROOT / "backend/api/memora/asr_mlx.py")
            model = "mlx-large-v3-turbo" if engine == "turbo-fr" else "mlx-large-v3"
            folder = ROOT / ".memora/models" / model
            verify_mlx(folder)
            os.environ["MEMORA_MLX_MODEL_PATH"] = str(folder)
            os.environ["MEMORA_MLX_FR_MODEL_PATH"] = str(folder)
        for case in cases:
            if args.cases and case["id"] not in args.cases:
                continue
            started = time.monotonic()
            segments = module.transcribe(Path(case["path"]), language="fr")
            seconds = time.monotonic() - started
            text = " ".join(s["text"] for s in segments)
            expected = normalized(case["text"])
            actual = normalized(text)
            row = {
                "engine": engine,
                "model": model,
                "case": case["id"],
                "requested_language": "fr",
                "expected_synthetic": case["text"],
                "obtained_synthetic": text,
                "wer_normalized": distance(expected.split(), actual.split())
                / len(expected.split()),
                "seconds": round(seconds, 3),
                "rtf": round(seconds / case["duration"], 4),
                "segments": segments,
                "adapter_sha256": hashlib.sha256(
                    Path(module.__file__).read_bytes()
                ).hexdigest(),
            }
            output["results"].append(row)
            args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2))
            print(engine, case["id"], row["seconds"], row["wer_normalized"], flush=True)


if __name__ == "__main__":
    main()
