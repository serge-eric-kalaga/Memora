"""Real local speaker retry -> report on synthetic reference; isolated DB and auth seam."""

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
with tempfile.TemporaryDirectory(prefix="memora-speaker-retry-") as folder:
    os.environ.update(
        APP_NAME="Synthetic retry",
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
        MEMORA_DATA_DIR=folder + "/data",
        MEMORA_DISABLE_WORKER="1",
        MEMORA_MODEL="gemma4:e4b",
        MEMORA_OLLAMA_URL="http://127.0.0.1:11434",
        MEMORA_DIARIZATION_MODEL_DIR=str(ROOT / ".memora/models/resemblyzer-0.1.4"),
        HF_HUB_OFFLINE="1",
        TRANSFORMERS_OFFLINE="1",
    )
    from api.memora import store as s
    from api.memora import worker
    from pytest import MonkeyPatch
    from test.test_memora_domain import PREFIX, create, seed
    from test.test_memora_domain import client as fixture

    refs = json.loads(
        (ROOT / ".memora/qa/diarization-reserve/references.json").read_text()
    )
    case = next(c for c in refs["cases"] if c["id"] == "reserve-two-return")
    source = [
        {**seg, "speaker": "Intervenant non identifié"} for seg in case["segments"]
    ]
    for seg in source:
        seg.pop("speaker_id", None)
    with MonkeyPatch.context() as mp:
        generator = fixture.__wrapped__(Path(folder), mp)
        client = next(generator)
        try:
            mid = create(client)
            seed(mid)
            (s.ROOT / mid).mkdir(exist_ok=True)
            shutil.copyfile(case["path"], s.ROOT / mid / "audio.bin")
            with s.db() as c:
                m = s.meeting(c, mid)
                m["automatic_diarization"] = {"state": "failed", "source_version": 1}
                m["settings"]["email_notifications"] = False
                s.save(c, m)
                c.execute(
                    "UPDATE transcripts SET data=? WHERE meeting=? AND version=1",
                    (json.dumps(source), mid),
                )
            start = time.monotonic()
            r = client.post(
                PREFIX + "/meetings/" + mid + "/analyze",
                json={"request_id": "synthetic-real-retry", "num_speakers": 2},
            )
            assert r.status_code == 200, r.text
            with s.db() as c:
                job = dict(
                    c.execute(
                        "SELECT * FROM jobs WHERE id=?", (r.json()["job_id"],)
                    ).fetchone()
                )
            worker.process(job)
            with s.db() as c:
                m = s.meeting(c, mid)
                labelled = s.transcript(c, mid, 2)
                assert (
                    m["state"] == "ready"
                    and m["version"] == 2
                    and m["report_version"] == 2
                )
                assert s.transcript(c, mid, 1) == source
                assert all(
                    all(a[k] == b[k] for k in ("id", "start", "end", "text"))
                    for a, b in zip(source, labelled, strict=True)
                )
                assert (
                    len(
                        {seg["speaker_id"] for seg in labelled if seg.get("speaker_id")}
                    )
                    == 2
                )
                assert (
                    c.execute(
                        "SELECT count(*) FROM reports WHERE meeting=?", (mid,)
                    ).fetchone()[0]
                    == 2
                )
            print(
                json.dumps(
                    {
                        "synthetic_only": True,
                        "auth_overridden": True,
                        "real_local_diarization_and_report": True,
                        "seconds": round(time.monotonic() - start, 3),
                        "groups": 2,
                        "source_unchanged": True,
                        "old_report_retained": True,
                        "report_version": 2,
                    }
                )
            )
        finally:
            next(generator, None)
