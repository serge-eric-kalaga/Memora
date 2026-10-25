"""Real local Gemma follow-up on fixed synthetic transcript; no application data."""

import importlib.util
import json
import os
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ["MEMORA_MODEL"] = "gemma4:e4b"
os.environ["MEMORA_OLLAMA_URL"] = "http://127.0.0.1:11434"
spec = importlib.util.spec_from_file_location(
    "synthetic_conversation_ai", ROOT / "backend/api/memora/ai.py"
)
ai = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ai)
segments = [
    {
        "id": "s1",
        "start": 0,
        "end": 6,
        "speaker": "Alice",
        "text": "Je préparerai le dossier Saphir pour vendredi.",
    },
    {
        "id": "s2",
        "start": 7,
        "end": 12,
        "speaker": "Bob",
        "text": "Je présenterai la démonstration mardi.",
    },
    {
        "id": "s3",
        "start": 13,
        "end": 19,
        "speaker": "Alice",
        "text": "Aucun budget du dossier Saphir n’a été établi.",
    },
]
questions = [
    "Qui préparera le dossier Saphir ?",
    "Et son échéance ?",
    "Et quel est son budget ?",
]
history = []
results = []
for index, question in enumerate(questions):
    start = time.monotonic()
    result = ai.answer(segments, question, "fr", history)
    print(
        json.dumps({"turn": index, "question": question, **result}, ensure_ascii=False),
        file=__import__("sys").stderr,
        flush=True,
    )
    assert set(result["sources"]) <= {"s1", "s2", "s3"}
    if index == 0:
        assert "alice" in result["answer"].lower() and "s1" in result["sources"]
    elif index == 1:
        assert (
            "vendredi" in result["answer"].lower()
            and "mardi" not in result["answer"].lower()
            and "s1" in result["sources"]
        )
    else:
        assert any(
            term in result["answer"].lower()
            for term in ("aucun", "pas", "non", "absent")
        )
        import re

        assert not re.search(
            r"\b\d+[.,]?\d*\s*(?:euros?|dollars?|€|\$)", result["answer"], re.IGNORECASE
        ), result
    results.append(
        {"question": question, "seconds": round(time.monotonic() - start, 3), **result}
    )
    history.append({"question": question, **result})
print(
    json.dumps(
        {"synthetic_only": True, "model": ai.MODEL, "checks": 3, "results": results},
        ensure_ascii=False,
        indent=2,
    )
)
