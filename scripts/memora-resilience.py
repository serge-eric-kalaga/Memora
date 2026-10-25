"""Real local provider failure/recovery on disposable synthetic data, no global service changes."""

import json
import os
import sys
import tempfile
import time
from pathlib import Path

import httpx

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "backend"))
with tempfile.TemporaryDirectory(prefix="memora-resilience-") as temp:
    os.environ.update(
        MEMORA_DATA_DIR=temp,
        APP_NAME="Memora resilience",
        ADMINS_EMAIL="test@example.org",
        SECRET_KEY="synthetic-test-only",
        JWT_SECRET="synthetic-test-only",
        ALGORITHM="HS256",
        DATABASE_URL="sqlite://",
    )
    from api.memora import ai
    from api.memora import store as s
    from api.memora import worker as w

    s.init()
    mid = s.uid()
    with s.db() as c:
        m = {
            "id": mid,
            "owner": 1,
            "title": "Réunion synthétique résilience",
            "version": 1,
            "state": "queued",
            "report_version": None,
            "settings": s.DEFAULTS,
            "email": None,
        }
        c.execute("INSERT INTO meetings VALUES(?,?,?)", (mid, 1, json.dumps(m)))
        c.execute(
            "INSERT INTO transcripts VALUES(?,?,?,?,?)",
            (
                mid,
                1,
                json.dumps(
                    [
                        {
                            "id": "s1",
                            "text": "Nous décidons de conserver le budget inchangé.",
                        }
                    ]
                ),
                "synthetic",
                time.time(),
            ),
        )
        jid = s.enqueue(c, mid, "pipeline", 1)
    original = ai.MODEL
    ai.MODEL = "memora-model-deliberately-unavailable:synthetic"
    job = {"id": jid, "meeting": mid, "kind": "pipeline", "version": 1}
    try:
        w.process(job)
        raise AssertionError("Missing model must fail")
    except httpx.HTTPStatusError as exc:
        assert exc.response.status_code == 404
        w.fail_job(job, "Modèle synthétique indisponible")
        with s.db() as c:
            assert s.meeting(c, mid)["state"] == "failed"
            assert len(s.transcript(c, mid)) == 1
            c.execute("UPDATE jobs SET state='failed' WHERE id=?", (jid,))
        print("PASS real unavailable model preserves source and marks failure")
    finally:
        ai.MODEL = original
    with s.db() as c:
        jid = s.enqueue(c, mid, "pipeline", 1)
    w.process({"id": jid, "meeting": mid, "kind": "pipeline", "version": 1})
    with s.db() as c:
        assert s.meeting(c, mid)["state"] == "ready"
        assert c.execute("SELECT count(*) FROM reports").fetchone()[0] == 1
    print("PASS restored local model generates actual report without reimport")
