"""Generate a synthetic long meeting; infer only with explicit --infer after SHA verification.

Generation uses only fixed synthetic PCM fixtures and streams output to disk.
A long file accepted here does not establish that available RAM can transcribe it.
"""

import argparse
import hashlib
import importlib.util
import json
import os
import re
import sys
import time
import unicodedata
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "backend/test/fixtures/memora"
DESTINATION = ROOT / ".memora/qa/long.wav"
FINAL_PHRASE = "Aujourd'hui nous allons parler du langage python."
RATE = 16000


def normalize(text):
    return " ".join(
        re.sub(r"[^\w\s]", " ", unicodedata.normalize("NFC", text.casefold())).split()
    )


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while block := source.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def read_fixture(name):
    path = FIXTURES / name
    with wave.open(str(path), "rb") as source:
        if (
            source.getnchannels() != 1
            or source.getsampwidth() != 2
            or source.getframerate() != RATE
            or source.getcomptype() != "NONE"
        ):
            raise RuntimeError("Fixture synthétique attendue mono PCM16bit16k.")
        frames = source.readframes(source.getnframes())
    return frames, {
        "fixture": name,
        "sha256": sha256(path),
        "samples": len(frames) // 2,
    }


def generate(minutes):
    if not 1 <= minutes <= 120:
        raise ValueError("Durée de génération entre 1 et 120 minutes requise.")
    french, french_info = read_fixture("french.wav")
    english, english_info = read_fixture("english.wav")
    final, final_info = read_fixture("python-sentence.wav")
    gap = b"\0\0" * int(0.3 * RATE)
    cycle = french + gap + english + gap
    requested_samples = round(minutes * 60 * RATE)
    before_final = requested_samples - len(final) // 2
    cycles = (before_final - int(0.5 * RATE)) // (len(cycle) // 2)
    padding_samples = before_final - cycles * (len(cycle) // 2)
    DESTINATION.parent.mkdir(parents=True, exist_ok=True)
    staged = DESTINATION.with_suffix(".wav.tmp")
    with wave.open(str(staged), "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(RATE)
        for _ in range(cycles):
            target.writeframesraw(cycle)
        # No fixture is cut mid-word; the residual target interval is silence.
        target.writeframesraw(b"\0\0" * padding_samples)
        target.writeframesraw(final)
    staged.replace(DESTINATION)
    metadata = {
        "synthetic_only": True,
        "audio": ".memora/qa/long.wav",
        "requested_minutes": minutes,
        "actual_seconds": requested_samples / RATE,
        "audio_sha256": sha256(DESTINATION),
        "file_bytes": DESTINATION.stat().st_size,
        "whole_fr_en_cycles": cycles,
        "inter_fixture_silence_seconds": 0.3,
        "silence_before_final_seconds": padding_samples / RATE,
        "final_phrase_expected": FINAL_PHRASE,
        "final_phrase_start_seconds": before_final / RATE,
        "fixtures": [french_info, english_info, final_info],
        "generation_policy": "Whole French + short silence + whole English + short silence repeated; residual interval silence; final Python sentence. No speech cut to hit target length.",
    }
    (DESTINATION.parent / "long-source.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2)
    )
    return metadata


def load_benchmark():
    path = ROOT / "scripts/memora-benchmark-mlx.py"
    spec = importlib.util.spec_from_file_location(
        "memora_long_verified_benchmark", path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def infer(metadata, language):
    # Reuse the downloader-manifest/full-SHA gate; do not duplicate verification.
    benchmark = load_benchmark()
    model = (
        Path(
            os.environ.get(
                "MEMORA_MLX_MODEL_PATH", ROOT / ".memora/models/mlx-large-v3-turbo"
            )
        )
        .expanduser()
        .resolve()
    )
    manifest = benchmark.verify_model(model)
    os.environ.update(
        {
            "MEMORA_MLX_MODEL_PATH": str(model),
            "HF_HUB_OFFLINE": "1",
            "HF_HUB_DISABLE_TELEMETRY": "1",
            "TRANSFORMERS_OFFLINE": "1",
        }
    )
    adapter = benchmark.load_file(
        "memora_long_mlx_adapter", ROOT / "backend/api/memora/asr_mlx.py"
    )
    started = time.monotonic()
    segments = adapter.transcribe(DESTINATION, language=language)
    elapsed = time.monotonic() - started
    full_text = normalize(" ".join(segment["text"] for segment in segments))
    final_start = metadata["final_phrase_start_seconds"]
    near_tail = normalize(
        " ".join(
            segment["text"] for segment in segments if segment["end"] >= final_start - 5
        )
    )
    maximum_end = max((segment["end"] for segment in segments), default=None)
    output = {
        "generation": metadata,
        "model_manifest_sha256_verified": manifest,
        "language_requested": language,
        "wall_seconds": round(elapsed, 4),
        "rtf": round(elapsed / metadata["actual_seconds"], 4),
        "segment_count": len(segments),
        "first_segment_start": segments[0]["start"] if segments else None,
        "last_segment_end": segments[-1]["end"] if segments else None,
        "max_segment_end": maximum_end,
        "segments_in_first_30_seconds": sum(
            segment["start"] < 30 for segment in segments
        ),
        "segments_in_last_30_seconds": sum(
            segment["end"] >= metadata["actual_seconds"] - 30 for segment in segments
        ),
        "beginning_marker_found": "nous décidons de lancer le projet" in full_text,
        "final_phrase_found_anywhere": normalize(FINAL_PHRASE) in full_text,
        "final_phrase_found_near_end": normalize(FINAL_PHRASE) in near_tail,
        "tail_reached_by_timestamps": maximum_end is not None
        and maximum_end >= final_start,
        "uncertain_segments": sum(
            bool(segment.get("uncertain")) for segment in segments
        ),
        "languages": sorted(
            {segment.get("language", "unknown") for segment in segments}
        ),
        "segments_synthetic": segments,
        "limitations": "Markers/timestamps are coverage diagnostics, not proof every repeated word is correct. A repeated synthetic meeting does not validate a natural two-hour meeting. RTF includes decode, VAD, model load and cleanup; auto language is dominant within each VAD speech region, not per-word confidence. Full-file decoding has memory costs growing with duration.",
    }
    path = ROOT / "agents/logs/benchmark-long.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(output, ensure_ascii=False, indent=2))
    print(
        json.dumps(
            {
                key: output[key]
                for key in (
                    "segment_count",
                    "first_segment_start",
                    "last_segment_end",
                    "max_segment_end",
                    "final_phrase_found_anywhere",
                    "final_phrase_found_near_end",
                    "wall_seconds",
                    "rtf",
                )
            },
            ensure_ascii=False,
        ),
        flush=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--minutes", type=float, default=5)
    parser.add_argument(
        "--infer",
        action="store_true",
        help="Explicit real inference; requires complete verified local model",
    )
    parser.add_argument("--language", choices=("auto", "fr", "en"), default="auto")
    try:
        args = parser.parse_args()
        data = generate(args.minutes)
        print(
            f"Synthetic audio generated: {data['actual_seconds']} seconds, {data['whole_fr_en_cycles']} full FR/EN cycles; .memora/qa/long.wav",
            flush=True,
        )
        if args.infer:
            infer(data, args.language)
        else:
            print("Generation only; no AI inference or model download.", flush=True)
    except (RuntimeError, OSError, ValueError, ImportError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(2)
