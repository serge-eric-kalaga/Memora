"""Speaker jobs publish only versioned labels on disposable synthetic stores."""

import json

import pytest
from api.memora import diarization, store as s, worker as w

SEGMENTS = [
    {"id": "s1", "start": 0, "end": 2, "text": "Synthetic example", "speaker": ""}
]


def setup_job(tmp_path, monkeypatch):
    monkeypatch.setattr(s, "ROOT", tmp_path / "data")
    s.init()
    mid = "synthetic-speakers"
    (s.ROOT / mid).mkdir()
    (s.ROOT / mid / "audio.bin").write_bytes(b"synthetic-audio")
    with s.db() as c:
        m = {
            "id": mid,
            "owner_uid": "synthetic-owner",
            "version": 1,
            "report_version": 1,
            "state": "queued",
            "settings": dict(s.DEFAULTS),
        }
        c.execute("INSERT INTO meetings VALUES(?,?,?)", (mid, 1, json.dumps(m)))
        c.execute(
            "INSERT INTO transcripts VALUES(?,?,?,?,?)",
            (mid, 1, json.dumps(SEGMENTS), "Synthetic", 0),
        )
        c.execute(
            "INSERT INTO reports VALUES(?,?,?,?,?)", ("old-report", mid, 1, "{}", 0)
        )
        jid = s.enqueue(c, mid, "diarize", 1)
        m.update(
            active_job_id=jid,
            diarization_request={"actor": "Synthetic reviewer", "num_speakers": 2},
        )
        s.save(c, m)
        job = dict(c.execute("SELECT * FROM jobs WHERE id=?", (jid,)).fetchone())
    return mid, job


def result():
    return {
        "segments": [{**SEGMENTS[0], "speaker": "Intervenant 1"}],
        "metadata": {"engine": "synthetic-test"},
        "turns": [],
    }


def test_speaker_commit_idempotent_preserves_text_and_old_report(tmp_path, monkeypatch):
    mid, job = setup_job(tmp_path, monkeypatch)
    calls = []
    monkeypatch.setattr(
        diarization, "diarize", lambda *args, **kwargs: calls.append(True) or result()
    )
    w.process(job)
    w.process(job)  # Simulate restart after commit, before worker marks done.
    with s.db() as c:
        meeting = s.meeting(c, mid)
        assert meeting["version"] == 2 and meeting["report_version"] == 1
        assert meeting["state"] == "ready"
        assert "diarization_request" not in meeting
        assert s.transcript(c, mid, 1) == SEGMENTS
        assert s.transcript(c, mid, 2)[0]["text"] == SEGMENTS[0]["text"]
        assert s.transcript(c, mid, 2)[0]["speaker"] == "Intervenant 1"
        assert c.execute("SELECT COUNT(*) FROM reports").fetchone()[0] == 1
        assert (
            c.execute("SELECT phase FROM jobs WHERE id=?", (job["id"],)).fetchone()[0]
            == "complete"
        )
    assert calls == [True]
    assert not list((s.ROOT / mid).glob("snapshot-*"))


@pytest.mark.parametrize("failure", ["text", "start", "id"])
def test_reject_provider_source_mutation(tmp_path, monkeypatch, failure):
    mid, job = setup_job(tmp_path, monkeypatch)
    altered = result()
    altered["segments"][0][failure] = "mutated" if failure != "start" else 0.5
    monkeypatch.setattr(diarization, "diarize", lambda *args, **kwargs: altered)
    with pytest.raises(w.ai.ProcessingError):
        w.process(job)
    with s.db() as c:
        assert s.meeting(c, mid)["version"] == 1
    assert not list((s.ROOT / mid).glob("snapshot-*"))


def test_late_speaker_result_does_not_replace_newer_source(tmp_path, monkeypatch):
    mid, job = setup_job(tmp_path, monkeypatch)

    def infer(*args, **kwargs):
        with s.db() as c:
            meeting = s.meeting(c, mid)
            meeting["version"] = 2
            s.save(c, meeting)
            c.execute(
                "INSERT INTO transcripts VALUES(?,?,?,?,?)",
                (mid, 2, json.dumps(SEGMENTS), "Concurrent correction", 1),
            )
        return result()

    monkeypatch.setattr(diarization, "diarize", infer)
    w.process(job)
    with s.db() as c:
        assert s.meeting(c, mid)["version"] == 2
        assert s.transcript(c, mid, 2) == SEGMENTS


def test_unavailable_engine_preserves_source_and_cleans_snapshot(tmp_path, monkeypatch):
    mid, job = setup_job(tmp_path, monkeypatch)

    def fail(*args, **kwargs):
        raise RuntimeError("Synthetic offline model failure")

    monkeypatch.setattr(diarization, "diarize", fail)
    with pytest.raises(RuntimeError):
        w.process(job)
    w.fail_job(job, "Service indisponible")
    with s.db() as c:
        assert s.meeting(c, mid)["state"] == "failed"
        assert s.transcript(c, mid, 1) == SEGMENTS
    assert not list((s.ROOT / mid).glob("snapshot-*"))
