"""Crash durability on disposable SQLite, synthetic ASR/report only."""

import json
from pathlib import Path

import pytest
from api.memora import store as s, worker as w

SEGMENTS = [{"id": "s1", "start": 0, "end": 1, "text": "Synthetic source"}]
REPORT = {
    "summary": [{"text": "Synthetic", "sources": ["s1"]}],
    "topics": [],
    "decisions": [],
    "actions": [],
    "open_questions": [],
    "limitations": "",
}


@pytest.mark.parametrize("kind,initial", [("pipeline", 0), ("retranscribe", 1)])
def test_resume_after_asr_commit_does_not_repeat_asr(
    tmp_path, monkeypatch, kind, initial
):
    monkeypatch.setattr(s, "ROOT", tmp_path / "resume")
    s.init()
    mid = "synthetic-resume"
    (s.ROOT / mid).mkdir()
    (s.ROOT / mid / "audio.bin").write_bytes(b"synthetic-placeholder")
    with s.db() as c:
        m = {
            "id": mid,
            "owner_uid": "synthetic-owner",
            "title": "Synthetic",
            "version": initial,
            "state": "queued",
            "settings": dict(s.DEFAULTS),
        }
        c.execute("INSERT INTO meetings VALUES(?,?,?)", (mid, 1, json.dumps(m)))
        if initial:
            c.execute(
                "INSERT INTO transcripts VALUES(?,?,?,?,?)",
                (mid, initial, json.dumps(SEGMENTS), "Previous synthetic", 0),
            )
        jid = s.enqueue(c, mid, kind, initial)
        c.execute("UPDATE jobs SET state='running' WHERE id=?", (jid,))
        job = dict(c.execute("SELECT * FROM jobs WHERE id=?", (jid,)).fetchone())
    calls = []
    monkeypatch.setattr(
        w.ai, "transcribe", lambda *a, **k: calls.append(True) or SEGMENTS
    )
    monkeypatch.setattr(
        w.ai,
        "report",
        lambda *a, **k: (_ for _ in ()).throw(SystemExit("synthetic process death")),
    )
    with pytest.raises(SystemExit):
        w.process(job)
    with s.db() as c:
        assert s.meeting(c, mid)["version"] == initial + 1
        checkpoint = c.execute("SELECT * FROM jobs WHERE id=?", (jid,)).fetchone()
        assert checkpoint["state"] == "running"
        assert checkpoint["phase"] == "report"
        assert checkpoint["source_version"] == initial + 1
        assert checkpoint["version"] == initial
        assert checkpoint["result_report_id"] is None
        # An API request now sees the committed source version, not initial job.version.
        assert s.enqueue(c, mid, kind, initial + 1) == jid
    s.init()  # Same restart/requeue behavior as application startup.
    with s.db() as c:
        resumed = dict(c.execute("SELECT * FROM jobs WHERE id=?", (jid,)).fetchone())
        assert resumed["state"] == "queued"
    monkeypatch.setattr(w.ai, "report", lambda *a, **k: REPORT)
    w.process(resumed)
    w.process(resumed)  # Crash after report commit, before worker marks job done.
    with s.db() as c:
        result = s.meeting(c, mid)
        assert result["state"] == "ready"
        assert result["report_version"] == initial + 1
        assert c.execute("SELECT COUNT(*) FROM reports").fetchone()[0] == 1
        checkpoint = c.execute("SELECT * FROM jobs WHERE id=?", (jid,)).fetchone()
        assert checkpoint["phase"] == "complete"
        assert checkpoint["result_report_id"] == result["report_id"]
        assert (
            c.execute("SELECT COUNT(*) FROM transcripts").fetchone()[0] == initial + 1
        )
        if initial:
            assert s.transcript(c, mid, initial) == SEGMENTS
    assert calls == [True]


def test_active_checkpoint_deduplicates_current_source_but_allows_new_revision(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(s, "ROOT", tmp_path / "dedupe")
    s.init()
    with s.db() as c:
        c.execute(
            "INSERT INTO meetings VALUES(?,?,?)",
            ("synthetic", 1, json.dumps({"version": 2})),
        )
        old = s.enqueue(c, "synthetic", "pipeline", 0)
        c.execute(
            "UPDATE jobs SET source_version=1,phase='report',state='running' WHERE id=?",
            (old,),
        )
        assert s.enqueue(c, "synthetic", "pipeline", 1) == old
        new = s.enqueue(c, "synthetic", "pipeline", 2)
        assert new != old
        assert s.enqueue(c, "synthetic", "pipeline", 2) == new
        assert c.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 2


def test_checkpoint_migration_is_additive_and_repeatable(tmp_path, monkeypatch):
    monkeypatch.setattr(s, "ROOT", tmp_path / "legacy")
    with s.db() as c:
        c.executescript(
            (Path(s.__file__).parent / "migrations/001_initial.sql").read_text()
        )
        c.execute(
            "INSERT INTO meetings VALUES(?,?,?)",
            ("legacy", 1, json.dumps({"version": 0})),
        )
        c.execute(
            "INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?)",
            ("legacy-job", "legacy", "pipeline", 0, "queued", None, 0, None),
        )
    s.init()
    s.init()
    with s.db() as c:
        row = c.execute("SELECT * FROM jobs WHERE id='legacy-job'").fetchone()
        assert row["phase"] == "source" and row["source_version"] is None
        assert row["result_report_id"] is None and row["version"] == 0
        assert (
            c.execute("SELECT COUNT(*) FROM schema_version WHERE version=6").fetchone()[
                0
            ]
            == 1
        )


@pytest.mark.parametrize(
    "job_version,job_state,active", [(0, "done", None), (1, "failed", "missing-job")]
)
def test_startup_reconciles_orphaned_processing_without_losing_history(
    tmp_path, monkeypatch, job_version, job_state, active
):
    monkeypatch.setattr(s, "ROOT", tmp_path / "orphan")
    s.init()
    with s.db() as c:
        m = {
            "id": "synthetic",
            "state": "analyzing",
            "version": 1,
            "report_version": 1,
            "report_id": "old-report",
            "active_job_id": active,
        }
        c.execute("INSERT INTO meetings VALUES(?,?,?)", ("synthetic", 1, json.dumps(m)))
        c.execute(
            "INSERT INTO transcripts VALUES(?,?,?,?,?)",
            ("synthetic", 1, json.dumps(SEGMENTS), "Synthetic", 0),
        )
        c.execute(
            "INSERT INTO reports VALUES(?,?,?,?,?)",
            ("old-report", "synthetic", 1, json.dumps(REPORT), 0),
        )
        jid = s.enqueue(c, "synthetic", "pipeline", job_version)
        c.execute("UPDATE jobs SET state=? WHERE id=?", (job_state, jid))
    monkeypatch.setattr(
        w.ai, "transcribe", lambda *a, **k: pytest.fail("No startup ASR")
    )
    monkeypatch.setattr(
        w.ai, "report", lambda *a, **k: pytest.fail("No startup generation")
    )
    s.init()
    with s.db() as c:
        result = s.meeting(c, "synthetic")
        assert result["state"] == "failed" and "Relancez" in result["error"]
        assert result["report_id"] == "old-report" and result["version"] == 1
        assert s.transcript(c, "synthetic", 1) == SEGMENTS
        assert c.execute("SELECT COUNT(*) FROM reports").fetchone()[0] == 1
        assert c.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 1


def test_failure_uses_durable_source_version_not_old_job_dictionary(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(s, "ROOT", tmp_path / "failure")
    s.init()
    with s.db() as c:
        c.execute(
            "INSERT INTO meetings VALUES(?,?,?)",
            (
                "synthetic",
                1,
                json.dumps({"id": "synthetic", "version": 1, "state": "analyzing"}),
            ),
        )
        jid = s.enqueue(c, "synthetic", "pipeline", 0)
        c.execute("UPDATE jobs SET phase='report',source_version=1 WHERE id=?", (jid,))
        m = s.meeting(c, "synthetic")
        m["active_job_id"] = jid
        s.save(c, m)
    w.fail_job(
        {
            "id": jid,
            "meeting": "synthetic",
            "kind": "pipeline",
            "version": 0,
            "source_version": None,
        },
        "Synthetic failure",
    )
    with s.db() as c:
        assert s.meeting(c, "synthetic")["state"] == "failed"
        assert (
            c.execute("SELECT state FROM jobs WHERE id=?", (jid,)).fetchone()[0]
            == "failed"
        )
