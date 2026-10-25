"""Offline synthetic-only benchmark; refuse incomplete/unverified MLX weights.

No inference or ASR import occurs before the local download manifest and full
weights SHA256 have been verified. Baseline runs first and is unloaded before MLX.
"""

import argparse
import gc
import hashlib
import importlib.util
import json
import os
import sys
import time
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "backend/test/fixtures/memora"
CASES = {
    "python": (
        "python-sentence.wav",
        "Aujourd'hui nous allons parler du langage python.",
    ),
    "python-tail": (
        "python-sentence-tail10s.wav",
        "Aujourd'hui nous allons parler du langage python.",
    ),
    "french-realistic": (
        "french-realistic.aiff",
        "Nous ne validons pas le paiement. Le montant est de deux mille quatre cents francs CFA, et non de vingt-quatre mille. Le rendez-vous à Ouagadougou est reporté au douze novembre. Aïcha doit appeler Monsieur Traoré ; Moussa ne doit rien envoyer avant son accord.",
    ),
    "mixed": (
        "mixed-native.wav",
        "Bonjour. Nous décidons de lancer le projet Memora lundi. Alice préparera la démonstration vendredi. The budget remains an open question. We will discuss it next week.",
    ),
    "english": (
        "english.wav",
        "We decided to launch the Memora project on Monday. Alice will prepare the demonstration on Friday. The budget remains an open question.",
    ),
    "silence": ("benchmark-silence.wav", ""),
    "white-noise": ("benchmark-white-noise.wav", ""),
}


def ensure_synthetic_negative_fixtures():
    """Only create known synthetic WAVs; never read arbitrary recordings."""
    import numpy as np

    with wave.open(str(FIXTURES / "python-sentence.wav"), "rb") as source:
        params = source.getparams()
        frames = source.readframes(source.getnframes())
        speech_duration = source.getnframes() / source.getframerate()
    tail = FIXTURES / CASES["python-tail"][0]
    if not tail.exists():
        with wave.open(str(tail), "wb") as target:
            target.setparams(params)
            target.writeframes(
                frames
                + b"\0" * (10 * params.framerate * params.nchannels * params.sampwidth)
            )
    silence = FIXTURES / CASES["silence"][0]
    noise = FIXTURES / CASES["white-noise"][0]
    for path, samples in (
        (silence, np.zeros(3 * 16000, dtype="<i2")),
        (
            noise,
            np.rint(
                np.random.default_rng(20261025).normal(0, 0.0015, 10 * 16000) * 32767
            ).astype("<i2"),
        ),
    ):
        if not path.exists():
            with wave.open(str(path), "wb") as target:
                target.setnchannels(1)
                target.setsampwidth(2)
                target.setframerate(16000)
                target.writeframes(samples.tobytes())
    return {
        "python_original_duration_seconds": speech_duration,
        "appended_digital_silence_seconds": 10,
        "white_noise_duration_seconds": 10,
        "white_noise_seed": 20261025,
        "white_noise_target_rms": 0.0015,
        "white_noise_target_dbfs": -56.48,
    }


def verify_model(model):
    manifest = model / "memora-model.json"
    weights = model / "weights.safetensors"
    if not all(path.is_file() for path in (manifest, weights, model / "config.json")):
        raise RuntimeError(
            "Modèle incomplet : manifeste/config/poids vérifiés requis ; aucune inférence lancée."
        )
    metadata = json.loads(manifest.read_text())
    expected = metadata.get("sha256", "")
    if len(expected) != 64 or any(c not in "0123456789abcdef" for c in expected):
        raise RuntimeError("SHA256 du manifeste invalide ; aucune inférence lancée.")
    if weights.stat().st_size != metadata.get("bytes"):
        raise RuntimeError(
            "Taille des poids différente du manifeste ; aucune inférence lancée."
        )
    digest = hashlib.sha256()
    with weights.open("rb") as source:
        while block := source.read(8 * 1024 * 1024):
            digest.update(block)
    if digest.hexdigest() != expected:
        raise RuntimeError(
            "SHA256 des poids différent du manifeste ; aucune inférence lancée."
        )
    if metadata.get(
        "repo"
    ) != "mlx-community/whisper-large-v3-turbo" or not metadata.get("revision"):
        raise RuntimeError("Provenance du modèle inattendue ; aucune inférence lancée.")
    return metadata


def load_file(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(args):
    model = (
        Path(
            os.environ.get(
                "MEMORA_MLX_MODEL_PATH", ROOT / ".memora/models/mlx-large-v3-turbo"
            )
        )
        .expanduser()
        .resolve()
    )
    manifest = verify_model(model)
    print("SHA256 complet et manifeste local vérifiés.", flush=True)
    if args.check_only:
        return
    # All inference remains offline even if an installed dependency tries a lookup.
    os.environ.update(
        {
            "HF_HUB_OFFLINE": "1",
            "HF_HUB_DISABLE_TELEMETRY": "1",
            "TRANSFORMERS_OFFLINE": "1",
            "MEMORA_MLX_MODEL_PATH": str(model),
        }
    )
    scoring = load_file(
        "memora_benchmark_metrics", ROOT / "scripts/memora-qa-capture.py"
    )
    import av

    negative_fixture_info = ensure_synthetic_negative_fixtures()
    selected = args.cases or list(CASES)
    durations = {}
    for case in selected:
        filename, _ = CASES[case]
        with av.open(str(FIXTURES / filename)) as container:
            durations[case] = sum(
                frame.samples / frame.sample_rate for frame in container.decode(audio=0)
            )
    output = {
        "model_manifest_sha256_verified": manifest,
        "language_mode": args.language,
        "synthetic_only": True,
        "negative_fixture_info": negative_fixture_info,
        "normalization": "NFC, lowercase, punctuation to spaces, collapse whitespace, accents retained. Strict WER includes numeric formatting. Additional normalized metrics map only: deux mille quatre cents→2400; vingt quatre mille/24 000→24000; douze→12.",
        "timing_policy": "Wall time covers audio decode, transcription, adapter metadata and cleanup. Baseline model cached across cases, first case includes load; unloaded before MLX. MLX adapter unloads GPU per case, so each non-silent case includes model load. RTF=wall/audio duration; not a pure warm-kernel comparison.",
        "language_limit": "MLX auto detects a dominant language independently within each Silero VAD speech region; scope/confidence metadata recorded. Language changes within continuous speech or very short regions remain uncertain. Mixed corpus must be inspected for omissions or translation. No automatic superiority claim from these fixtures.",
        "results": [],
    }
    destination = ROOT / "agents/logs/benchmark-mlx.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    engines = ("baseline", "mlx") if args.engine == "both" else (args.engine,)
    for engine in engines:
        if engine == "baseline":
            snapshots = (
                ROOT / ".memora/models/models--Systran--faster-whisper-base/snapshots"
            )
            local = next(
                (
                    p
                    for p in sorted(snapshots.glob("*"))
                    if (p / "model.bin").is_file() and (p / "config.json").is_file()
                ),
                None,
            )
            if local is None:
                raise RuntimeError(
                    "Baseline base locale manquante ; aucun téléchargement autorisé par benchmark."
                )
            os.environ["MEMORA_ASR_ENGINE"] = "faster-whisper"
            os.environ["MEMORA_ASR_MODEL"] = str(local.resolve())
            adapter = load_file(
                "memora_benchmark_baseline", ROOT / "backend/api/memora/ai.py"
            )
        else:
            adapter = load_file(
                "memora_benchmark_mlx", ROOT / "backend/api/memora/asr_mlx.py"
            )
        for case in selected:
            filename, expected = CASES[case]
            started = time.monotonic()
            segments = adapter.transcribe(FIXTURES / filename, language=args.language)
            elapsed = time.monotonic() - started
            actual = " ".join(s["text"] for s in segments)
            scores = (
                scoring.metrics(expected, actual)
                if expected
                else {
                    "wer": None,
                    "cer": None,
                    "wer_numbers_normalized": None,
                    "cer_numbers_normalized": None,
                    "silence_hallucinated": bool(actual.strip()),
                    "inserted_words": len(scoring.normalized(actual).split()),
                }
            )
            row = {
                "engine": engine,
                "case": case,
                "fixture": str((FIXTURES / filename).relative_to(ROOT)),
                "expected_synthetic": expected,
                "actual_synthetic": actual,
                "duration_seconds": round(durations[case], 4),
                "wall_seconds": round(elapsed, 4),
                "rtf": round(elapsed / durations[case], 4),
                "uncertain_segments": sum(bool(s.get("uncertain")) for s in segments),
                "segment_count": len(segments),
                "languages": sorted({s.get("language", "unknown") for s in segments}),
                "segments_synthetic": segments,
                **scores,
            }
            if not expected:
                row["acceptance"] = {
                    "no_extra_text": not actual.strip(),
                    "no_nonempty_segments": not any(
                        s["text"].strip() for s in segments
                    ),
                }
            elif case == "python-tail":
                expected_tokens = scoring.normalized(expected).split()
                actual_tokens = scoring.normalized(actual).split()
                same_text = actual_tokens == expected_tokens
                no_tail_segments = all(
                    s["start"]
                    < negative_fixture_info["python_original_duration_seconds"] + 0.15
                    for s in segments
                    if s["text"].strip()
                )
                original = next(
                    (
                        r
                        for r in output["results"]
                        if r["engine"] == engine and r["case"] == "python"
                    ),
                    None,
                )
                row["acceptance"] = {
                    "matches_original_expected_text": same_text,
                    "no_segment_starts_in_appended_silence": no_tail_segments,
                    "accepted": same_text and no_tail_segments,
                }
                row["unexpected_suffix_words_if_expected_prefix_matches"] = (
                    actual_tokens[len(expected_tokens) :]
                    if actual_tokens[: len(expected_tokens)] == expected_tokens
                    else None
                )
                row["extra_wall_seconds_vs_python"] = (
                    round(elapsed - original["wall_seconds"], 4) if original else None
                )
            output["results"].append(row)
            destination.write_text(json.dumps(output, ensure_ascii=False, indent=2))
            print(
                json.dumps(
                    {
                        key: row[key]
                        for key in (
                            "engine",
                            "case",
                            "wall_seconds",
                            "rtf",
                            "wer",
                            "cer",
                            "wer_numbers_normalized",
                            "uncertain_segments",
                            "languages",
                        )
                    },
                    ensure_ascii=False,
                ),
                flush=True,
            )
        if engine == "baseline":
            adapter._model = None
            gc.collect()
    print("Benchmark terminé : agents/logs/benchmark-mlx.json", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Verify local manifest/SHA256 only, never infer",
    )
    parser.add_argument("--engine", choices=("both", "baseline", "mlx"), default="both")
    parser.add_argument("--language", choices=("auto", "fr", "en"), default="auto")
    parser.add_argument("--cases", nargs="+", choices=tuple(CASES))
    try:
        run(parser.parse_args())
    except (RuntimeError, OSError, ValueError, ImportError) as error:
        print(
            str(error)
            if isinstance(error, RuntimeError)
            else f"Échec benchmark ({type(error).__name__}) ; diagnostic local requis.",
            file=sys.stderr,
        )
        sys.exit(2)
