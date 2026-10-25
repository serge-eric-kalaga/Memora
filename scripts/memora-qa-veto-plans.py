"""Plan-only V11 probe from preserved real map outputs, never a full rerun."""

import argparse
import hashlib
import importlib.util
import json
import os
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true")
    parser.add_argument(
        "--output", type=Path, default=ROOT / ".agents/logs/analysis-veto-plans-v11.json"
    )
    args = parser.parse_args()
    pairs = [
        (
            "backend/test/fixtures/memora/analysis-long-cases.v1.json",
            ".agents/logs/analysis-long-independent-v10.json",
        ),
        (
            "backend/test/fixtures/memora/analysis/cross-batch-v1.json",
            ".agents/logs/analysis-cross-batch-v10.json",
        ),
    ]
    if not args.run:
        print("Five cached map cases; no inference. Explicit --run required.")
        return
    if args.output.exists():
        raise ValueError("Refusing overwrite")
    os.environ.update(MEMORA_MODEL="gemma4:e4b", MEMORA_OLLAMA_KEEP_ALIVE="0")
    path = ROOT / "backend/api/memora/ai.py"
    spec = importlib.util.spec_from_file_location("veto_probe_ai", path)
    ai = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ai)
    output = {
        "scope": "plan-only cached real map generations; not end-to-end",
        "ai_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "inputs": [],
        "results": [],
        "raw_generations": [],
    }
    current = None

    def save():
        args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2))

    generate = ai.generate

    def recorded(prompt, schema, allowed_sources=None):
        started = time.monotonic()
        result = generate(prompt, schema, allowed_sources)
        output["raw_generations"].append(
            {
                "case": current,
                "schema": schema.__name__,
                "schema_base": schema.__bases__[0].__name__,
                "seconds": round(time.monotonic() - started, 3),
                "synthetic_result": result,
            }
        )
        save()
        return result

    ai.generate = recorded
    for corpus_name, baseline_name in pairs:
        corpus_path, baseline_path = ROOT / corpus_name, ROOT / baseline_name
        corpus, baseline = (
            json.loads(corpus_path.read_text()),
            json.loads(baseline_path.read_text()),
        )
        output["inputs"].append(
            {
                "corpus": corpus_name,
                "corpus_sha256": hashlib.sha256(corpus_path.read_bytes()).hexdigest(),
                "baseline": baseline_name,
                "baseline_sha256": hashlib.sha256(
                    baseline_path.read_bytes()
                ).hexdigest(),
            }
        )
        cursor = 0
        for case, previous in zip(corpus["cases"], baseline["results"], strict=True):
            current = case["id"]
            mapping = {v: k for k, v in previous.get("reverse_source_ids", {}).items()}
            segments = [
                {
                    k: v
                    for k, v in {**s, "id": mapping.get(s["id"], s["id"])}.items()
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
                for s in case["segments"]
            ]
            count = len(list(ai.batches(ai.reading_units(segments))))
            if mapping:
                raws = [
                    g["synthetic_result"]
                    for g in baseline["raw_generations"]
                    if g["case"] == current and g["schema"] == "Report"
                ]
            else:
                raw_maps = [
                    g["synthetic_result"]
                    for g in baseline["raw_generations"]
                    if g["schema"] == "Report"
                ]
                raws = raw_maps[cursor : cursor + count]
                cursor += count
            assert len(raws) == count
            allowed = {s["id"] for s in segments}
            parts = []
            for raw in raws:
                part = ai.Report().model_dump()
                for field in ai._REPORT_FIELDS:
                    part[field] = [
                        dict(item)
                        for item in raw[field]
                        if item["sources"]
                        and set(item["sources"]) <= allowed
                        and item["text"].strip(" \t\r\n.!?").casefold()
                        not in {
                            "non précisé",
                            "non précisée",
                            "not specified",
                            "aucune action",
                            "aucune question ouverte",
                            "no action",
                            "no open question",
                        }
                    ]
                assert part["summary"]
                parts.append(part)
            row = {
                "case": current,
                "parts": len(parts),
                "candidate_count": len(ai._report_candidates(parts)),
                "reverse_source_ids": previous.get("reverse_source_ids", {}),
            }
            output["results"].append(row)
            started = time.monotonic()
            print(current, "plan start", row["candidate_count"], flush=True)
            try:
                row["report"] = ai.reconcile(parts, segments, "fr", ai.Report)
            except ai.ProcessingError as error:
                row["error"] = str(error)
            row["seconds"] = round(time.monotonic() - started, 3)
            save()
            print(current, "complete", row["seconds"], row.get("error"), flush=True)
    output["ai_unchanged_during_run"] = (
        hashlib.sha256(path.read_bytes()).hexdigest() == output["ai_sha256"]
    )
    save()


if __name__ == "__main__":
    main()
