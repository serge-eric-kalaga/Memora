"""Frozen synthetic independent long reports, opaque source IDs; explicit --run."""

import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "backend/test/fixtures/memora/analysis-long-cases.v1.json"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--case", help="Run only this frozen case ID")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "agents/logs/analysis-long-independent-v10.json",
    )
    args = parser.parse_args()
    corpus_sha = hashlib.sha256(CORPUS.read_bytes()).hexdigest()
    assert (
        corpus_sha == "ec64b0a74f57a7bc0419f1e7fc649fe14e14f6d166395a0282a02b1c1225449f"
    )
    corpus = json.loads(CORPUS.read_text())
    if not args.run:
        print(
            json.dumps(
                {
                    "corpus_sha256": corpus_sha,
                    "cases": len(corpus["cases"]),
                    "inference": False,
                }
            )
        )
        return
    if args.output.exists():
        raise ValueError("Refusing to overwrite evidence")
    os.environ.update(MEMORA_MODEL="gemma4:e4b", MEMORA_OLLAMA_KEEP_ALIVE="0")
    path = ROOT / "backend/api/memora/ai.py"
    spec = importlib.util.spec_from_file_location("independent_long_ai", path)
    ai = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ai)
    output = {
        "ai_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "corpus_sha256": corpus_sha,
        "model": ai.MODEL,
        "synthetic_only": True,
        "results": [],
        "raw_generations": [],
        "memory_free_percent": [],
    }
    current_case = None

    def save():
        args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2))

    generate = ai.generate

    def recorded(prompt, schema, allowed_sources=None):
        started = time.monotonic()
        result = generate(prompt, schema, allowed_sources)
        output["raw_generations"].append(
            {
                "case": current_case,
                "schema": schema.__name__,
                "seconds": round(time.monotonic() - started, 3),
                "synthetic_result": result,
            }
        )
        save()
        return result

    ai.generate = recorded
    stopped = threading.Event()

    def sample_memory():
        while not stopped.is_set():
            try:
                result = subprocess.run(
                    ["memory_pressure"],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                line = next(
                    line
                    for line in result.stdout.splitlines()
                    if line.startswith("System-wide memory free percentage:")
                )
                output["memory_free_percent"].append(
                    int(line.split(":")[1].strip().rstrip("%"))
                )
            except (OSError, subprocess.TimeoutExpired, StopIteration, ValueError):
                pass
            stopped.wait(2)

    sampler = threading.Thread(target=sample_memory, daemon=True)
    sampler.start()
    try:
        for case_number, case in enumerate(corpus["cases"]):
            if args.case and case["id"] != args.case:
                continue
            current_case = case["id"]
            reverse, segments = {}, []
            for index, source in enumerate(case["segments"]):
                ident = (
                    "r"
                    + hashlib.sha256(
                        f"{corpus_sha}:{case_number}:{index}".encode()
                    ).hexdigest()[:12]
                )
                reverse[ident] = source["id"]
                segments.append(
                    {
                        k: v
                        for k, v in {**source, "id": ident}.items()
                        if k
                        in (
                            "id",
                            "text",
                            "speaker",
                            "start",
                            "end",
                            "language",
                            "uncertain",
                        )
                    }
                )
            row = {
                "case": current_case,
                "reverse_source_ids": reverse,
                "batches": len(list(ai.batches(ai.reading_units(segments)))),
                "segment_count": len(segments),
            }
            output["results"].append(row)
            save()
            print(current_case, "batches", row["batches"], flush=True)
            started = time.monotonic()
            try:
                row["report"] = ai.report(segments, "fr")
            except Exception as error:  # noqa: BLE001 - preserve isolated benchmark failures
                row["error"] = (
                    str(error)
                    if isinstance(error, ai.ProcessingError)
                    else type(error).__name__
                )
            row["report_seconds"] = round(time.monotonic() - started, 3)
            # No questions are invented: this frozen corpus currently has none.
            if case.get("question"):
                started = time.monotonic()
                row["answer"] = ai.answer(segments, case["question"], "fr")
                row["answer_seconds"] = round(time.monotonic() - started, 3)
            save()
            print(
                current_case,
                "complete",
                row["report_seconds"],
                row.get("error"),
                flush=True,
            )
    finally:
        stopped.set()
        sampler.join(timeout=6)
        output["ai_unchanged_during_run"] = (
            hashlib.sha256(path.read_bytes()).hexdigest() == output["ai_sha256"]
        )
        save()


if __name__ == "__main__":
    main()
