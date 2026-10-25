"""Two fixed synthetic multi-batch report/chat cases; no application data."""

import argparse
import hashlib
import importlib.util
import json
import os
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "backend/test/fixtures/memora/analysis/cross-batch-v1.json"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", action="store_true")
    parser.add_argument(
        "--output", type=Path, default=ROOT / ".agents/logs/analysis-cross-batch-v1.json"
    )
    args = parser.parse_args()
    corpus = json.loads(CORPUS.read_text())
    print("corpus_sha256", hashlib.sha256(CORPUS.read_bytes()).hexdigest(), flush=True)
    if not args.run:
        print([(c["id"], len(c["segments"])) for c in corpus["cases"]])
        return
    os.environ.update(MEMORA_MODEL="gemma4:e4b", MEMORA_OLLAMA_KEEP_ALIVE="0")
    path = ROOT / "backend/api/memora/ai.py"
    spec = importlib.util.spec_from_file_location("cross_batch_ai", path)
    ai = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ai)
    output = {
        "ai_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "corpus_sha256": hashlib.sha256(CORPUS.read_bytes()).hexdigest(),
        "synthetic_only": True,
        "results": [],
    }
    target = args.output
    if target.exists():
        raise ValueError("Refusing to overwrite evidence")
    generate = ai.generate
    output["raw_generations"] = []

    def recorded(prompt, schema, allowed_sources=None):
        started = time.monotonic()
        result = generate(prompt, schema, allowed_sources)
        output["raw_generations"].append(
            {
                "schema": schema.__name__,
                "seconds": round(time.monotonic() - started, 3),
                "synthetic_result": result,
            }
        )
        target.write_text(json.dumps(output, ensure_ascii=False, indent=2))
        return result

    ai.generate = recorded
    for case in corpus["cases"]:
        units = ai.reading_units(case["segments"])
        batches = list(ai.batches(units))
        assert len(batches) > 2
        print(case["id"], "batches", len(batches), flush=True)
        started = time.monotonic()
        report = ai.report(case["segments"], "fr")
        row = {
            "case": case["id"],
            "batches": len(batches),
            "report_seconds": round(time.monotonic() - started, 3),
            "report": report,
        }
        output["results"].append(row)
        target.write_text(json.dumps(output, ensure_ascii=False, indent=2))
        print(case["id"], "report complete", flush=True)
        started = time.monotonic()
        row.update(
            answer=ai.answer(case["segments"], case["question"], "fr"),
            answer_seconds=round(time.monotonic() - started, 3),
        )
        target.write_text(json.dumps(output, ensure_ascii=False, indent=2))
        print(case["id"], "chat complete", flush=True)


if __name__ == "__main__":
    main()
