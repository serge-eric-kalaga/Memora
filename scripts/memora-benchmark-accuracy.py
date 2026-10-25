"""Frozen synthetic ASR benchmark. Default prepares audio; --run explicitly infers.

Strict scoring preserves accents. Numeric scoring only maps the documented number
phrases below; it never collapses 2400/24000. Lexical critical probes are not a
semantic oracle. Holdout must not guide tuning. No natural-speech guarantee.
"""

import argparse
import hashlib
import importlib
import importlib.util
import json
import marshal
import os
import re
import resource
import secrets
import subprocess
import sys
import time
import types
import unicodedata
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "backend/test/fixtures/memora/accuracy-corpus.v1.json"
NUMBERS = {
    "deux mille quatre cents": "2400",
    "deux mille quatre cent": "2400",
    "vingt quatre mille": "24000",
    "two thousand four hundred": "2400",
    "twenty four thousand": "24000",
    "trois mille cinq cents": "3500",
    "trois mille cinq cent": "3500",
    "trente cinq mille": "35000",
    "three thousand five hundred": "3500",
    "thirty five thousand": "35000",
    "seventeen": "17",
    "seventy": "70",
    "thirteen": "13",
    "thirty": "30",
}
METRIC_VERSION = "2-currency-and-canonical-probes-all-occurrences"
NUMBERS["cent"] = "100"
PROFILES = ("clean", "noise20", "noise10", "reverb", "opus32", "quiet24")


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        while b := f.read(8 * 1024 * 1024):
            h.update(b)
    return h.hexdigest()


def normalize(text, numeric=False):
    text = unicodedata.normalize("NFC", text).casefold()
    if numeric:
        currencies = {"$": "dollars", "€": "euros", "£": "pounds"}
        text = re.sub(
            r"([$€£])\s*(\d+(?:[ ,]\d{3})*(?:\.\d+)?)",
            lambda m: m[2] + " " + currencies[m[1]],
            text,
        )
        for symbol, unit in currencies.items():
            text = text.replace(symbol, " " + unit + " ")
    text = "".join(c if c.isalnum() or c.isspace() else " " for c in text)
    text = " ".join(text.split())
    if numeric:
        for a, b in sorted(NUMBERS.items(), key=lambda p: -len(p[0])):
            text = re.sub(r"(?<!\w)" + re.escape(a) + r"(?!\w)", b, text)
        text = re.sub(r"(?<=\d)\s+(?=\d{3}(?:\D|$))", "", text)
    return text


def distance(ref, hyp):
    # Tuple cost, substitutions, deletions, insertions; deterministic tie order.
    prev = [(j, 0, 0, j) for j in range(len(hyp) + 1)]
    for i, a in enumerate(ref, 1):
        row = [(i, 0, i, 0)]
        for j, b in enumerate(hyp, 1):
            if a == b:
                row.append(prev[j - 1])
                continue
            s = prev[j - 1]
            d = prev[j]
            ins = row[j - 1]
            row.append(
                min(
                    [
                        (s[0] + 1, s[1] + 1, s[2], s[3]),
                        (d[0] + 1, d[1], d[2] + 1, d[3]),
                        (ins[0] + 1, ins[1], ins[2], ins[3] + 1),
                    ],
                    key=lambda x: x[0],
                )
            )
        prev = row
    e, s, d, i = prev[-1]
    return {
        "n": len(ref),
        "errors": e,
        "s": s,
        "d": d,
        "i": i,
        "rate": e / len(ref) if ref else None,
    }


def score(ref, hyp):
    out = {}
    for name, numeric in [("strict", False), ("numeric", True)]:
        r, h = normalize(ref, numeric), normalize(hyp, numeric)
        out[name] = {"wer": distance(r.split(), h.split()), "cer": distance(r, h)}
    return out


def critical(probes, hyp):
    tokens = normalize(hyp, True).split()
    results = []
    for probe in probes:
        canonical = normalize(" ".join(probe), True).split()
        positions = {-1}
        for term in canonical:
            positions = {
                i
                for i, token in enumerate(tokens)
                if token == term
                and any(
                    i > previous and (previous < 0 or i - previous <= 12)
                    for previous in positions
                )
            }
            if not positions:
                break
        results.append(
            {"tokens": probe, "canonical_tokens": canonical, "pass": bool(positions)}
        )
    return results


def save_wav(path, audio):
    import numpy as np

    with wave.open(str(path), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(16000)
        f.writeframes(np.rint(np.clip(audio, -1, 1) * 32767).astype("<i2").tobytes())


def prepare(args, corpus):
    import numpy as np
    from faster_whisper.audio import decode_audio

    version = str(corpus["version"])
    if not re.fullmatch(r"[A-Za-z0-9_-]+", version):
        raise ValueError("Invalid corpus version")
    target = ROOT / ".memora/accuracy-benchmark" / ("v" + version)
    target.mkdir(parents=True, exist_ok=True)
    rows = []
    for case in corpus["cases"]:
        chunks = []
        for chunk in case["chunks"]:
            key = hashlib.sha256(
                json.dumps(chunk, sort_keys=True).encode()
            ).hexdigest()[:20]
            path = target / (key + ".aiff")
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
            a = decode_audio(str(path), sampling_rate=16000)
            if not len(a):
                raise RuntimeError(
                    "Empty macOS TTS audio; rerun with native speech service permission"
                )
            # Strip digital-zero padding only, not weak spoken content.
            nz = np.flatnonzero(a)
            if len(nz):
                a = a[nz[0] : nz[-1] + 1]
            chunks.extend([a, np.zeros(round(chunk["gap_ms"] * 16), dtype=np.float32)])
        audio = np.concatenate(chunks[:-1])
        audio = audio / (max(1, float(np.max(np.abs(audio))) / 0.85))
        for profile in args.profiles:
            path = target / (case["id"] + "-" + profile + ".wav")
            changed = audio.copy()
            seed = corpus["seed"] + int(
                hashlib.sha256(case["id"].encode()).hexdigest()[:8], 16
            )
            if profile.startswith("noise"):
                snr = int(profile[5:])
                active = audio[np.abs(audio) > 0.01]
                rms = float(np.sqrt(np.mean(active**2))) if len(active) else 0.01
                changed += np.random.default_rng(seed).normal(
                    0, rms / (10 ** (snr / 20)), len(audio)
                )
            elif profile == "reverb":
                ir = np.zeros(4801, dtype=np.float32)
                ir[0] = 1
                for ms, gain in [
                    (31, 0.3),
                    (67, 0.18),
                    (113, 0.09),
                    (173, 0.035),
                    (251, 0.006),
                ]:
                    ir[ms * 16] = gain
                changed = np.convolve(audio, ir)
            elif profile == "quiet24":
                changed *= 10 ** (-24 / 20)
            save_wav(path, changed)
            if profile == "opus32":
                import av

                encoded = path.with_suffix(".ogg")
                with av.open(str(encoded), "w") as out:
                    stream = out.add_stream("libopus", rate=16000)
                    stream.bit_rate = 32000
                    stream.layout = "mono"
                    frame = av.AudioFrame.from_ndarray(
                        changed[None, :].astype("float32"), format="fltp", layout="mono"
                    )
                    frame.sample_rate = 16000
                    for packet in stream.encode(frame):
                        out.mux(packet)
                    for packet in stream.encode(None):
                        out.mux(packet)
                path = encoded
            rows.append(
                {
                    "id": case["id"] + "-" + profile,
                    "source": case["id"],
                    "split": case["split"],
                    "profile": profile,
                    "path": str(path),
                    "sha256": sha(path),
                    "seconds": len(changed) / 16000,
                    "reference": " ".join(c["text"] for c in case["chunks"]),
                    "language": case["language"],
                    "critical": case["critical"],
                    "keywords": case["keywords"],
                    "forbidden": case.get("forbidden", []),
                }
            )
    for name, audio in [
        ("silence", np.zeros(3 * 16000)),
        (
            "noise-only",
            np.random.default_rng(corpus["seed"]).normal(0, 0.01, 5 * 16000),
        ),
    ]:
        path = target / (name + ".wav")
        save_wav(path, audio)
        rows.append(
            {
                "id": name,
                "source": name,
                "split": "negative",
                "profile": "negative",
                "path": str(path),
                "sha256": sha(path),
                "seconds": len(audio) / 16000,
                "reference": "",
                "language": "auto",
                "critical": [],
                "keywords": ["Kadiatou", "Memora"],
                "forbidden": ["Kadiatou", "Memora"],
            }
        )
    manifest = {
        "corpus_sha256": sha(args.corpus),
        "generated": rows,
        "profiles": args.profiles,
        "notes": {
            "noise": "stationary seeded Gaussian; SNR relative to samples abs>0.01, not measured room noise",
            "reverb": "fixed sparse 251ms FIR; synthetic echoes, no claimed real room RT60",
            "quiet24": "amplitude scaled -24dB, not whispered speech",
            "split": "source-group split; acoustics do not create independent utterances",
            "pause": "inserted digital silence after zero-padding trim; TTS can contain natural pauses",
        },
    }
    (target / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    )
    return manifest


def verify_model(model):
    metadata = json.loads((model / "memora-model.json").read_text())
    allowed = {
        "mlx-community/whisper-large-v3-turbo",
        "mlx-community/whisper-large-v3-mlx",
        "mlx-community/parakeet-tdt-0.6b-v3",
    }
    if metadata.get("repo") not in allowed or not metadata.get("revision"):
        raise ValueError("Unrecognized model provenance")
    weights = next(
        (
            model / n
            for n in ("weights.safetensors", "weights.npz", "model.safetensors")
            if (model / n).is_file()
        ),
        None,
    )
    if (
        not weights
        or not (model / "config.json").is_file()
        or weights.stat().st_size != metadata.get("bytes")
        or sha(weights) != metadata.get("sha256")
    ):
        raise ValueError("Model size/SHA mismatch")
    for name, asset in metadata.get("assets", {}).items():
        file = model / name
        if file.resolve().parent != model.resolve() or not file.is_file():
            raise ValueError("Invalid model asset path")
        if file == weights:
            continue
        if file.stat().st_size != asset.get("bytes") or sha(file) != asset.get(
            "sha256"
        ):
            raise ValueError("Model asset size/SHA mismatch")
    return metadata


def adapter(path, variant, language, keywords):
    spec = importlib.util.spec_from_file_location("accuracy_adapter", path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    if "context" in variant and language in ("fr", "en"):
        original = m._speech_regions

        def grouped(audio):
            out = []
            for region in original(audio):
                r = dict(region)
                if (
                    out
                    and r["start"] - out[-1]["end"] <= 16000
                    and r["end"] - out[-1]["start"] <= 25 * 16000
                ):
                    out[-1]["end"] = r["end"]
                else:
                    out.append(r)
            return out

        m._speech_regions = grouped
    if ("vocabulary" in variant and keywords) or variant in (
        "temperature-zero",
        "best-of-five",
    ):
        original_runtime = m._runtime

        def runtime():
            real, mx = original_runtime()

            def transcribe(*a, **kw):
                if "vocabulary" in variant and keywords:
                    kw["initial_prompt"] = "Terms: " + ", ".join(keywords)
                if variant == "temperature-zero":
                    kw["temperature"] = 0.0
                elif variant == "best-of-five":
                    kw["best_of"] = 5
                return real.transcribe(*a, **kw)

            return types.SimpleNamespace(
                transcribe=transcribe, ModelHolder=real.ModelHolder
            ), mx

        m._runtime = runtime
    return m


def function_code_sha(function):
    """Loaded bytecode/constants, excluding file/line positions changed by helpers."""

    def normalized(code):
        return code.replace(
            co_filename="",
            co_firstlineno=0,
            co_linetable=b"",
            co_consts=tuple(
                normalized(value) if isinstance(value, types.CodeType) else value
                for value in code.co_consts
            ),
        )

    return hashlib.sha256(marshal.dumps(normalized(function.__code__))).hexdigest()


def production_factory(calls):
    """Observe real production dispatch in this process, without fake ASR output."""
    os.environ.update(
        APP_NAME="Memora synthetic ASR benchmark",
        ADMINS_EMAIL="synthetic@example.invalid",
        SECRET_KEY=secrets.token_hex(32),
        JWT_SECRET=secrets.token_hex(32),
        ALGORITHM="HS256",
        DATABASE_URL="sqlite:///:memory:",
        INITIALISE_DATABASE="false",
        CACHE_ENABLED="false",
        RATE_LIMIT_ENABLED="false",
    )
    sys.path.insert(0, str(ROOT / "backend"))
    factory = importlib.import_module("api.memora.ai")
    for engine, name in (("mlx-whisper", "asr_mlx"), ("parakeet-mlx", "asr_parakeet")):
        provider = importlib.import_module("api.memora." + name)
        original = provider.transcribe

        def wrap(real, provider_module, provider_engine):
            def transcribe(path, tail_seconds=None, language="auto"):
                if provider_engine == "parakeet-mlx":
                    chosen = (
                        os.environ.get("MEMORA_PARAKEET_MODEL_PATH")
                        or provider_module.DEFAULT_MODEL
                    )
                else:
                    chosen = (
                        os.environ.get("MEMORA_MLX_MODEL_PATH")
                        or provider_module._DEFAULT_MODEL
                    )
                    if language == "fr" and tail_seconds is None:
                        chosen = os.environ.get("MEMORA_MLX_FR_MODEL_PATH") or chosen
                selected = Path(chosen).resolve()
                metadata = json.loads((selected / "memora-model.json").read_text())
                calls.append(
                    {
                        "engine": provider_engine,
                        "model_path": str(selected),
                        "model_sha256": metadata["sha256"],
                        "model_repo": metadata["repo"],
                        "language_argument": language,
                        "tail_seconds": tail_seconds,
                    }
                )
                return real(path, tail_seconds=tail_seconds, language=language)

            return transcribe

        provider.transcribe = wrap(original, provider, engine)
    return factory


def summarize(results):
    summary = {}
    for split, profile in {(r["split"], r["profile"]) for r in results}:
        subset = [
            r
            for r in results
            if r["profile"] == profile and r["split"] == split and r["reference"]
        ]
        if not subset:
            continue
        stratum = split + ":" + profile
        summary[stratum] = {}
        for metric in ("strict", "numeric"):
            counts = {
                k: sum(r["scores"][metric]["wer"][k] for r in subset)
                for k in ("n", "errors", "s", "d", "i")
            }
            counts["wer"] = counts["errors"] / counts["n"]
            counts["one_minus_wer"] = 1 - counts["wer"]
            chars = {
                k: sum(r["scores"][metric]["cer"][k] for r in subset)
                for k in ("n", "errors", "s", "d", "i")
            }
            chars["cer"] = chars["errors"] / chars["n"]
            counts["characters"] = chars
            counts["critical_passed"] = sum(
                p["pass"] for r in subset for p in r["critical_results"]
            )
            counts["critical_total"] = sum(len(r["critical_results"]) for r in subset)
            summary[stratum][metric] = counts
    return summary


def memory_snapshot():
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform != "darwin":
        peak *= 1024
    result = {
        "process_peak_rss_bytes": peak,
        "physical_memory_bytes": os.sysconf("SC_PAGE_SIZE")
        * os.sysconf("SC_PHYS_PAGES"),
    }
    mx = sys.modules.get("mlx.core")
    if mx and hasattr(mx, "get_peak_memory"):
        result["mlx_peak_allocated_bytes"] = mx.get_peak_memory()
    if sys.platform == "darwin":
        text = subprocess.run(
            ["/usr/bin/vm_stat"], capture_output=True, text=True, check=True
        ).stdout
        page = int(re.search(r"page size of (\d+) bytes", text)[1])
        pages = {
            name: int(re.search(re.escape(name) + r":\s+(\d+)", text)[1])
            for name in ("Pages free", "Pages inactive", "Pages speculative")
        }
        result["free_inactive_speculative_bytes_proxy"] = sum(pages.values()) * page
        result["vm_stat_pages"] = pages
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run", action="store_true")
    p.add_argument(
        "--max-rss-gib",
        type=float,
        default=12,
        help="Stop between cases if process RSS high-water exceeds this limit",
    )
    p.add_argument(
        "--rescore",
        nargs="+",
        type=Path,
        help="Rescore stored synthetic outputs only, no model/audio inference",
    )
    p.add_argument("--self-test", action="store_true")
    p.add_argument("--corpus", type=Path, default=CORPUS)
    p.add_argument(
        "--prepared",
        action="store_true",
        help="Reuse frozen generated manifest/audio, verify every SHA, no TTS/audio preparation dependency",
    )
    p.add_argument(
        "--model-path", type=Path, default=ROOT / ".memora/models/mlx-large-v3-turbo"
    )
    p.add_argument(
        "--fr-model-path",
        type=Path,
        help="Optional verified model for explicit French final cases only; auto/English stay on base model",
    )
    p.add_argument(
        "--adapter-path",
        type=Path,
        default=ROOT / "backend/api/memora/asr_mlx.py",
        help="Versioned current adapter; historical comparisons require their explicit preserved snapshot path",
    )
    p.add_argument(
        "--production-factory",
        action="store_true",
        help="Call actual api.memora.ai.transcribe and verify provider/model dispatch",
    )
    p.add_argument(
        "--fr-engine", choices=["mlx-whisper", "parakeet-mlx"], default="mlx-whisper"
    )
    p.add_argument("--label", default="baseline")
    p.add_argument("--split", choices=["tuning", "holdout", "all"], default="tuning")
    p.add_argument("--cases", nargs="+")
    p.add_argument("--profiles", nargs="+", choices=PROFILES, default=list(PROFILES))
    p.add_argument(
        "--variant",
        choices=[
            "baseline",
            "context",
            "vocabulary",
            "context-vocabulary",
            "temperature-zero",
            "best-of-five",
        ],
        default="baseline",
    )
    p.add_argument("--language", choices=["auto", "native", "fr", "en"], default="auto")
    args = p.parse_args()
    if args.rescore:
        default_numbers = dict(NUMBERS)
        for path in args.rescore:
            old = json.loads(path.read_text())
            NUMBERS.clear()
            NUMBERS.update(old.get("normalizer_numbers", default_numbers))
            backup = path.with_suffix(".metric-v1.json")
            if not backup.exists():
                backup.write_text(path.read_text())
            for row in old["results"]:
                row["scores"] = score(row["reference"], row["hypothesis"])
                row["critical_results"] = critical(row["critical"], row["hypothesis"])
            old["metric_version"] = METRIC_VERSION
            old["normalizer_numbers"] = NUMBERS
            old["summary_by_profile"] = summarize(old["results"])
            path.write_text(json.dumps(old, ensure_ascii=False, indent=2) + "\n")
            print("RESCORED", path)
        return
    if args.self_test:
        assert distance(["a", "b"], ["a", "c", "d"]) == {
            "n": 2,
            "errors": 2,
            "s": 1,
            "d": 0,
            "i": 1,
            "rate": 1,
        }
        assert normalize("deux mille quatre cents", True) == "2400"
        assert normalize("vingt-quatre mille", True) == "24000"
        assert normalize("Aïcha") != normalize("Aicha")
        assert normalize("$2,400", True) == normalize(
            "two thousand four hundred dollars", True
        )
        assert normalize("€2,400", True) != normalize("$2,400", True)
        assert normalize("$24,000", True) != normalize("$2,400", True)
        assert critical([["cent", "dossiers"]], "100 dossiers")[0]["pass"]
        assert critical(
            [["not", "approved"]], "not " + "earlier " * 20 + "not approved"
        )[0]["pass"]
        assert not critical([["not", "approved"]], "approved")[0]["pass"]
        print("PASS metric self-tests")
        return
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.label):
        p.error("Invalid label")
    corpus = json.loads(args.corpus.read_text())
    NUMBERS.update(corpus.get("number_normalization", {}))
    if args.prepared:
        version = str(corpus["version"])
        if not re.fullmatch(r"[A-Za-z0-9_-]+", version):
            raise ValueError("Invalid corpus version")
        manifest = json.loads(
            (
                ROOT / ".memora/accuracy-benchmark" / ("v" + version) / "manifest.json"
            ).read_text()
        )
        if manifest["corpus_sha256"] != sha(args.corpus):
            raise ValueError("Prepared corpus SHA mismatch")
        if not set(args.profiles).issubset(manifest["profiles"]):
            raise ValueError("Requested acoustic profiles not prepared")
        for row in manifest["generated"]:
            if sha(Path(row["path"])) != row["sha256"]:
                raise ValueError("Prepared audio SHA mismatch")
    else:
        manifest = prepare(args, corpus)
    selected = [
        r
        for r in manifest["generated"]
        if (r["profile"] in args.profiles or r["profile"] == "negative")
        and (args.split == "all" or r["split"] in (args.split, "negative"))
        and (not args.cases or r["source"] in args.cases)
    ]
    print(
        json.dumps(
            {
                "prepared": len(manifest["generated"]),
                "selected": len(selected),
                "corpus_sha256": manifest["corpus_sha256"],
                "inference": args.run,
            }
        ),
        flush=True,
    )
    if not args.run:
        return
    model = verify_model(args.model_path.resolve())
    if model["repo"] == "mlx-community/parakeet-tdt-0.6b-v3" and (
        args.fr_model_path or args.variant != "baseline"
    ):
        raise ValueError(
            "Parakeet experiment supports baseline only, without Whisper routing/decoding variants"
        )
    fr_model = (
        verify_model(args.fr_model_path.resolve()) if args.fr_model_path else None
    )
    if fr_model and "parakeet" in fr_model["repo"] and not args.production_factory:
        raise ValueError(
            "French Parakeet routing must use the real --production-factory"
        )
    if args.production_factory:
        if args.variant != "baseline" or "whisper" not in model["repo"]:
            raise ValueError("Production route requires baseline Whisper base engine")
        if args.fr_engine == "parakeet-mlx" and (
            not fr_model or "parakeet" not in fr_model["repo"]
        ):
            raise ValueError(
                "French Parakeet factory requires a verified Parakeet --fr-model-path"
            )
        if (
            args.fr_engine == "mlx-whisper"
            and fr_model
            and "whisper" not in fr_model["repo"]
        ):
            raise ValueError("Whisper French engine cannot load Parakeet weights")
    os.environ.update(
        MEMORA_MLX_MODEL_PATH=str(args.model_path.resolve()),
        MEMORA_MLX_FR_MODEL_PATH=str(args.fr_model_path.resolve())
        if args.fr_model_path
        else "",
        HF_HUB_OFFLINE="1",
        TRANSFORMERS_OFFLINE="1",
        HF_HUB_DISABLE_TELEMETRY="1",
    )
    actual_calls = []
    factory = None
    production_sources = {}
    if args.production_factory:
        os.environ.update(
            MEMORA_ASR_ENGINE="mlx-whisper",
            MEMORA_LIVE_ASR_ENGINE="mlx-whisper",
            MEMORA_FRENCH_ASR_ENGINE=args.fr_engine if fr_model else "",
            MEMORA_PARAKEET_MODEL_PATH=str(args.fr_model_path.resolve())
            if fr_model and args.fr_engine == "parakeet-mlx"
            else "",
            MEMORA_MLX_FR_MODEL_PATH=str(args.fr_model_path.resolve())
            if fr_model and args.fr_engine == "mlx-whisper"
            else "",
        )
        production_sources = {
            str(path.relative_to(ROOT)): sha(path)
            for path in (
                ROOT / "backend/api/memora/ai.py",
                ROOT / "backend/api/memora/asr_mlx.py",
                ROOT / "backend/api/memora/asr_parakeet.py",
            )
        }
        factory = production_factory(actual_calls)
    output = {
        "config": vars(args)
        | {"model_path": str(args.model_path), "adapter_path": str(args.adapter_path)},
        "corpus_sha256": manifest["corpus_sha256"],
        "adapter_sha256": production_sources.get("backend/api/memora/ai.py")
        if factory
        else sha(args.adapter_path),
        "production_sources_sha256": production_sources,
        "factory_transcribe_loaded_code_sha256": function_code_sha(factory.transcribe)
        if factory
        else None,
        "effective_adapter": "api.memora.ai.transcribe"
        if factory
        else str(args.adapter_path),
        "model": model,
        "fr_model": fr_model,
        "language_parameter_semantics": "compatibility hint only, no forced-language decoder"
        if "parakeet" in model["repo"]
        else (
            "French final Parakeet compatibility-only hint; English/auto Whisper"
            if factory and args.fr_engine == "parakeet-mlx" and fr_model
            else "Whisper forced fr/en or auto"
        ),
        "memory_before": memory_snapshot(),
        "results": [],
    }
    dest = ROOT / ".agents/logs" / ("accuracy-" + args.label + ".json")
    for row in selected:
        language = row["language"] if args.language == "native" else args.language
        selected_model = (
            args.fr_model_path
            if language == "fr" and args.fr_model_path
            else args.model_path
        )
        os.environ["MEMORA_MLX_MODEL_PATH"] = str(
            (args.model_path if factory else selected_model).resolve()
        )
        module = factory or adapter(
            args.adapter_path, args.variant, language, row["keywords"]
        )
        actual_calls.clear()
        before = memory_snapshot()
        if before["process_peak_rss_bytes"] > args.max_rss_gib * 1024**3:
            raise RuntimeError(
                "Benchmark RSS safety limit reached; partial results retained"
            )
        start = time.monotonic()
        segments = module.transcribe(Path(row["path"]), language=language)
        if factory:
            expected_engine = (
                args.fr_engine if language == "fr" and fr_model else "mlx-whisper"
            )
            if (
                len(actual_calls) != 1
                or actual_calls[0]["engine"] != expected_engine
                or actual_calls[0]["model_path"] != str(selected_model.resolve())
            ):
                raise RuntimeError(
                    "Production factory dispatch/model differs from pre-registered route"
                )
        hypothesis = " ".join(s["text"] for s in segments)
        result = row | {
            "hypothesis": hypothesis,
            "selected_model_path": str(selected_model.resolve()),
            "actual_asr_calls": list(actual_calls),
            "selected_language_parameter_semantics": "compatibility hint only, no forced-language decoder"
            if "parakeet"
            in (fr_model if language == "fr" and fr_model else model)["repo"]
            else "Whisper forced fr/en or auto",
            "selected_model_sha256": (
                fr_model if language == "fr" and fr_model else model
            )["sha256"],
            "memory_before": before,
            "memory_after": memory_snapshot(),
            "segments": segments,
            "elapsed": round(time.monotonic() - start, 3),
            "scores": score(row["reference"], hypothesis),
            "critical_results": critical(row["critical"], hypothesis),
            "false_glossary_insertions": [
                word
                for word in row.get("forbidden", [])
                if normalize(word) in normalize(hypothesis).split()
            ],
            "hallucination": not row["reference"] and bool(hypothesis.strip()),
            "requested_language": language,
        }
        output["results"].append(result)
        # Strata micro rates, never pool acoustic duplicates into unique-speech claim.
        output["summary_by_profile"] = summarize(output["results"])
        output["metric_version"] = METRIC_VERSION
        output["normalizer_numbers"] = NUMBERS
        dest.write_text(
            json.dumps(output, ensure_ascii=False, indent=2, default=str) + "\n"
        )
        print(
            row["id"], result["scores"]["numeric"]["wer"], result["elapsed"], flush=True
        )
    print("RESULT", dest, flush=True)


if __name__ == "__main__":
    main()
