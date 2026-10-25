"""Synthetic transport and host boundary regression tests; no model/audio use."""

import importlib.util
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.memora import ai, diarization, inference_bridge


@pytest.fixture
def bridge(monkeypatch, tmp_path):
    monkeypatch.delenv("MEMORA_INFERENCE_URL", raising=False)
    spec = importlib.util.spec_from_file_location(
        "host_bridge",
        Path(__file__).resolve().parents[2] / "scripts/memora-inference-host.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    audio = tmp_path / ("a" * 32) / "audio.bin"
    audio.parent.mkdir()
    audio.write_bytes(b"synthetic transport boundary, not audio")
    monkeypatch.setattr(ai, "transcribe", lambda *args, **kwargs: [{"text": "Bonjour"}])
    monkeypatch.setattr(
        diarization, "diarize", lambda *args, **kwargs: {"segments": args[1]}
    )
    monkeypatch.setattr(
        diarization, "availability", lambda: {"available": True, "reason": ""}
    )
    return TestClient(module.create_app(tmp_path, "x" * 40)), audio


def test_host_bridge_authorization_and_path_boundary(bridge, tmp_path):
    client, audio = bridge
    headers = {"Authorization": "Bearer " + "x" * 40}
    assert client.get("/health").json()["status"] == "ok"
    assert client.get("/diarization/availability").status_code == 401
    assert client.post("/transcribe", json={"path": str(audio)}).status_code == 401
    assert client.get("/diarization/availability", headers=headers).json()["available"]
    assert client.post(
        "/transcribe", headers=headers, json={"path": str(audio), "language": "fr"}
    ).json() == [{"text": "Bonjour"}]
    assert (
        client.post(
            "/transcribe", headers=headers, json={"path": "/etc/passwd"}
        ).status_code
        == 403
    )
    secret = audio.parent / "secrets.env"
    secret.write_text("synthetic")
    assert (
        client.post(
            "/transcribe", headers=headers, json={"path": str(secret)}
        ).status_code
        == 422
    )
    link = audio.parent / ("snapshot-" + "b" * 32 + ".bin")
    link.symlink_to(secret)
    assert (
        client.post(
            "/transcribe", headers=headers, json={"path": str(link)}
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/transcribe", headers=headers, json={"path": str(audio), "language": "xx"}
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/transcribe",
            headers=headers,
            json={"path": str(audio), "tail_seconds": -2},
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/diarize",
            headers=headers,
            json={
                "path": str(audio),
                "segments": [{"text": "Bonjour", "start": 0, "end": 1}],
            },
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/diarize",
            headers=headers,
            json={
                "path": str(audio),
                "segments": [{"text": "Bonjour", "start": 2, "end": 1}],
            },
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/transcribe", headers=headers, content=b"x" * (5 * 1024 * 1024 + 1)
        ).status_code
        == 413
    )


def test_bridge_configuration_and_native_delegation(monkeypatch, tmp_path):
    monkeypatch.setenv("MEMORA_INFERENCE_URL", "https://external.example")
    monkeypatch.setenv("MEMORA_INFERENCE_TOKEN", "x" * 40)
    with pytest.raises(inference_bridge.BridgeError):
        inference_bridge.request("/transcribe", {})
    monkeypatch.setenv("MEMORA_INFERENCE_URL", "http://host.docker.internal:8091")
    calls = []
    monkeypatch.setattr(
        inference_bridge,
        "request",
        lambda endpoint, payload=None: (
            calls.append((endpoint, payload))
            or ([] if endpoint == "/transcribe" else {"segments": []})
        ),
    )
    assert ai.transcribe(tmp_path / "audio.bin", language="fr") == []
    assert diarization.diarize(tmp_path / "audio.bin", [], num_speakers=2) == {
        "segments": []
    }
    assert calls[0][1]["language"] == "fr"
    assert calls[1][1]["num_speakers"] == 2


def test_capture_awake_bridge_bounded_and_independent(bridge, monkeypatch):
    from api.memora import capture_awake

    client, _ = bridge
    calls = []
    monkeypatch.setattr(
        capture_awake,
        "set_active",
        lambda owner, meeting, active: (
            calls.append((owner, meeting, active))
            or {"supported": True, "active": active}
        ),
    )
    headers = {"Authorization": "Bearer " + "x" * 40}
    payload = {"owner": "a" * 32, "meeting": "b" * 32, "active": True}
    assert client.post("/capture-awake", json=payload).status_code == 401
    # The ASR semaphore may be held without blocking renewal or release.
    module_lock = client.app.routes[-1].endpoint.__globals__["_LOCK"]
    with module_lock:
        assert client.post("/capture-awake", headers=headers, json=payload).json() == {
            "supported": True,
            "active": True,
        }
        payload["active"] = False
        assert not client.post("/capture-awake", headers=headers, json=payload).json()[
            "active"
        ]
    for invalid in (
        {**payload, "owner": "a" * 33},
        {**payload, "meeting": "../foo"},
        {**payload, "active": "true"},
        {**payload, "active": 1},
    ):
        assert (
            client.post("/capture-awake", headers=headers, json=invalid).status_code
            == 422
        )
    assert len(calls) == 2


def test_capture_awake_client_delegates_without_native_process(monkeypatch):
    from api.memora import capture_awake

    monkeypatch.setenv("MEMORA_INFERENCE_URL", "http://host.docker.internal:8091")
    calls = []
    monkeypatch.setattr(
        inference_bridge,
        "request",
        lambda endpoint, payload=None: (
            calls.append((endpoint, payload)) or {"supported": True, "active": True}
        ),
    )
    assert capture_awake.set_active("a" * 32, "b" * 32, True) == {
        "supported": True,
        "active": True,
    }
    assert calls == [
        ("/capture-awake", {"owner": "a" * 32, "meeting": "b" * 32, "active": True})
    ]
    monkeypatch.setattr(
        inference_bridge, "request", lambda *args: {"supported": "yes", "active": True}
    )
    assert capture_awake.set_active("a" * 32, "b" * 32, True) == {
        "supported": False,
        "active": False,
    }


def test_worker_speaker_snapshot_is_accepted_without_widening_path_access(bridge):
    client, audio = bridge
    snapshot = audio.parent / ("snapshot-" + "b" * 32 + "-speakers.bin")
    snapshot.write_bytes(b"synthetic speaker snapshot")
    headers = {"Authorization": "Bearer " + "x" * 40}
    response = client.post(
        "/diarize",
        headers=headers,
        json={
            "path": str(snapshot),
            "segments": [{"text": "Bonjour", "start": 0, "end": 1}],
        },
    )
    assert response.status_code == 200
    assert response.json()["segments"][0]["text"] == "Bonjour"


def test_bridge_accepts_administrative_four_hour_time_range(bridge):
    client, audio = bridge
    headers = {"Authorization": "Bearer " + "x" * 40}
    for end, status in ((8000, 200), (14400, 200), (14401, 422)):
        response = client.post(
            "/diarize",
            headers=headers,
            json={
                "path": str(audio),
                "segments": [
                    {"text": "Synthetic long meeting", "start": end - 1, "end": end}
                ],
            },
        )
        assert response.status_code == status
