"""Compare a user-authorized private audio copy with its supplied reference.

No account/database mutation, network inference or source text in console/logs.
All detailed outputs stay inside the private case directory, excluded from Git.
"""

import argparse
import hashlib
import importlib.util
import json
import os
import re
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case-dir", type=Path, required=True)
    parser.add_argument(
        "--model-path", type=Path, default=ROOT / ".memora/models/mlx-large-v3-turbo"
    )
    parser.add_argument("--language", choices=("auto", "fr", "en"), default="fr")
    parser.add_argument("--context-gap", type=float, default=0)
    parser.add_argument("--label", required=True)
    args = parser.parse_args()
    if not 0 <= args.context_gap <= 3 or (args.context_gap and args.language == "auto"):
        raise ValueError("Experimental context gap must be 0–3s with explicit language")
    private = (ROOT / ".memora/accuracy-private").resolve()
    case = args.case_dir.resolve()
    if case.parent != private or not re.fullmatch(r"[a-zA-Z0-9_-]+", args.label):
        raise ValueError("Private case directory and safe label required")
    metadata = json.loads((case / "metadata.json").read_text())
    if metadata.get("reference_pending", True) or not metadata.get("authorization"):
        raise ValueError("Explicit authorization and user reference required")
    audio = case / "audio.bin"
    if hashlib.sha256(audio.read_bytes()).hexdigest() != metadata["sha256"]:
        raise ValueError("Private audio copy changed")
    output = case / (args.label + ".json")
    if output.exists():
        raise ValueError("Output exists; use a new label to preserve evidence")
    benchmark = module(
        "accuracy_scoring", ROOT / "scripts/memora-benchmark-accuracy.py"
    )
    model = args.model_path.resolve()
    manifest = benchmark.verify_model(model)
    os.environ.update(
        MEMORA_MLX_MODEL_PATH=str(model), HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1"
    )
    # An explicit comparison model must not be overridden by the app's optional
    # French routing configuration inherited from the operator environment.
    os.environ.pop("MEMORA_MLX_FR_MODEL_PATH", None)
    adapter_path = ROOT / "backend/api/memora/asr_mlx.py"
    adapter = module("private_mlx", adapter_path)
    if args.context_gap:
        regions = adapter._speech_regions

        def contextual_regions(audio):
            grouped = []
            for region in regions(audio):
                if (
                    grouped
                    and region["start"] - grouped[-1]["end"] <= args.context_gap * 16000
                    and region["end"] - grouped[-1]["start"] <= 25 * 16000
                ):
                    grouped[-1]["end"] = region["end"]
                else:
                    grouped.append(dict(region))
            return grouped

        adapter._speech_regions = contextual_regions
    started = time.monotonic()
    segments = adapter.transcribe(audio, language=args.language)
    elapsed = time.monotonic() - started
    hypothesis = " ".join(s["text"] for s in segments)
    scores = benchmark.score((case / "reference.txt").read_text(), hypothesis)
    result = {
        "synthetic_only": False,
        "model": manifest,
        "adapter_sha256": hashlib.sha256(adapter_path.read_bytes()).hexdigest(),
        "language": args.language,
        "context_gap_seconds": args.context_gap,
        "seconds": elapsed,
        "scores": scores,
        "segments_private": segments,
        "scope": "One designated audio copy; user-supplied reference. No inference of general accuracy.",
    }
    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as target:
        json.dump(result, target, ensure_ascii=False, indent=2)
    print(
        json.dumps(
            {
                "label": args.label,
                "seconds": round(elapsed, 3),
                "strict_wer": scores["strict"]["wer"],
                "numeric_wer": scores["numeric"]["wer"],
                "private_output_saved": True,
            }
        )
    )


if __name__ == "__main__":
    main()
