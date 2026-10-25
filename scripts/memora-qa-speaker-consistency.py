"""Exercise real local speaker-count consistency on synthetic audio only.

Prepare the existing diarization and diarization-reserve corpora first with their
preparation scripts. This probe derives monologues and channel variants from
those synthetic TTS clips; it never reads meeting storage or private audio.
Run: backend/.venv/bin/python scripts/memora-qa-speaker-consistency.py
The output distinguishes successful counts, abstentions and remaining errors.
"""

import argparse
import hashlib
import importlib.util
import json
import os
import secrets
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / ".memora/qa/speaker-consistency"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def prepare_cases(bench):
    from faster_whisper.audio import decode_audio
    from scipy.signal import butter, sosfilt

    FOLDER.mkdir(parents=True, exist_ok=True)
    baseline = []
    for corpus in ("diarization", "diarization-reserve"):
        reference = ROOT / f".memora/qa/{corpus}/references.json"
        content = json.loads(reference.read_text())
        if not content.get("synthetic_only", True):
            raise ValueError("Only the prepared synthetic corpora are accepted")
        baseline.extend(content["cases"])
    variants = []
    for voice, corpus, indices in (
        ("thomas", "diarization", [0, 3, 4]),
        ("amelie", "diarization", [1, 2, 5]),
        ("daniel", "diarization-reserve", [0, 3]),
        ("karen", "diarization-reserve", [1, 4]),
        ("eddy", "diarization-reserve", [2]),
    ):
        clips = [
            decode_audio(
                str(ROOT / f".memora/qa/{corpus}/tts-{index}.aiff"),
                sampling_rate=bench.RATE,
            )
            for index in indices
        ]
        conditions = ["clean"]
        if voice != "eddy":
            conditions += [
                "short-context",
                "channel-change",
                "loudness-change",
                "noise10",
            ]
        for condition in conditions:
            pieces = []
            segments = []
            cursor = 0
            for index, original in enumerate(clips):
                waveform = original.copy()
                if condition == "channel-change" and index % 2:
                    waveform = sosfilt(
                        butter(
                            4,
                            [300, 2200],
                            fs=bench.RATE,
                            btype="bandpass",
                            output="sos",
                        ),
                        waveform,
                    ).astype(np.float32)
                elif condition == "loudness-change" and index % 2:
                    waveform *= 0.08
                elif condition == "noise10" and index % 2:
                    waveform += (
                        np.random.default_rng(25)
                        .normal(
                            0,
                            np.sqrt(np.mean(waveform**2)) / np.sqrt(10),
                            len(waveform),
                        )
                        .astype(np.float32)
                    )
                chunks = (
                    [
                        waveform[start : start + bench.RATE]
                        for start in range(0, len(waveform), bench.RATE)
                    ]
                    if condition == "short-context"
                    else [waveform]
                )
                for chunk in chunks:
                    segments.append(
                        {
                            "id": f"s{len(segments) + 1}",
                            "start": cursor / bench.RATE,
                            "end": (cursor + len(chunk)) / bench.RATE,
                            "text": f"Extrait synthétique de contrôle {len(segments) + 1}.",
                            "speaker": "Intervenant non identifié",
                        }
                    )
                    silence = np.zeros(
                        4000 if condition == "short-context" else 8000, dtype=np.float32
                    )
                    pieces.extend([chunk, silence])
                    cursor += len(chunk) + len(silence)
            audio = np.concatenate(pieces)
            ident = f"mono-{voice}" if condition == "clean" else f"{voice}-{condition}"
            path = FOLDER / f"{ident}.wav"
            bench.write_wav(path, audio)
            case = {
                "id": ident,
                "path": str(path),
                "segments": segments,
                "duration": len(audio) / bench.RATE,
                "expected_speakers": 1,
            }
            (baseline if condition == "clean" else variants).append(case)
    return baseline, variants


def unchanged(source, result):
    keys = ("id", "start", "end", "text")
    return [tuple(segment.get(key) for key in keys) for segment in source] == [
        tuple(segment.get(key) for key in keys) for segment in result
    ]


def run_case(engine, bench, case, known=None):
    started = time.monotonic()
    row = {
        "case": case["id"],
        "expected_speakers": case["expected_speakers"],
        "known_speakers": known,
    }
    try:
        result = engine.diarize(
            Path(case["path"]), case["segments"], num_speakers=known
        )
        count = result["metadata"]["speaker_count"]
        row.update(
            status="correct_count"
            if count == case["expected_speakers"]
            else "remaining_count_error",
            detected_speakers=count,
            source_preserved=unchanged(case["segments"], result["segments"]),
            assigned_segments=sum(
                bool(segment.get("speaker_id")) for segment in result["segments"]
            ),
            total_segments=len(result["segments"]),
            count_policy=result["metadata"].get("count_policy"),
        )
        if case.get("reference_activity"):
            row["metrics"] = bench.score(case, result["turns"], case["duration"])
    except engine.DiarizationError as error:
        row.update(status="abstained", reason=str(error))
    row["seconds"] = round(time.monotonic() - started, 4)
    row["rtf"] = round(row["seconds"] / case["duration"], 4)
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / ".agents/logs/speaker-consistency-real.json",
    )
    parser.add_argument(
        "--engine", choices=["resemblyzer", "ecapa-tdnn"], default="resemblyzer"
    )
    parser.add_argument("--include-holdout", action="store_true")
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Refusing to overwrite evidence; select another output path")
    engine_path = ROOT / "backend/api/memora/diarization.py"
    os.environ.update(
        APP_NAME="Synthetic consistency QA",
        ADMINS_EMAIL="synthetic@example.test",
        SECRET_KEY=secrets.token_hex(32),
        JWT_SECRET=secrets.token_hex(32),
        ALGORITHM="HS256",
        DATABASE_URL="sqlite:///:memory:",
        INITIALISE_DATABASE="false",
        CACHE_ENABLED="false",
        RATE_LIMIT_ENABLED="false",
        EMAIL_HOST="127.0.0.1",
        EMAIL_PORT="1025",
        EMAIL_DOMAIN="synthetic@localhost",
        MEMORA_DISABLE_WORKER="1",
        MEMORA_DIARIZATION_ENGINE=args.engine,
    )
    sys.path.insert(0, str(ROOT / "backend"))
    from api.memora import diarization as engine

    bench = load_module(
        "speaker_consistency_bench", ROOT / "scripts/memora-benchmark-diarization.py"
    )
    baseline, variants = prepare_cases(bench)
    output = {
        "synthetic_only": True,
        "engine": args.engine,
        "code_sha256": hashlib.sha256(engine_path.read_bytes()).hexdigest(),
        "scope": "16 baseline cases, 16 altered-channel monologues, explicit one-speaker recovery",
        "baseline": [],
        "variants_auto": [],
        "variants_known_one": [],
    }
    started = time.monotonic()
    for group, cases, known in (
        ("baseline", baseline, None),
        ("variants_auto", variants, None),
        ("variants_known_one", variants, 1),
    ):
        for case in cases:
            row = run_case(engine, bench, case, known)
            output[group].append(row)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2))
            print(
                group,
                row["case"],
                row["status"],
                row.get("detected_speakers"),
                row["seconds"],
                flush=True,
            )
    if args.include_holdout:
        references = json.loads(
            (ROOT / ".memora/qa/ecapa-holdout/references.json").read_text()
        )
        if references.get("synthetic_only") is not True:
            raise ValueError("Holdout must be synthetic")
        output["holdout"] = [
            run_case(engine, bench, case) for case in references["cases"]
        ]
    output["seconds_total"] = round(time.monotonic() - started, 4)
    output["checks"] = {
        "baseline_count": len(baseline) == 16
        and all(row["status"] == "correct_count" for row in output["baseline"]),
        "successful_sources_preserved": all(
            row.get("source_preserved", True)
            for group in ("baseline", "variants_auto", "variants_known_one")
            for row in output[group]
        ),
        "known_one_count": len(variants) == 16
        and all(
            row["status"] == "correct_count" for row in output["variants_known_one"]
        ),
    }
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2))
    print(json.dumps(output["checks"]), flush=True)
    if not all(output["checks"].values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
