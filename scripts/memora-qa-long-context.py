"""Real local LLM check: final synthetic fact beyond the first source batch."""

import importlib.util
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
spec = importlib.util.spec_from_file_location(
    "memora_long_context_ai", ROOT / "backend/api/memora/ai.py"
)
ai = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ai)
segments = [
    {
        "id": f"s{i}",
        "start": i * 30,
        "end": i * 30 + 25,
        "speaker": "Intervenant non identifié",
        "language": "fr",
        "uncertain": False,
        "text": "Le groupe examine les modalités de suivi du projet. " * 12,
    }
    for i in range(55)
]
segments.append(
    {
        "id": "s-final",
        "start": 1650,
        "end": 1660,
        "speaker": "Alice",
        "language": "fr",
        "uncertain": False,
        "text": "Je préparerai le dossier Zéphyr vendredi.",
    }
)
units = ai.reading_units(segments)
metadata = {
    "synthetic_only": True,
    "segments": len(segments),
    "batches": len(list(ai.batches(units))),
    "results": {},
}
assert metadata["batches"] > 1
started = time.monotonic()
report = ai.report(segments, "fr")
assert any(
    "s-final" in item["sources"]
    and item["owner"] == "Alice"
    and "vendredi" in item["deadline"].lower()
    for item in report["actions"]
), report["actions"]
metadata["results"]["report"] = {
    "seconds": round(time.monotonic() - started, 3),
    "result": report,
}
print("PASS final action in report", flush=True)
started = time.monotonic()
answer = ai.answer(segments, "Qui préparera le dossier Zéphyr et quand ?", "fr")
assert (
    "s-final" in answer["sources"]
    and "alice" in answer["answer"].lower()
    and "vendredi" in answer["answer"].lower()
), answer
metadata["results"]["chat"] = {
    "seconds": round(time.monotonic() - started, 3),
    "result": answer,
}
print("PASS final fact and citation in chat", flush=True)
(ROOT / "agents/logs/long-context.json").write_text(
    json.dumps(metadata, ensure_ascii=False, indent=2) + "\n"
)
print(
    json.dumps(
        {
            "batches": metadata["batches"],
            "seconds": {k: v["seconds"] for k, v in metadata["results"].items()},
        }
    ),
    flush=True,
)
