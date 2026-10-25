"""Synthetic live preview regression; no real ASR or running worker."""

import json

import pytest
from api.memora import store as s, worker as w


@pytest.mark.parametrize(
    "prior",
    [
        [],
        [
            {
                "id": "s1",
                "start": 0,
                "end": 2,
                "text": "Parole synthétique",
                "provisional": True,
            }
        ],
    ],
)
def test_silent_live_window_preserves_previous_preview(tmp_path, monkeypatch, prior):
    monkeypatch.setattr(s, "ROOT", tmp_path / "live")
    s.init()
    mid = "synthetic-live"
    folder = s.ROOT / mid
    folder.mkdir()
    (folder / "audio.bin").write_bytes(b"synthetic-audio-placeholder")
    with s.db() as c:
        c.execute(
            "INSERT INTO meetings VALUES(?,?,?)",
            (
                mid,
                1,
                json.dumps(
                    {
                        "id": mid,
                        "owner_uid": "synthetic-owner",
                        "version": 0,
                        "state": "paused",
                        "live_segments": prior,
                    }
                ),
            ),
        )
    monkeypatch.setattr(w.ai, "transcribe", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        w.ai,
        "report",
        lambda *args, **kwargs: pytest.fail("Live must not generate a report"),
    )
    w.process({"id": "synthetic-job", "meeting": mid, "kind": "live", "version": 0})
    with s.db() as c:
        result = s.meeting(c, mid)
        assert result["live_segments"] == prior
        assert result["state"] == "paused" and result["version"] == 0
        assert c.execute("SELECT COUNT(*) FROM transcripts").fetchone()[0] == 0
    assert not (folder / "snapshot-synthetic-job.bin").exists()
