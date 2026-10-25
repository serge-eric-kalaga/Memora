"""Prepare95s synthetic French chunk-boundary probe. CPU/TTS only, never ASR."""

import hashlib
import json
import subprocess
import wave
from pathlib import Path

import numpy as np
from faster_whisper.audio import decode_audio

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "backend/test/fixtures/memora/accuracy-long-fr.v1.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    corpus = json.loads(CORPUS.read_text())
    case = corpus["cases"][0]
    target = ROOT / ".memora/accuracy-benchmark" / ("v" + corpus["version"])
    target.mkdir(parents=True, exist_ok=True)
    pieces, boundaries = [], []
    offset = 0
    for index, chunk in enumerate(case["chunks"]):
        key = hashlib.sha256(json.dumps(chunk, sort_keys=True).encode()).hexdigest()[
            :16
        ]
        path = target / f"block-{index}-{key}.aiff"
        if not path.exists() or path.stat().st_size <= 4096:
            subprocess.run(
                [
                    "/usr/bin/say",
                    "-v",
                    chunk["voice"],
                    "-r",
                    str(chunk["rate"]),
                    "-o",
                    str(path),
                    chunk["text"],
                ],
                check=True,
                timeout=60,
            )
        audio = decode_audio(str(path), sampling_rate=16000)
        nz = np.flatnonzero(audio)
        if not len(nz):
            raise RuntimeError(
                "Empty synthetic speech; native speech-service permission required"
            )
        audio = audio[nz[0] : nz[-1] + 1]
        slot = round(chunk["slot_seconds"] * 16000)
        if len(audio) > slot:
            raise RuntimeError(
                f"Block {index} speech exceeds frozen slot; never truncate it"
            )
        padded = np.pad(audio, (0, slot - len(audio)))
        pieces.append(padded)
        boundaries.append(
            {
                "block": index,
                "start": offset / 16000,
                "speech_duration": len(audio) / 16000,
                "slot_seconds": chunk["slot_seconds"],
                "reference": chunk["text"],
                "tts_sha256": sha(path),
            }
        )
        offset += slot
    audio = np.concatenate(pieces)
    audio /= max(1, float(np.max(np.abs(audio))) / 0.85)
    path = target / "long-fr-boundaries-clean.wav"
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(16000)
        stream.writeframes(
            np.rint(np.clip(audio, -1, 1) * 32767).astype("<i2").tobytes()
        )
    row = {
        "id": "long-fr-boundaries-clean",
        "source": case["id"],
        "split": "holdout",
        "profile": "clean",
        "path": str(path),
        "sha256": sha(path),
        "seconds": len(audio) / 16000,
        "reference": " ".join(c["text"] for c in case["chunks"]),
        "language": "fr",
        "critical": case["critical"],
        "keywords": [],
        "alignment_blocks": boundaries,
    }
    manifest = {
        "corpus_sha256": sha(CORPUS),
        "generated": [row],
        "profiles": ["clean"],
        "notes": {
            "preparation": "Exact digital-zero padding to frozen slot lengths; no truncation or ASR",
            "window_starts": [0, 28, 56, 84],
            "window_ends": [30, 58, 86, 95],
            "metrics": "Complete reference WER/CER and S/D/I; start/end markers are additional only",
        },
    }
    (target / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    )
    print(
        json.dumps(
            {
                "prepared": 1,
                "seconds": row["seconds"],
                "corpus_sha256": manifest["corpus_sha256"],
                "audio_sha256": row["sha256"],
                "inference": False,
                "blocks": boundaries,
            },
            ensure_ascii=False,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
