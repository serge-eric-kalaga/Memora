"""Initial-final speaker pipeline, disposable SQLite and mocked providers only."""

import json

import pytest
from api.memora import diarization, store as s, worker as w

SEGMENTS = [
    dict(
        id="s1",
        start=0,
        end=1,
        text="Premier exemple.",
        speaker="Intervenant non identifié",
    ),
    dict(
        id="s2",
        start=1,
        end=2,
        text="Deuxième exemple.",
        speaker="Intervenant non identifié",
    ),
]
REPORT = dict(
    summary=[dict(text="Exemple", sources=["s1"])],
    topics=[],
    decisions=[],
    actions=[],
    open_questions=[],
    limitations="",
)


def setup(tmp_path, monkeypatch, new=True, kind="pipeline", initial=0):
    monkeypatch.setattr(s, "ROOT", tmp_path / "auto-speakers")
    s.init()
    mid = "synthetic-auto"
    (s.ROOT / mid).mkdir()
    (s.ROOT / mid / "audio.bin").write_bytes(b"synthetic audio")
    with s.db() as c:
        settings = dict(s.DEFAULTS)
        if new:
            settings["auto_diarization_new_meetings"] = True
        meeting = dict(
            id=mid,
            owner_uid="synthetic-owner",
            title="Synthetic",
            version=initial,
            state="queued",
            settings=settings,
        )
        c.execute("INSERT INTO meetings VALUES(?,?,?)", (mid, 1, json.dumps(meeting)))
        if initial:
            c.execute(
                "INSERT INTO transcripts VALUES(?,?,?,?,?)",
                (mid, initial, json.dumps(SEGMENTS), "Earlier", 0),
            )
        jid = s.enqueue(c, mid, kind, initial)
        c.execute("UPDATE jobs SET state='running' WHERE id=?", (jid,))
        job = dict(c.execute("SELECT * FROM jobs WHERE id=?", (jid,)).fetchone())
    calls = dict(asr=0, voices=0, report=0)

    def asr(*args, **kwargs):
        calls["asr"] += 1
        return json.loads(json.dumps(SEGMENTS))

    def voices(path, segments, **kwargs):
        calls["voices"] += 1
        return dict(
            segments=[
                {
                    **segment,
                    "speaker": f"Intervenant {index + 1}",
                    "speaker_id": f"SPEAKER_{index:02d}",
                    "speaker_uncertain": False,
                }
                for index, segment in enumerate(segments)
            ],
            metadata=dict(engine="synthetic"),
            turns=[],
        )

    def report(segments, language):
        calls["report"] += 1
        return json.loads(json.dumps(REPORT))

    monkeypatch.setattr(w.ai, "transcribe", asr)
    monkeypatch.setattr(w.ai, "report", report)
    monkeypatch.setattr(diarization, "available", lambda: True)
    monkeypatch.setattr(diarization, "diarize", voices)
    return mid, job, calls


def test_new_meeting_commits_raw_asr_and_separate_labels_before_report(
    tmp_path, monkeypatch
):
    mid, job, calls = setup(tmp_path, monkeypatch)
    w.process(job)
    with s.db() as c:
        meeting = s.meeting(c, mid)
        assert meeting["version"] == 2 and meeting["state"] == "ready"
        assert s.transcript(c, mid, 1) == SEGMENTS
        labelled = s.transcript(c, mid, 2)
        assert [x["speaker"] for x in labelled] == ["Intervenant 1", "Intervenant 2"]
        assert all(
            a[k] == b[k]
            for a, b in zip(SEGMENTS, labelled, strict=True)
            for k in ("id", "start", "end", "text")
        )
        assert meeting["automatic_diarization"]["state"] == "completed"
        checkpoint = c.execute("SELECT * FROM jobs WHERE id=?", (job["id"],)).fetchone()
        assert checkpoint["source_version"] == 2 and checkpoint["phase"] == "complete"
    assert calls == dict(asr=1, voices=1, report=1)
    assert (s.ROOT / mid / "audio.bin").read_bytes() == b"synthetic audio"


@pytest.mark.parametrize(
    "kind,initial,new", [("pipeline", 0, False), ("retranscribe", 1, True)]
)
def test_existing_snapshot_or_retranscribe_never_automatically_separates(
    tmp_path, monkeypatch, kind, initial, new
):
    mid, job, calls = setup(tmp_path, monkeypatch, new, kind, initial)
    w.process(job)
    assert calls["voices"] == 0
    with s.db() as c:
        assert s.meeting(c, mid)["version"] == initial + 1


@pytest.mark.parametrize(
    "failure", ["unavailable", "provider", "mutation", "malformed", "disputed"]
)
def test_optional_speaker_failure_preserves_asr_and_warns_report(
    tmp_path, monkeypatch, failure
):
    mid, job, calls = setup(tmp_path, monkeypatch)
    if failure == "unavailable":
        monkeypatch.setattr(diarization, "available", lambda: False)
    elif failure == "disputed":
        monkeypatch.setattr(
            diarization,
            "diarize",
            lambda *a, **kw: (_ for _ in ()).throw(
                diarization.DiarizationError("Les comparaisons se contredisent")
            ),
        )
    elif failure == "provider":
        monkeypatch.setattr(
            diarization,
            "diarize",
            lambda *a, **kw: (_ for _ in ()).throw(
                RuntimeError("sensitive exception detail")
            ),
        )
    elif failure == "malformed":
        monkeypatch.setattr(
            diarization, "diarize", lambda path, segments: {"segments": segments}
        )
    else:

        def mutate(path, segments):
            segments[0]["text"] = "Changed"
            return dict(segments=segments, metadata={}, turns=[])

        monkeypatch.setattr(diarization, "diarize", mutate)
    w.process(job)
    with s.db() as c:
        meeting = s.meeting(c, mid)
        assert meeting["version"] == 1 and meeting["state"] == "ready"
        assert s.transcript(c, mid, 1) == SEGMENTS
        assert meeting["automatic_diarization"]["state"] == "failed"
        assert "sensitive" not in json.dumps(meeting)
        report = json.loads(
            c.execute(
                "SELECT data FROM reports WHERE id=?", (meeting["report_id"],)
            ).fetchone()[0]
        )
        assert "Identification automatique" in report["limitations"]
    assert calls["asr"] == 1 and calls["report"] == 1


def test_crash_during_labels_resumes_without_repeating_committed_asr(
    tmp_path, monkeypatch
):
    mid, job, calls = setup(tmp_path, monkeypatch)
    provider = diarization.diarize
    monkeypatch.setattr(
        diarization,
        "diarize",
        lambda *a, **kw: (_ for _ in ()).throw(SystemExit("synthetic death")),
    )
    with pytest.raises(SystemExit):
        w.process(job)
    with s.db() as c:
        assert s.meeting(c, mid)["version"] == 1
        assert (
            c.execute("SELECT phase FROM jobs WHERE id=?", (job["id"],)).fetchone()[0]
            == "diarize_initial"
        )
    s.init()
    monkeypatch.setattr(diarization, "diarize", provider)
    w.process(job)
    assert calls == dict(asr=1, voices=1, report=1)
    with s.db() as c:
        assert s.meeting(c, mid)["version"] == 2


def test_crash_after_label_commit_does_not_repeat_asr_or_diarization(
    tmp_path, monkeypatch
):
    mid, job, calls = setup(tmp_path, monkeypatch)
    report = w.ai.report
    monkeypatch.setattr(
        w.ai,
        "report",
        lambda *a, **kw: (_ for _ in ()).throw(SystemExit("synthetic death")),
    )
    with pytest.raises(SystemExit):
        w.process(job)
    with s.db() as c:
        assert s.meeting(c, mid)["version"] == 2
        assert (
            c.execute("SELECT phase FROM jobs WHERE id=?", (job["id"],)).fetchone()[0]
            == "report"
        )
    s.init()
    monkeypatch.setattr(w.ai, "report", report)
    w.process(job)
    assert calls == dict(asr=1, voices=1, report=1)


def test_human_correction_during_labels_wins_and_blocks_old_report(
    tmp_path, monkeypatch
):
    mid, job, calls = setup(tmp_path, monkeypatch)
    provider = diarization.diarize

    def concurrent(path, segments):
        with s.db() as c:
            meeting = s.meeting(c, mid)
            meeting.update(version=2, state="ready", active_job_id="newer-job")
            s.save(c, meeting)
            c.execute(
                "INSERT INTO transcripts VALUES(?,?,?,?,?)",
                (
                    mid,
                    2,
                    json.dumps([{**SEGMENTS[0], "text": "Human correction"}]),
                    "Human",
                    1,
                ),
            )
        return provider(path, segments)

    monkeypatch.setattr(diarization, "diarize", concurrent)
    w.process(job)
    assert calls["report"] == 0
    with s.db() as c:
        assert s.transcript(c, mid, 2)[0]["text"] == "Human correction"
        assert s.meeting(c, mid)["active_job_id"] == "newer-job"


def test_failed_labels_warning_survives_report_crash_and_retry(tmp_path, monkeypatch):
    mid, job, calls = setup(tmp_path, monkeypatch)
    monkeypatch.setattr(diarization, "available", lambda: False)
    report = w.ai.report
    monkeypatch.setattr(
        w.ai,
        "report",
        lambda *a, **kw: (_ for _ in ()).throw(SystemExit("synthetic death")),
    )
    with pytest.raises(SystemExit):
        w.process(job)
    s.init()
    monkeypatch.setattr(w.ai, "report", report)
    w.process(job)
    assert calls == dict(asr=1, voices=0, report=1)
    with s.db() as c:
        meeting = s.meeting(c, mid)
        assert meeting["version"] == 1
        result = json.loads(
            c.execute(
                "SELECT data FROM reports WHERE id=?", (meeting["report_id"],)
            ).fetchone()[0]
        )
        assert "Identification automatique" in result["limitations"]


def test_old_speaker_failure_warning_is_not_attached_to_corrected_source_report(
    tmp_path, monkeypatch
):
    mid, job, calls = setup(tmp_path, monkeypatch)
    monkeypatch.setattr(diarization, "available", lambda: False)
    w.process(job)
    with s.db() as c:
        meeting = s.meeting(c, mid)
        assert meeting["automatic_diarization"]["source_version"] == 1
        corrected = [{**s0, "speaker": "Nom corrigé"} for s0 in SEGMENTS]
        c.execute(
            "INSERT INTO transcripts VALUES(?,?,?,?,?)",
            (mid, 2, json.dumps(corrected), "Human", 1),
        )
        meeting.update(version=2, state="queued")
        s.save(c, meeting)
        jid = s.enqueue(c, mid, "pipeline", 2)
        newer = dict(c.execute("SELECT * FROM jobs WHERE id=?", (jid,)).fetchone())
    w.process(newer)
    with s.db() as c:
        meeting = s.meeting(c, mid)
        report = json.loads(
            c.execute(
                "SELECT data FROM reports WHERE id=?", (meeting["report_id"],)
            ).fetchone()[0]
        )
        assert "Identification automatique" not in report["limitations"]
        assert meeting["report_version"] == 2
    assert calls["asr"] == 1 and calls["voices"] == 0 and calls["report"] == 2
