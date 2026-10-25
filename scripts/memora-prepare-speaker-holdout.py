"""Prepare or validate the frozen synthetic ECAPA holdout, without inference.

Uses only installed macOS TTS voices and the versioned synthetic fixture. Existing
compatible references are checked and preserved. Incompatible evidence is never
overwritten. --check-only does not generate audio or initialize any model.
"""

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "backend/test/fixtures/memora/ecapa-holdout-v1.json"


def definitions(fixture):
    return [
        [
            case["id"],
            [[entry["speaker"], entry["utterance"]] for entry in case["entries"]],
            case["condition"],
        ]
        for case in fixture["cases"]
    ]


def check_existing(folder, fixture, digest):
    path = folder / "references.json"
    reference = json.loads(path.read_text())
    compatible = (
        reference.get("synthetic_only") is True
        and reference.get("threshold_fixed_before_generation")
        == fixture["threshold_fixed_before_generation"]
        and reference.get("voices") == fixture["voices"]
        and reference.get("definitions") == definitions(fixture)
        and reference.get("fixture_sha256", digest) == digest
    )
    if not compatible:
        raise ValueError(
            "Existing references differ from the frozen fixture; refusing to overwrite"
        )
    by_id = {case["id"]: case for case in reference["cases"]}
    if len(by_id) != len(fixture["cases"]):
        raise ValueError("The prepared reference case count does not match the fixture")
    for definition in fixture["cases"]:
        case = by_id[definition["id"]]
        expected = len({entry["speaker"] for entry in definition["entries"]})
        if case["expected_speakers"] != expected:
            raise ValueError(
                "The prepared speaker count differs from the frozen fixture"
            )
        audio = folder / f"{case['id']}.wav"
        if not audio.is_file() or audio.stat().st_size <= 44:
            raise ValueError("A prepared synthetic WAV is missing or empty")
        if definition["condition"] not in {"short", "interrupted"}:
            texts = [
                fixture["utterances"][entry["speaker"]][entry["utterance"]]
                for entry in definition["entries"]
            ]
            if texts != [segment["text"] for segment in case["segments"]]:
                raise ValueError(
                    "The prepared synthetic text differs from the frozen fixture"
                )
        expected_digest = case.get("audio_sha256")
        if (
            expected_digest
            and hashlib.sha256(audio.read_bytes()).hexdigest() != expected_digest
        ):
            raise ValueError("Prepared synthetic audio integrity check failed")
    return (
        len(by_id),
        "fixture_hash"
        if "fixture_sha256" in reference
        else "legacy_definitions_and_text",
    )


def prepare(folder, fixture, digest):
    from scipy.signal import butter, sosfilt

    spec = importlib.util.spec_from_file_location(
        "diarization_benchmark", ROOT / "scripts/memora-benchmark-diarization.py"
    )
    bench = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bench)
    bench.FOLDER = folder
    folder.mkdir(parents=True, exist_ok=True)
    if any(folder.iterdir()):
        raise ValueError(
            "Output directory contains unreferenced evidence; select a new directory"
        )
    clips = {}
    index = 0
    for speaker, texts in fixture["utterances"].items():
        for number, text in enumerate(texts):
            clips[speaker, number] = bench.tts(fixture["voices"][speaker], text, index)
            index += 1
    cases = []
    for definition in fixture["cases"]:
        condition = definition["condition"]
        placements, segments = [], []
        cursor = bench.RATE // 2
        for index, entry in enumerate(definition["entries"]):
            speaker, number = entry["speaker"], entry["utterance"]
            waveform = clips[speaker, number].copy()
            if condition == "channel" and index % 2:
                waveform = (
                    sosfilt(
                        butter(
                            4,
                            [300, 2200],
                            fs=bench.RATE,
                            btype="bandpass",
                            output="sos",
                        ),
                        waveform,
                    ).astype(np.float32)
                    * 0.2
                )
                waveform += (
                    np.random.default_rng(20261025 + index)
                    .normal(
                        0,
                        np.sqrt(np.mean(waveform**2)) / (10 ** (15 / 20)),
                        len(waveform),
                    )
                    .astype(np.float32)
                )
            if condition == "short":
                waveform = waveform[: int(1.2 * bench.RATE)]
            chunks = (
                [
                    waveform[start : start + int(0.8 * bench.RATE)]
                    for start in range(0, len(waveform), int(0.8 * bench.RATE))
                ]
                if condition == "interrupted"
                else [waveform]
            )
            for chunk in chunks:
                placements.append((speaker, cursor, chunk))
                segments.append(
                    {
                        "id": f"s{len(segments) + 1}",
                        "start": cursor / bench.RATE,
                        "end": (cursor + len(chunk)) / bench.RATE,
                        "text": fixture["utterances"][speaker][number]
                        if condition not in {"short", "interrupted"}
                        else "Extrait synthétique volontairement interrompu.",
                        "speaker": "Intervenant non identifié",
                    }
                )
                cursor += len(chunk) + int(0.3 * bench.RATE)
        tracks = {
            speaker: np.zeros(cursor + bench.RATE // 2, dtype=np.float32)
            for speaker, _, _ in placements
        }
        for speaker, start, clip in placements:
            tracks[speaker][start : start + len(clip)] += clip
        waveform = sum(tracks.values())
        path = folder / f"{definition['id']}.wav"
        bench.write_wav(path, waveform)
        cases.append(
            {
                "id": definition["id"],
                "path": str(path),
                "expected_speakers": len(tracks),
                "duration": len(waveform) / bench.RATE,
                "segments": segments,
                "reference_activity": {
                    speaker: bench.reference_activity(track)
                    for speaker, track in tracks.items()
                },
                "audio_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    reference = {
        "synthetic_only": True,
        "fixture_sha256": digest,
        "threshold_fixed_before_generation": fixture[
            "threshold_fixed_before_generation"
        ],
        "voices": fixture["voices"],
        "definitions": definitions(fixture),
        "cases": cases,
    }
    (folder / "references.json").write_text(
        json.dumps(reference, ensure_ascii=False, indent=2) + "\n"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir", type=Path, default=ROOT / ".memora/qa/ecapa-holdout"
    )
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    fixture = json.loads(FIXTURE.read_text())
    if (
        fixture.get("synthetic_only") is not True
        or fixture.get("frozen_before_inference") is not True
    ):
        raise ValueError("Only the frozen synthetic fixture is accepted")
    digest = hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
    folder = args.output_dir.resolve()
    if (folder / "references.json").exists():
        count, verification = check_existing(folder, fixture, digest)
        print(
            f"PASS: {count} existing synthetic cases preserved; verification={verification}; fixture_sha256={digest}"
        )
        return
    if args.check_only:
        raise ValueError(
            "The holdout is not prepared; --check-only never generates audio"
        )
    prepare(folder, fixture, digest)
    count, verification = check_existing(folder, fixture, digest)
    print(
        f"PASS: {count} synthetic cases prepared; verification={verification}; no neural inference"
    )


if __name__ == "__main__":
    main()
