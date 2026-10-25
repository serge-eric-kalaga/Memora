"""Real synthetic initial ASR -> local voice groups -> report; disposable domain only."""

import json
import os
import secrets
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
with tempfile.TemporaryDirectory(prefix="memora-auto-speakers-") as folder:
    os.environ.update(
        APP_NAME="Synthetic speaker QA",
        ADMINS_EMAIL="test@example.org",
        SECRET_KEY=secrets.token_hex(32),
        JWT_SECRET=secrets.token_hex(32),
        ALGORITHM="HS256",
        DATABASE_URL="sqlite:///" + folder + "/auth.sqlite3",
        INITIALISE_DATABASE="false",
        CACHE_ENABLED="false",
        RATE_LIMIT_ENABLED="false",
        EMAIL_HOST="127.0.0.1",
        EMAIL_PORT="1025",
        EMAIL_DOMAIN="synthetic@localhost",
        MEMORA_DATA_DIR=folder,
        MEMORA_DISABLE_WORKER="1",
        MEMORA_ASR_ENGINE="mlx-whisper",
        MEMORA_MLX_MODEL_PATH=str(ROOT / ".memora/models/mlx-whisper"),
        MEMORA_MODEL="gemma4:e4b",
        MEMORA_OLLAMA_URL="http://127.0.0.1:11434",
        HF_HUB_OFFLINE="1",
        TRANSFORMERS_OFFLINE="1",
    )
    # Fixed public-model path, not private application configuration.
    candidates = [
        ROOT / ".memora/models/mlx-whisper",
        ROOT / ".memora/models/mlx-large-v3-turbo",
    ]
    os.environ["MEMORA_MLX_MODEL_PATH"] = str(
        next(p for p in candidates if (p / "memora-model.json").exists())
    )
    from api.memora import diarization, worker
    from api.memora import store as s

    refs = json.loads(
        (ROOT / ".memora/qa/diarization-reserve/references.json").read_text()
    )
    case = next(c for c in refs["cases"] if c["id"] == "reserve-two-return")
    audio = Path(case["path"])
    started = time.monotonic()
    direct = diarization.diarize(audio, case["segments"])
    assert direct["metadata"]["speaker_count"] == 2
    assert (
        len({x.get("speaker_id") for x in direct["segments"] if x.get("speaker_id")})
        == 2
    )
    for before, after in zip(case["segments"], direct["segments"], strict=True):
        assert all(before[k] == after[k] for k in ("id", "text", "start", "end"))
    metadata = {
        "synthetic_only": True,
        "direct": {
            "seconds": round(time.monotonic() - started, 3),
            "groups": 2,
            "segments": len(direct["segments"]),
            "labels": [x["speaker"] for x in direct["segments"]],
        },
    }
    if "--cpu-only" in sys.argv:
        print(json.dumps(metadata, indent=2))
        raise SystemExit(0)
    s.init()
    mid = secrets.token_hex(16)
    (s.ROOT / mid).mkdir()
    shutil.copyfile(audio, s.ROOT / mid / "audio.bin")
    settings = {
        **s.DEFAULTS,
        "email_notifications": False,
        "auto_diarization_new_meetings": True,
        "report_language": "en",
    }
    meeting = {
        "id": mid,
        "owner": 1,
        "owner_uid": "synthetic-" + secrets.token_hex(16),
        "title": "Synthetic two-voice initial analysis",
        "mode": "import",
        "created": time.time(),
        "updated": time.time(),
        "state": "queued",
        "version": 0,
        "report_version": None,
        "report_id": None,
        "settings": settings,
        "duration": case["duration"],
        "audio_expires_at": time.time() + 86400,
        "audio_expired": False,
        "archived": False,
        "email": None,
        "transcription_language": "en",
    }
    with s.db() as c:
        c.execute("INSERT INTO meetings VALUES(?,?,?)", (mid, 1, json.dumps(meeting)))
        jid = s.enqueue(c, mid, "pipeline", 0)
        job = dict(c.execute("SELECT * FROM jobs WHERE id=?", (jid,)).fetchone())
    started = time.monotonic()
    worker.process(job)
    with s.db() as c:
        current = s.meeting(c, mid)
        first = s.transcript(c, mid, 1)
        second = s.transcript(c, mid, 2)
        assert current["state"] == "ready", current.get("error")
        assert current["version"] == 2 and current["report_version"] == 2
        assert current["automatic_diarization"]["state"] == "completed"
        assert first and len(first) == len(second)
        assert all(
            all(a[k] == b[k] for k in ("id", "start", "end", "text"))
            for a, b in zip(first, second, strict=True)
        )
        labels = [x.get("speaker_id") for x in second if x.get("speaker_id")]
        assert len(set(labels)) == 2, labels
        assert all(x["speaker"] == "Intervenant non identifié" for x in first)
        assert (
            c.execute(
                "SELECT count(*) FROM reports WHERE meeting=?", (mid,)
            ).fetchone()[0]
            == 1
        )
        metadata["pipeline"] = {
            "seconds": round(time.monotonic() - started, 3),
            "state": current["state"],
            "version": current["version"],
            "report_version": current["report_version"],
            "asr_segments": len(first),
            "labelled_segments": len(labels),
            "groups": len(set(labels)),
            "immutable_text_times": True,
            "labels": [x["speaker"] for x in second],
        }
    print(json.dumps(metadata, indent=2))
