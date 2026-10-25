"""Isolated plan-only probe using preserved real map candidates; --run is explicit.

This is NOT a fresh end-to-end transcript analysis. No map calls or audio.
"""

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
    parser.add_argument("--model", default="gemma4:e4b")
    parser.add_argument("--active-only", action="store_true")
    parser.add_argument(
        "--output", type=Path, default=ROOT / ".agents/logs/analysis-plan-v6.json"
    )
    args = parser.parse_args()
    os.environ.update(MEMORA_MODEL=args.model, MEMORA_OLLAMA_KEEP_ALIVE="0")
    path = ROOT / "backend/api/memora/ai.py"
    spec = importlib.util.spec_from_file_location("plan_probe_ai", path)
    ai = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ai)
    if args.active_only:
        original_candidates = ai._report_candidates
        original_payload = ai._chronological_payload

        def active_candidates(reports):
            records = [
                r
                for r in original_candidates(reports)
                if r["category"] in ("actions", "decisions", "open_questions")
            ]
            return [{**r, "id": f"c{i + 1}"} for i, r in enumerate(records)]

        def active_payload(reports, positions):
            records = active_candidates(reports)
            allowed = {s for r in records for s in r["item"]["sources"]}
            data = json.loads(original_payload(reports, positions))
            data["source_order"] = [
                s for s in data["source_order"] if s["id"] in allowed
            ]
            used = {s["text_ref"] for s in data["source_order"]}
            data["literal_texts"] = {
                k: v for k, v in data["literal_texts"].items() if k in used
            }
            return json.dumps(data, ensure_ascii=False)

        ai._report_candidates = active_candidates
        ai._chronological_payload = active_payload
    corpus_path = ROOT / "backend/test/fixtures/memora/analysis/cross-batch-v1.json"
    baseline_path = ROOT / ".agents/logs/analysis-cross-batch-v1.json"
    corpus = json.loads(corpus_path.read_text())
    baseline = json.loads(baseline_path.read_text())
    output = {
        "model": args.model,
        "active_only_experiment": args.active_only,
        "scope": "plan-only on preserved real map candidates; not fresh end-to-end",
        "ai_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "corpus_sha256": hashlib.sha256(corpus_path.read_bytes()).hexdigest(),
        "baseline_sha256": hashlib.sha256(baseline_path.read_bytes()).hexdigest(),
        "results": [],
    }
    trace = []
    generate = ai.generate

    def recorded(prompt, schema, allowed):
        started = time.monotonic()
        result = generate(prompt, schema, allowed)
        trace.append(
            {
                "schema": schema.__name__,
                "seconds": round(time.monotonic() - started, 3),
                "synthetic_result": result,
            }
        )
        # Persist synthetic raw plans before local validation can reject them.
        output["raw_plans"] = trace
        args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2))
        return result

    ai.generate = recorded
    if args.run and args.output.exists():
        raise ValueError("Refusing to overwrite evidence")
    for case, old in zip(corpus["cases"], baseline["results"], strict=True):
        parts = []
        for batch in ai.batches(ai.reading_units(case["segments"])):
            ids = {source for unit in batch for source in unit["source_ids"]}
            part = ai.Report().model_dump()
            for category in ai._REPORT_FIELDS:
                part[category] = [
                    item
                    for item in old["report"][category]
                    if set(item["sources"]) <= ids
                ]
            parts.append(part)
        assert sum(
            len(part[field]) for part in parts for field in ai._REPORT_FIELDS
        ) == sum(len(old["report"][field]) for field in ai._REPORT_FIELDS)
        positions = {
            segment["id"]: {
                "id": segment["id"],
                "position": i,
                "start": segment.get("start"),
                "end": segment.get("end"),
                "speaker": segment.get("speaker"),
                "text": segment["text"],
            }
            for i, segment in enumerate(case["segments"])
        }
        payload = ai._chronological_payload(parts, positions)
        row = {
            "case": case["id"],
            "parts": len(parts),
            "candidate_count": len(ai._report_candidates(parts)),
            "payload_characters": len(payload),
        }
        print(json.dumps(row), flush=True)
        if args.run:
            before = len(trace)
            started = time.monotonic()
            try:
                row["report"] = ai.reconcile(parts, case["segments"], "fr", ai.Report)
                if args.active_only:
                    for category in ("summary", "topics"):
                        row["report"][category] = [
                            {
                                **item,
                                "text": f"À la position {min(positions[s]['position'] for s in item['sources']) + 1} dans la réunion : {item['text']}",
                            }
                            for part in parts
                            for item in part[category]
                        ]
            except ai.ProcessingError as error:
                row["validation_error"] = str(error)
            row.update(
                seconds=round(time.monotonic() - started, 3), plans=trace[before:]
            )
            output["results"].append(row)
            args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2))
            print(case["id"], "plan complete", flush=True)


if __name__ == "__main__":
    main()
