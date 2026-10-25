"""Synthetic-only codec/ASR audit. Never reads recordings or contacts a microphone."""

import json
import re
import time
import unicodedata
from pathlib import Path

import av
import numpy as np
from faster_whisper import WhisperModel
from faster_whisper.audio import decode_audio

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "backend/test/fixtures/memora"
OUT = ROOT / ".memora/capture-qa"
OUT.mkdir(exist_ok=True)
EXPECTED = {
    "french": "Nous décidons de lancer le projet Memora lundi. Alice préparera la démonstration vendredi. Le budget reste une question ouverte.",
    "english": "We decided to launch the Memora project on Monday. Alice will prepare the demonstration on Friday. The budget remains an open question.",
    "french-realistic": "Nous ne validons pas le paiement. Le montant est de deux mille quatre cents francs CFA, et non de vingt-quatre mille. Le rendez-vous à Ouagadougou est reporté au douze novembre. Aïcha doit appeler Monsieur Traoré ; Moussa ne doit rien envoyer avant son accord.",
}


def normalized(text):
    text = unicodedata.normalize("NFC", text.casefold())
    return " ".join(re.sub(r"[^\w\s]", " ", text).split())


def distance(a, b):
    row = list(range(len(b) + 1))
    for i, aa in enumerate(a, 1):
        nxt = [i]
        for j, bb in enumerate(b, 1):
            nxt.append(min(nxt[-1] + 1, row[j] + 1, row[j - 1] + (aa != bb)))
        row = nxt
    return row[-1]


def canonical_numbers(text):
    # Explicit synthetic-fixture normalization only; not a French number parser.
    text = normalized(text)
    for words, digits in (
        ("deux mille quatre cents", "2400"),
        ("vingt quatre mille", "24000"),
        ("24 000", "24000"),
        ("douze", "12"),
    ):
        text = text.replace(words, digits)
    return text


def metrics(expected, actual):
    a, b = normalized(expected), normalized(actual)
    ca, cb = canonical_numbers(expected), canonical_numbers(actual)
    return {
        "wer": round(distance(a.split(), b.split()) / len(a.split()), 4),
        "cer": round(distance(a, b) / len(a), 4),
        "wer_numbers_normalized": round(
            distance(ca.split(), cb.split()) / len(ca.split()), 4
        ),
        "cer_numbers_normalized": round(distance(ca, cb) / len(ca), 4),
    }


def encode_opus(samples, target, bitrate):
    with av.open(str(target), "w", format="webm") as container:
        stream = container.add_stream("libopus", rate=48000)
        stream.layout = "mono"
        stream.bit_rate = bitrate
        resampler = av.AudioResampler(format="fltp", layout="mono", rate=48000)
        frame = av.AudioFrame.from_ndarray(
            samples.reshape(1, -1), format="fltp", layout="mono"
        )
        frame.sample_rate = 16000
        for converted in resampler.resample(frame) + resampler.resample(None):
            for packet in stream.encode(converted):
                container.mux(packet)
        for packet in stream.encode(None):
            container.mux(packet)


def main():
    model = WhisperModel(
        "base",
        device="cpu",
        compute_type="int8",
        cpu_threads=2,
        download_root=str(ROOT / ".memora/models"),
        local_files_only=True,
    )
    results = []
    for name, expected in EXPECTED.items():
        path = FIXTURES / f"{name}.aiff"
        samples = decode_audio(str(path), sampling_rate=16000)
        profiles = [("pcm-original", path)]
        for bitrate in (32000, 64000, 128000):
            target = OUT / f"{name}-opus-{bitrate}.webm"
            encode_opus(samples, target, bitrate)
            profiles.append((f"opus-{bitrate}", target))
        for profile, source in profiles:
            decoded = decode_audio(str(source), sampling_rate=16000)
            max_peak = float(np.max(np.abs(decoded), initial=0))
            for vad in (True, False):
                t = time.monotonic()
                segments, _info = model.transcribe(
                    decoded,
                    beam_size=5,
                    multilingual=True,
                    vad_filter=vad,
                    condition_on_previous_text=False,
                )
                actual = " ".join(s.text.strip() for s in segments)
                result = {
                    "fixture": name,
                    "profile": profile,
                    "vad": vad,
                    "duration_seconds": round(len(decoded) / 16000, 3),
                    "duration_delta_ms": round((len(decoded) - len(samples)) / 16, 2),
                    "peak": round(max_peak, 4),
                    "seconds": round(time.monotonic() - t, 2),
                    **metrics(expected, actual),
                    "actual_synthetic": actual,
                }
                results.append(result)
                print(json.dumps(result, ensure_ascii=False), flush=True)
    (ROOT / "agents/logs/capture-qa.json").write_text(
        json.dumps(
            {
                "normalization": "Unicode NFC lower case, punctuation to spaces, collapse whitespace; digits and accents preserved. Strict WER includes numeric-formatting differences.",
                "expected_synthetic": EXPECTED,
                "results": results,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
