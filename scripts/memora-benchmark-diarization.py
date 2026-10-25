"""Synthetic multivoice CPU diarization benchmark, no user audio/microphone.

--prepare-only builds known TTS tracks and reference; --run explicitly infers.
DER uses20ms frames, optimal permutation, no collar and includes overlap.
Reference activity is deterministic per-source RMS>-45dBFS, not model VAD.
"""

import argparse
import hashlib
import importlib.util
import json
import subprocess
import time
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / ".memora/qa/diarization"
RATE = 16000


def write_wav(path, values):
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(RATE)
        handle.writeframes((np.clip(values, -1, 1) * 32767).astype("<i2").tobytes())


def tts(voice, text, index):
    from faster_whisper.audio import decode_audio

    path = FOLDER / f"tts-{index}.aiff"
    subprocess.run(
        ["say", "-v", voice, "-r", "175", "-o", str(path), text],
        check=True,
        capture_output=True,
    )
    audio = decode_audio(str(path), sampling_rate=RATE)
    if len(audio) < RATE // 2 or np.sqrt(np.mean(audio**2)) < 1e-5:
        raise ValueError(
            "Synthetic TTS source is empty/silent; benchmark reference invalid."
        )
    return audio


def reference_activity(track):
    result = []
    for start in range(0, len(track), 320):
        values = track[start : start + 320]
        if len(values) and np.sqrt(np.mean(values**2)) > 10 ** (-45 / 20):
            result.append(start // 320)
    return result


def prepare():
    FOLDER.mkdir(parents=True, exist_ok=True)
    utterances = [
        (
            "A",
            "Thomas",
            "Nous allons examiner le calendrier du projet et vérifier les documents avant la prochaine réunion.",
        ),
        (
            "B",
            "Amélie",
            "Je préparerai les tableaux lundi. Le budget reste ouvert et nous déciderons après la revue des chiffres.",
        ),
        (
            "B",
            "Amélie",
            "Nous avons encore plusieurs questions sur les accès et la disponibilité de notre équipe.",
        ),
        (
            "A",
            "Thomas",
            "Les mêmes participants se retrouveront vendredi pour confirmer les étapes et répartir les travaux.",
        ),
        (
            "A",
            "Thomas",
            "Je souhaite conserver la version précédente du dossier pour pouvoir comparer les propositions.",
        ),
        (
            "B",
            "Amélie",
            "La décision finale sera annoncée après la lecture des observations et la correction des erreurs.",
        ),
        (
            "C",
            "Samantha",
            "We will review the latest figures before the next meeting. The final decision has not been made yet.",
        ),
    ]
    clips = [
        tts(voice, text, index) for index, (_, voice, text) in enumerate(utterances)
    ]
    cases = []
    for name, indices, noisy, overlap in [
        ("two-fr", [0, 1, 2, 3, 4, 5], False, False),
        ("gain-noise", [0, 1, 2, 3, 4, 5], True, False),
        ("fr-en", [0, 3, 6, 4, 6], False, False),
        ("overlap", [0, 1, 3, 5], False, True),
        ("three-voices", [0, 1, 6, 3, 2, 6], False, False),
    ]:
        cursor = int(0.5 * RATE)
        placements = []
        segments = []
        for number, index in enumerate(indices):
            speaker, _, text = utterances[index]
            if overlap and number == len(indices) - 1:
                cursor -= int(1.4 * RATE)
            clip = clips[index].copy()
            if noisy and speaker == "A":
                clip *= 0.22
            placements.append((speaker, cursor, clip))
            segments.append(
                {
                    "id": f"s{number + 1}",
                    "start": cursor / RATE,
                    "end": (cursor + len(clip)) / RATE,
                    "text": text,
                    "speaker": "Intervenant non identifié",
                }
            )
            cursor += len(clip) + int(0.35 * RATE)
        tracks = {
            speaker: np.zeros(cursor + int(0.5 * RATE), dtype=np.float32)
            for speaker, _, _ in placements
        }
        for speaker, start, clip in placements:
            tracks[speaker][start : start + len(clip)] += clip
        mixed = sum(tracks.values())
        if noisy:
            rms = np.sqrt(np.mean(mixed**2))
            mixed += (
                np.random.default_rng(140)
                .normal(0, rms / 10, len(mixed))
                .astype(np.float32)
            )
        path = FOLDER / f"{name}.wav"
        write_wav(path, mixed)
        cases.append(
            {
                "id": name,
                "path": str(path),
                "duration": len(mixed) / RATE,
                "segments": segments,
                "reference_activity": {
                    s: reference_activity(v) for s, v in tracks.items()
                },
                "expected_speakers": len(tracks),
            }
        )
    for name, noise in [("silence", False), ("noise-only", True)]:
        audio = np.zeros(RATE * 4, dtype=np.float32)
        if noise:
            audio = (
                np.random.default_rng(7).normal(0, 0.001, len(audio)).astype(np.float32)
            )
        path = FOLDER / f"{name}.wav"
        write_wav(path, audio)
        cases.append(
            {
                "id": name,
                "path": str(path),
                "duration": 4.0,
                "segments": [],
                "reference_activity": {},
                "expected_speakers": 0,
            }
        )
    (FOLDER / "references.json").write_text(
        json.dumps(
            {
                "synthetic_only": True,
                "reference": "TTS isolated source tracks,20ms RMS>-45dBFS; no collar",
                "cases": cases,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    print("Synthetic fixtures prepared", len(cases), flush=True)


def score(reference, turns, duration):
    from scipy.optimize import linear_sum_assignment

    frames = int(np.ceil(duration / 0.02))
    refs = reference["reference_activity"]
    refids = sorted(refs)
    hypids = sorted({t["speaker_id"] for t in turns if t["speaker_id"]})
    rsets = [set() for _ in range(frames)]
    hsets = [set() for _ in range(frames)]
    for ident, active in refs.items():
        for i in active:
            if i < frames:
                rsets[i].add(ident)
    for turn in turns:
        if turn["speaker_id"]:
            for i in range(
                int(turn["start"] / 0.02), min(frames, int(np.ceil(turn["end"] / 0.02)))
            ):
                hsets[i].add(turn["speaker_id"])
    matrix = np.zeros((len(refids), len(hypids)))
    for i, ref in enumerate(refids):
        for j, hyp in enumerate(hypids):
            matrix[i, j] = sum(
                ref in r and hyp in h for r, h in zip(rsets, hsets, strict=True)
            )
    mapping = {}
    if len(refids) and len(hypids):
        left, right = linear_sum_assignment(-matrix)
        mapping = {hypids[j]: refids[i] for i, j in zip(left, right, strict=True)}
    missed = false = confusion = total = 0
    for r, h in zip(rsets, hsets, strict=True):
        correct = len(r & {mapping.get(x) for x in h})
        missed += max(len(r) - len(h), 0)
        false += max(len(h) - len(r), 0)
        confusion += min(len(r), len(h)) - correct
        total += len(r)
    return {
        "der": (missed + false + confusion) / total if total else None,
        "miss_seconds": missed * 0.02,
        "false_alarm_seconds": false * 0.02,
        "confusion_seconds": confusion * 0.02,
        "reference_speaker_seconds": total * 0.02,
        "hypothesis_mapping": mapping,
        "negative_no_speakers": not turns if not total else None,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--run", action="store_true")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "agents/logs/diarization-benchmark-v1.json",
    )
    parser.add_argument("--cases", nargs="*")
    parser.add_argument("--num-speakers", type=int)
    parser.add_argument("--references", type=Path, default=FOLDER / "references.json")
    parser.add_argument("--cluster-distance", type=float)
    args = parser.parse_args()
    if args.prepare_only:
        prepare()
        return
    if not args.run:
        print("No inference. Use --prepare-only then --run.")
        return
    if args.output.exists():
        raise ValueError("Refusing to overwrite evidence")
    path = ROOT / "backend/api/memora/diarization.py"
    spec = importlib.util.spec_from_file_location("diarization_probe", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if args.cluster_distance is not None:
        module._CLUSTER_DISTANCE = args.cluster_distance
    reference_path = args.references
    references = json.loads(reference_path.read_text())
    output = {
        "cluster_distance": module._CLUSTER_DISTANCE,
        "code_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "reference_sha256": hashlib.sha256(reference_path.read_bytes()).hexdigest(),
        "synthetic_only": True,
        "metric": "DER20ms no collar, overlap included, optimal permutation; synthetic energy reference",
        "results": [],
    }
    for case in references["cases"]:
        if args.cases and case["id"] not in args.cases:
            continue
        started = time.monotonic()
        result = module.diarize(
            Path(case["path"]), case["segments"], num_speakers=args.num_speakers
        )
        seconds = time.monotonic() - started
        row = {
            "case": case["id"],
            "seconds": round(seconds, 3),
            "rtf": round(seconds / case["duration"], 4),
            "duration": case["duration"],
            "expected_speakers": case["expected_speakers"],
            "result": result,
            "metrics": score(case, result["turns"], case["duration"]),
        }
        output["results"].append(row)
        args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2))
        print(
            case["id"],
            "seconds",
            row["seconds"],
            "speaker_count",
            result["metadata"]["speaker_count"],
            "DER",
            row["metrics"]["der"],
            flush=True,
        )


if __name__ == "__main__":
    main()
