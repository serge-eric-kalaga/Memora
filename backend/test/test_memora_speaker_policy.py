"""Speaker policy is snapshotted at creation, never retroactively enabled."""

from api.memora import store as s
from .test_memora_domain import client as client, create


def test_policy_toggle_does_not_change_existing_snapshots(client, monkeypatch):
    monkeypatch.setenv("MEMORA_AUTO_DIARIZATION", "0")
    before = create(client)
    monkeypatch.setenv("MEMORA_AUTO_DIARIZATION", "1")
    after = create(client)
    with s.db() as db:
        assert (
            s.meeting(db, before)["settings"]["auto_diarization_new_meetings"] is False
        )
        assert s.meeting(db, after)["settings"]["auto_diarization_new_meetings"] is True
