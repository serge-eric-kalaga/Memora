"""Real Ollama regression for corrected speaker names, source metadata and dates.

All sources are synthetic, directly declared here; never reads meeting databases.
"""

import importlib.util
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "memora_speaker_ai", ROOT / "backend/api/memora/ai.py"
)
ai = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ai)
CASES = {
    "named_first_person": [
        {
            "id": "s1",
            "speaker": "Alice",
            "start": 0,
            "end": 4,
            "text": "Je préparerai la démonstration vendredi.",
        },
        {
            "id": "s2",
            "speaker": "Bob",
            "start": 4,
            "end": 7,
            "text": "Le budget reste une question ouverte.",
        },
    ],
    "named_fragment": [
        {
            "id": "s1",
            "speaker": "Alice",
            "start": 0,
            "end": 3,
            "text": "Je préparerai la démonstration",
        },
        {"id": "s2", "speaker": "Alice", "start": 3, "end": 4, "text": "vendredi."},
        {
            "id": "s3",
            "speaker": "Bob",
            "start": 4,
            "end": 7,
            "text": "Le budget reste une question ouverte.",
        },
    ],
    "other_speaker_unrelated_date": [
        {
            "id": "s1",
            "speaker": "Alice",
            "start": 0,
            "end": 3,
            "text": "Je préparerai la démonstration.",
        },
        {
            "id": "s2",
            "speaker": "Bob",
            "start": 3,
            "end": 7,
            "text": "Ma réunion du service marketing aura lieu vendredi.",
        },
    ],
}


def main():
    results = {}
    output = ROOT / "agents/logs/speaker-context-qa.json"
    original_generate = ai.generate
    generated = []

    def recorded_generate(prompt, schema, allowed=None):
        value = original_generate(prompt, schema, allowed)
        generated.append(
            {"schema": schema.__name__, "allowed": allowed, "synthetic_result": value}
        )
        (ROOT / "agents/logs/speaker-context-generations.json").write_text(
            json.dumps(generated, ensure_ascii=False, indent=2)
        )
        return value

    ai.generate = recorded_generate
    for name, segments in CASES.items():
        if len(sys.argv) > 1 and name not in sys.argv[1:]:
            continue
        started = time.monotonic()
        report = ai.report(segments, "fr")
        results[name] = {
            "report_seconds": round(time.monotonic() - started, 3),
            "synthetic_sources": segments,
            "report": report,
        }
        output.write_text(json.dumps(results, ensure_ascii=False, indent=2))
        print(name, "REPORT", json.dumps(report, ensure_ascii=False), flush=True)
        actions = [
            item
            for item in report["actions"]
            if item["owner"].casefold() == "alice"
            and "démonstration" in item["text"].casefold()
        ]
        assert actions, "Named first-person action not assigned to Alice"
        assert not any(
            "démonstration" in item["text"].casefold() for item in report["decisions"]
        ), "Future action misclassified as approval"
        if name == "other_speaker_unrelated_date":
            assert all(
                "vendredi" not in item["deadline"].casefold() for item in actions
            ), "Other speaker date attributed to Alice"
        else:
            expected = {"s1", "s2"} if name == "named_fragment" else {"s1"}
            assert any(
                "vendredi" in item["deadline"].casefold()
                and expected <= set(item["sources"])
                for item in actions
            ), "Action deadline or source provenance missing"
        source_backed_text = " ".join(
            item["text"]
            for key in ("summary", "topics", "decisions", "actions", "open_questions")
            for item in report[key]
        )
        assert "a décidé" not in source_backed_text.casefold(), (
            "First-person commitment paraphrased as approval"
        )
        allowed = {segment["id"] for segment in segments}
        assert all(
            item["sources"] and set(item["sources"]) <= allowed
            for key in ("summary", "topics", "decisions", "actions", "open_questions")
            for item in report[key]
        ), "Invalid report citations"
        started = time.monotonic()
        answer = ai.answer(
            segments,
            "Qui préparera la démonstration et quelle échéance est établie ?",
            "fr",
        )
        results[name].update(
            answer=answer, answer_seconds=round(time.monotonic() - started, 3)
        )
        output.write_text(json.dumps(results, ensure_ascii=False, indent=2))
        print(name, "ANSWER", json.dumps(answer, ensure_ascii=False), flush=True)
        assert "a décidé" not in answer["answer"].casefold(), (
            "Chat commitment paraphrased as approval"
        )
        assert (
            "alice" in answer["answer"].casefold()
            and answer["sources"]
            and set(answer["sources"]) <= allowed
        ), "Chat named speaker or references missing"
        if name == "other_speaker_unrelated_date":
            assert "vendredi" not in answer["answer"].casefold(), (
                "Inspect whether chat falsely attributed unrelated Friday"
            )
        else:
            assert "vendredi" in answer["answer"].casefold(), "Chat deadline missing"
        print("PASS", name, flush=True)


if __name__ == "__main__":
    main()
