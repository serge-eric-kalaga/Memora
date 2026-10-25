"""Bounded real local model report comparison on synthetic sources only."""

import importlib.util
import json
import os
import re
import subprocess
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "speaker_qa", ROOT / "scripts/memora-qa-speaker-context.py"
)
qa = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qa)
ai = qa.ai
os.environ["MEMORA_OLLAMA_KEEP_ALIVE"] = "0"
source = json.loads((ROOT / ".agents/logs/benchmark-mlx-final-auto.json").read_text())
mixed = next(
    r["segments_synthetic"]
    for r in source["results"]
    if r["case"] == "mixed" and r["engine"] == "mlx"
)
cases = {"mixed_final_asr": mixed, **qa.CASES}


def free_memory():
    result = subprocess.run(
        ["memory_pressure", "-Q"], capture_output=True, text=True, check=False
    )
    match = re.search(r"free percentage:\s*(\d+)%", result.stdout)
    return int(match.group(1)) if match else None


output = []
for model in os.environ.get("MEMORA_QA_MODELS", "qwen3.5:4b,gemma4:e4b").split(","):
    ai.MODEL = model
    for name, segments in cases.items():
        if model.startswith("qwen") and name != "mixed_final_asr":
            continue
        before = free_memory()
        # keep_alive=0 unloading may complete just after the HTTP response.
        for _ in range(30):
            if before is not None and before >= 45:
                break
            time.sleep(1)
            before = free_memory()
        if model == "gemma4:e4b" and (before is None or before < 45):
            raise RuntimeError("Insufficient free memory for bounded Gemma probe")
        samples = []
        stopped = threading.Event()

        def sample(stopped=stopped, samples=samples):
            while not stopped.wait(1):
                samples.append(free_memory())

        sampler = threading.Thread(target=sample, daemon=True)
        sampler.start()
        started = time.monotonic()
        report = ai.report(segments, "fr")
        stopped.set()
        sampler.join()
        row = {
            "memory_free_percent_before": before,
            "memory_free_percent_during_min": min(
                (v for v in samples if v is not None), default=None
            ),
            "memory_free_percent_after": free_memory(),
            "model": model,
            "case": name,
            "seconds": round(time.monotonic() - started, 3),
            "synthetic_sources": segments,
            "report": report,
        }
        output.append(row)
        (ROOT / ".agents/logs/modality-models.json").write_text(
            json.dumps(output, ensure_ascii=False, indent=2)
        )
        print(json.dumps(row, ensure_ascii=False), flush=True)
