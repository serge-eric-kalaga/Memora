"""Exactly one real local Gemma report generation on the synthetic Alice/Bob case.

Model override is limited to this process. This does not change the app default.
"""

import importlib.util
import json
import os
import re
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "gemma_synthetic_qa", ROOT / "scripts/memora-qa-speaker-context.py"
)
qa = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qa)


def main():
    memory = subprocess.run(
        ["memory_pressure", "-Q"], capture_output=True, text=True, check=True
    )
    match = re.search(r"free percentage:\s*(\d+)%", memory.stdout)
    free = int(match.group(1)) if match else None
    if free is None or free < 50:
        raise RuntimeError(
            "Gemma comparison skipped: less than 50 percent system free memory or unknown status; no generation."
        )
    os.environ["MEMORA_OLLAMA_KEEP_ALIVE"] = "0"
    print(
        f"Gemma one-generation caller PID {os.getpid()}, free memory {free}%; keep_alive=0",
        flush=True,
    )
    previous = qa.ai.MODEL
    generate = qa.ai.generate
    trace = []

    def recorded(prompt, schema, allowed=None):
        if trace:
            raise RuntimeError("Only one model generation authorized in this probe")
        trace.append({"call_started": True})
        result = generate(prompt, schema, allowed)
        trace[0]["synthetic_result"] = result
        return result

    qa.ai.generate = recorded
    started = time.monotonic()
    output = {
        "model": "gemma4:e4b",
        "synthetic_only": True,
        "system_free_percent_before": free,
        "keep_alive": 0,
        "case": "other_speaker_unrelated_date",
    }
    try:
        qa.ai.MODEL = "gemma4:e4b"
        segments = qa.CASES["other_speaker_unrelated_date"]
        report = qa.ai.report(segments, "fr")
        actions = [
            item
            for item in report["actions"]
            if item["owner"].casefold() == "alice"
            and "démonstration" in item["text"].casefold()
        ]
        items = [
            item
            for key in ("summary", "topics", "decisions", "actions", "open_questions")
            for item in report[key]
        ]
        allowed = {s["id"] for s in segments}
        output.update(
            report=report,
            synthetic_sources=segments,
            checks={
                "summary_present": bool(report["summary"]),
                "alice_action_present": bool(actions),
                "alice_deadline_not_friday": bool(actions)
                and all(
                    "vendredi" not in item["deadline"].casefold() for item in actions
                ),
                "decisions_empty": not report["decisions"],
                "literal_a_decide_absent": all(
                    "a décidé" not in item["text"].casefold() for item in items
                ),
                "all_citations_nonempty_and_authorized": all(
                    item["sources"] and set(item["sources"]) <= allowed
                    for item in items
                ),
            },
        )
    finally:
        qa.ai.MODEL = previous
        qa.ai.generate = generate
        output.update(
            wall_seconds=round(time.monotonic() - started, 3),
            generation_count=len(trace),
            raw_synthetic_generations=trace,
            application_default_unchanged=True,
        )
        (ROOT / "agents/logs/gemma-report-comparison.json").write_text(
            json.dumps(output, ensure_ascii=False, indent=2)
        )
        print(json.dumps(output, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
