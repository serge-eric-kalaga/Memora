"""Regression probes from independent audit; synthetic isolated store only."""
# ruff: noqa: F811 -- imported pytest fixture is intentionally injected by name

from concurrent.futures import ThreadPoolExecutor
import threading
import time

from .test_memora_domain import client, create, seed, wav, PREFIX  # noqa: F401, F811
from api.memora import store as s, worker as w
from fastapi.testclient import TestClient


def test_expired_recording_cannot_recreate_audio_outside_retention(client):
    mid = create(client, mode="recording")
    base = PREFIX + "/meetings/" + mid
    assert (
        client.post(base + "/chunks", content=b"original synthetic bytes").status_code
        == 200
    )
    with s.db() as c:
        meeting = s.meeting(c, mid)
        meeting["audio_expires_at"] = time.time() - 1
        s.save(c, meeting)
    w.retention()
    assert not (s.ROOT / mid / "audio.bin").exists()
    response = client.post(base + "/chunks?seq=1", content=b"late synthetic bytes")
    assert response.status_code in (404, 409, 410), response.text
    w.retention()
    assert not (s.ROOT / mid / "audio.bin").exists()


def test_analysis_and_retranscribe_are_mutually_exclusive_under_concurrent_requests(
    client, monkeypatch
):
    mid = create(client)
    seed(mid)
    folder = s.ROOT / mid
    folder.mkdir()
    (folder / "audio.bin").write_bytes(wav())
    base = PREFIX + "/meetings/" + mid
    enqueue = s.enqueue
    first_enqueue = threading.Event()

    def enqueue_after_both_passed_guard(*args):
        first_enqueue.set()
        time.sleep(0.1)  # Hold transaction while the second request attempts its guard.
        return enqueue(*args)

    monkeypatch.setattr(s, "enqueue", enqueue_after_both_passed_guard)

    def post_independent(suffix, request_id):
        with TestClient(
            client.app, headers={"Authorization": "Bearer 1"}
        ) as independent:
            return independent.post(base + suffix, json={"request_id": request_id})

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(post_independent, "/analyze", "concurrent-analysis")
        assert first_enqueue.wait(timeout=5)
        second = pool.submit(
            post_independent, "/retranscribe", "concurrent-retranscribe"
        )
        responses = [first.result(), second.result()]
    assert sorted(response.status_code for response in responses) == [200, 409]
    with s.db() as c:
        assert (
            c.execute(
                "SELECT count(*) FROM jobs WHERE kind!='live' AND state IN ('queued','running')"
            ).fetchone()[0]
            == 1
        )


def test_audio_deadline_enforced_before_retention_worker_runs(client):
    mid = create(client)
    base = PREFIX + "/meetings/" + mid
    assert client.post(base + "/chunks", content=wav()).status_code == 200
    with s.db() as c:
        meeting = s.meeting(c, mid)
        meeting["audio_expires_at"] = time.time() - 1
        meeting["duration"] = 1
        s.save(c, meeting)
    assert (s.ROOT / mid / "audio.bin").exists()
    assert not client.get(base).json()["audio_available"]
    assert client.get(base + "/audio").status_code in (404, 410)
    assert (
        client.post(base + "/finalize", json={"expected_chunks": 1}).status_code == 410
    )
    assert client.post(
        base + "/retranscribe", json={"request_id": "expired-before-worker"}
    ).status_code in (404, 410)
    with s.db() as c:
        assert c.execute("SELECT count(*) FROM jobs").fetchone()[0] == 0


def test_legacy_unbound_owner_never_grants_guest_or_owner_access(client):
    mid = create(client)
    base = PREFIX + "/meetings/" + mid
    token = client.post(base + "/shares", json={}).json()["id"]
    with s.db() as connection:
        meeting = s.meeting(connection, mid)
        meeting.pop("owner_uid")
        s.save(connection, meeting)
    assert client.get(PREFIX + "/share/" + token).status_code == 404
    assert client.get(base).status_code == 404
