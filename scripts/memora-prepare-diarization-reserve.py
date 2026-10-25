"""Build frozen synthetic reserve; no neural inference or personal voices."""

import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def main():
    spec = importlib.util.spec_from_file_location(
        "diarization_benchmark", ROOT / "scripts/memora-benchmark-diarization.py"
    )
    bench = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bench)
    folder = ROOT / ".memora/qa/diarization-reserve"
    folder.mkdir(parents=True, exist_ok=True)
    bench.FOLDER = folder
    source = ROOT / "backend/test/fixtures/memora/diarization-reserve-v1.json"
    corpus = json.loads(source.read_text())
    clips = [
        bench.tts(corpus["voices"][u["speaker"]], u["text"], i)
        for i, u in enumerate(corpus["utterances"])
    ]
    cases = []
    for definition in corpus["cases"]:
        if not definition["indices"]:
            waveform = (
                np.random.default_rng(510)
                .normal(0, definition["noise_only_rms"], bench.RATE * 5)
                .astype(np.float32)
            )
            path = folder / (definition["id"] + ".wav")
            bench.write_wav(path, waveform)
            cases.append(
                {
                    "id": definition["id"],
                    "path": str(path),
                    "duration": 5.0,
                    "segments": [],
                    "reference_activity": {},
                    "expected_speakers": 0,
                }
            )
            continue
        cursor = bench.RATE // 2
        placements = []
        segments = []
        for number, index in enumerate(definition["indices"]):
            utterance = corpus["utterances"][index]
            clip = clips[index].copy()
            if utterance["speaker"] == definition.get("weak_speaker"):
                clip *= definition["weak_gain"]
            placements.append((utterance["speaker"], cursor, clip))
            segments.append(
                {
                    "id": f"s{number + 1}",
                    "start": cursor / bench.RATE,
                    "end": (cursor + len(clip)) / bench.RATE,
                    "text": utterance["text"],
                    "speaker": "Intervenant non identifié",
                }
            )
            cursor += len(clip) + int(0.3 * bench.RATE)
        tracks = {
            speaker: np.zeros(cursor + bench.RATE // 2, dtype=np.float32)
            for speaker, _, _ in placements
        }
        for speaker, start, clip in placements:
            tracks[speaker][start : start + len(clip)] += clip
        waveform = sum(tracks.values())
        if definition["noise"]:
            rms = np.sqrt(np.mean(waveform**2))
            waveform += (
                np.random.default_rng(730)
                .normal(
                    0,
                    rms / (10 ** (definition["global_noise_snr_db"] / 20)),
                    len(waveform),
                )
                .astype(np.float32)
            )
        path = folder / (definition["id"] + ".wav")
        bench.write_wav(path, waveform)
        cases.append(
            {
                "id": definition["id"],
                "path": str(path),
                "duration": len(waveform) / bench.RATE,
                "segments": segments,
                "reference_activity": {
                    s: bench.reference_activity(v) for s, v in tracks.items()
                },
                "expected_speakers": len(tracks),
            }
        )
    (folder / "references.json").write_text(
        json.dumps(
            {
                "synthetic_only": True,
                "corpus_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                "cases": cases,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    print("Frozen reserve prepared; no inference;", len(cases), "cases")


if __name__ == "__main__":
    main()
