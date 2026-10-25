"""Reanalysis repairs failed current speaker labels before the report; isolated providers."""

# ruff: noqa: F401,F811
import json
from .test_memora_domain import client, create, seed, PREFIX, SEGMENTS, REPORT
from api.memora import store as s, worker as w, diarization


def prepared(client):
    mid = create(client)
    seed(mid)
    (s.ROOT / mid).mkdir(exist_ok=True)
    (s.ROOT / mid / "audio.bin").write_bytes(b"synthetic only")
    with s.db() as c:
        m = s.meeting(c, mid)
        m["automatic_diarization"] = {
            "state": "failed",
            "source_version": 1,
            "warning": "Previous failure",
        }
        s.save(c, m)
    return mid, PREFIX + "/meetings/" + mid


def providers(monkeypatch):
    calls = []
    monkeypatch.setattr(diarization, "available", lambda: True)

    def separate(path, segments, **kw):
        calls.append(kw.get("num_speakers"))
        return {
            "segments": [
                {
                    **seg,
                    "speaker": f"Intervenant {i + 1}",
                    "speaker_id": f"SPEAKER_{i:02d}",
                }
                for i, seg in enumerate(segments)
            ],
            "metadata": {"engine": "synthetic"},
            "turns": [],
        }

    monkeypatch.setattr(diarization, "diarize", separate)
    monkeypatch.setattr(
        w.ai, "report", lambda segments, lang: json.loads(json.dumps(REPORT))
    )
    monkeypatch.setattr(
        w.ai,
        "transcribe",
        lambda *a, **kw: (_ for _ in ()).throw(
            AssertionError("Must not transcribe again")
        ),
    )
    return calls


def run(mid, jid):
    with s.db() as c:
        job = dict(c.execute("SELECT * FROM jobs WHERE id=?", (jid,)).fetchone())
    w.process(job)
    with s.db() as c:
        c.execute(
            "UPDATE jobs SET state='done' WHERE id=? AND phase='complete'", (jid,)
        )


def test_reanalysis_separates_then_reports_new_version_preserving_history(
    client, monkeypatch
):
    mid, base = prepared(client)
    calls = providers(monkeypatch)
    body = {"request_id": "synthetic-repair-001", "num_speakers": 2}
    r = client.post(base + "/analyze", json=body)
    assert r.status_code == 200
    jid = r.json()["job_id"]
    assert client.post(base + "/analyze", json=body).json()["job_id"] == jid
    run(mid, jid)
    with s.db() as c:
        m = s.meeting(c, mid)
        assert m["version"] == 2 and m["report_version"] == 2 and m["state"] == "ready"
        assert s.transcript(c, mid, 1) == SEGMENTS
        assert (
            c.execute(
                "select count(*) from reports where meeting=?", (mid,)
            ).fetchone()[0]
            == 2
        )
        assert m["automatic_diarization"]["state"] == "completed"
    assert calls == [2]
    assert client.post(base + "/analyze", json=body).json()["job_id"] == jid
    assert (
        client.post(
            base + "/analyze",
            json={"request_id": "synthetic-no-overwrite", "num_speakers": 2},
        ).status_code
        == 409
    )


def test_plain_retry_also_retries_failed_labels(client, monkeypatch):
    mid, base = prepared(client)
    calls = providers(monkeypatch)
    jid = client.post(base + "/analyze").json()["job_id"]
    run(mid, jid)
    assert calls == [None]


def test_retry_after_another_failure_is_not_noop(client, monkeypatch):
    mid, base = prepared(client)
    providers(monkeypatch)
    monkeypatch.setattr(diarization, "available", lambda: False)
    jid = client.post(base + "/analyze").json()["job_id"]
    run(mid, jid)
    next_id = client.post(base + "/analyze").json()["job_id"]
    assert next_id != jid


def test_human_revision_is_not_relabelled_by_analysis(client, monkeypatch):
    mid, base = prepared(client)
    calls = providers(monkeypatch)
    with s.db() as c:
        m = s.meeting(c, mid)
        m["version"] = 2
        s.save(c, m)
        c.execute(
            "INSERT INTO transcripts SELECT meeting,2,data,'Human correction',created FROM transcripts WHERE meeting=? AND version=1",
            (mid,),
        )
    jid = client.post(
        base + "/analyze", json={"request_id": "synthetic-human-source"}
    ).json()["job_id"]
    run(mid, jid)
    assert calls == []
    assert client.get(base).json()["version"] == 2


def test_concurrent_change_of_parameters_cannot_replace_active_job(client):
    mid, base = prepared(client)
    first = client.post(
        base + "/analyze",
        json={"request_id": "synthetic-first-request", "num_speakers": 2},
    ).json()
    assert (
        client.post(
            base + "/analyze",
            json={"request_id": "synthetic-other-request", "num_speakers": 3},
        ).status_code
        == 409
    )
    assert (
        client.post(
            base + "/analyze",
            json={"request_id": "synthetic-same-request", "num_speakers": 2},
        ).json()["job_id"]
        == first["job_id"]
    )


def test_explicit_count_requires_available_audio_and_valid_bounds(client):
    mid, base = prepared(client)
    for count in (0, 9):
        assert (
            client.post(
                base + "/analyze",
                json={"request_id": "synthetic-bounds", "num_speakers": count},
            ).status_code
            == 422
        )
    (s.ROOT / mid / "audio.bin").unlink()
    assert client.post(base + "/analyze").json()["idempotent"]
    assert (
        client.post(
            base + "/analyze",
            json={"request_id": "synthetic-no-audio", "num_speakers": 2},
        ).status_code
        == 410
    )


def test_guest_without_audio_can_regenerate_report_but_not_separate(
    client, monkeypatch
):
    mid, base = prepared(client)
    calls = providers(monkeypatch)
    with s.db() as c:
        settings = s.config(c)
        settings["allow_guest_edit"] = True
        c.execute("UPDATE config SET data=? WHERE id=1", (json.dumps(settings),))
    token = client.post(
        base + "/shares",
        json={
            "permissions": {
                "edit": True,
                "transcript": True,
                "audio": False,
                "report": True,
            }
        },
    ).json()["id"]
    headers = {"x-share-token": token}
    assert (
        client.post(
            base + "/analyze",
            headers=headers,
            json={"request_id": "synthetic-denied-labels", "num_speakers": 2},
        ).status_code
        == 403
    )
    r = client.post(
        base + "/analyze",
        headers=headers,
        json={"request_id": "synthetic-allowed-report"},
    )
    assert r.status_code == 200
    run(mid, r.json()["job_id"])
    assert calls == []
    assert client.post(base + "/analyze", headers=headers).json()["idempotent"]


def test_report_crash_resumes_labelled_checkpoint_without_separating_twice(
    client, monkeypatch
):
    import pytest

    mid, base = prepared(client)
    calls = providers(monkeypatch)
    jid = client.post(
        base + "/analyze",
        json={"request_id": "synthetic-report-resume", "num_speakers": 2},
    ).json()["job_id"]
    monkeypatch.setattr(
        w.ai,
        "report",
        lambda *a: (_ for _ in ()).throw(RuntimeError("Synthetic report unavailable")),
    )
    with pytest.raises(RuntimeError):
        run(mid, jid)
    monkeypatch.setattr(w.ai, "report", lambda *a: json.loads(json.dumps(REPORT)))
    run(mid, jid)
    assert calls == [2]
    assert client.get(base).json()["report_version"] == 2
