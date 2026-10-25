"""Mocked native sleep assertions and isolated API authorization; no OS settings."""

import pytest
from fastapi.testclient import TestClient
from api.memora import capture_awake as awake, store as s
from .test_memora_domain import client, create, PREFIX  # noqa: F401


class Process:
    def __init__(self):
        self.done = False

    def poll(self):
        return 0 if self.done else None

    def terminate(self):
        self.done = True

    def wait(self, timeout):
        return 0

    def kill(self):
        self.done = True


@pytest.fixture
def native(monkeypatch):
    awake.release_all()
    processes = []
    commands = []
    clock = [0.0]
    monkeypatch.setattr(awake, "supported", lambda: True)
    monkeypatch.setattr(awake.time, "monotonic", lambda: clock[0])

    def spawn(command, **kwargs):
        process = Process()
        processes.append(process)
        commands.append(command)
        assert kwargs["close_fds"] and kwargs["stdout"] == awake.subprocess.DEVNULL
        return process

    monkeypatch.setattr(awake.subprocess, "Popen", spawn)
    yield processes, commands, clock
    awake.release_all()


def test_native_command_bounded_and_renew_replaces_only_own_lease(native):
    processes, commands, _ = native
    assert awake.set_active("owner1", "meeting1", True)["active"]
    assert commands == [["/usr/bin/caffeinate", "-i", "-t", "120"]]
    assert awake.set_active("owner1", "meeting1", True)["active"]
    assert processes[0].done and not processes[1].done and len(awake._LEASES) == 1
    awake.set_active("owner2", "other", True)
    awake.set_active("owner1", "meeting1", False)
    assert processes[1].done and not processes[2].done


def test_new_meeting_replaces_owner_lease_and_old_release_cannot_cancel_it(native):
    processes, _, _ = native
    awake.set_active("owner", "first", True)
    awake.set_active("owner", "second", True)
    awake.set_active("owner", "first", False)
    assert processes[0].done and not processes[1].done and len(awake._LEASES) == 1


def test_expiration_and_shutdown_cleanup(native):
    processes, _, clock = native
    awake.set_active("owner", "first", True)
    clock[0] = 121
    awake.set_active("other", "next", True)
    assert processes[0].done and "owner" not in awake._LEASES
    awake.release_all()
    assert all(p.done for p in processes) and not awake._LEASES


def test_unsupported_platform_and_spawn_failure_are_graceful(monkeypatch, native):
    monkeypatch.setattr(awake, "supported", lambda: False)
    assert awake.set_active("owner", "id", True) == dict(supported=False, active=False)
    monkeypatch.setattr(awake, "supported", lambda: True)
    monkeypatch.setattr(
        awake.subprocess, "Popen", lambda *a, **kw: (_ for _ in ()).throw(OSError())
    )
    assert awake.set_active("owner", "id", True) == dict(supported=False, active=False)


@pytest.fixture
def local_client(client):  # noqa: F811
    with TestClient(
        client.app, headers={"Authorization": "Bearer 1"}, client=("127.0.0.1", 50000)
    ) as local:
        yield local


def recording(api_client):
    mid = create(api_client, mode="recording")
    with s.db() as connection:
        meeting = s.meeting(connection, mid)
        meeting["state"] = "recording"
        s.save(connection, meeting)
    return mid


def test_owner_only_lease_guest_and_cross_account_forbidden(local_client, native):
    mid = recording(local_client)
    url = PREFIX + f"/meetings/{mid}/capture-awake"
    assert local_client.post(url, json={"active": True}).json() == dict(
        supported=True, active=True
    )
    assert (
        local_client.post(
            url, json={"active": True}, headers={"Authorization": "Bearer 2"}
        ).status_code
        == 404
    )
    assert (
        local_client.post(
            url, json={"active": True}, headers={"x-share-token": "synthetic-guest"}
        ).status_code
        == 403
    )
    assert len(native[0]) == 1


def test_capture_state_and_release_any_state(local_client, native):
    mid = create(local_client, mode="recording")
    url = PREFIX + f"/meetings/{mid}/capture-awake"
    assert local_client.post(url, json={"active": True}).status_code == 409
    with s.db() as connection:
        meeting = s.meeting(connection, mid)
        meeting["state"] = "paused"
        s.save(connection, meeting)
    assert local_client.post(url, json={"active": True}).json()["active"]
    with s.db() as connection:
        meeting = s.meeting(connection, mid)
        meeting["state"] = "ready"
        s.save(connection, meeting)
    assert local_client.post(url, json={"active": True}).status_code == 409
    assert local_client.post(url, json={"active": False}).status_code == 200
    assert native[0][0].done


def test_nonlocal_client_does_not_protect_remote_server(client, native):  # noqa: F811
    mid = recording(client)
    result = client.post(
        PREFIX + f"/meetings/{mid}/capture-awake", json={"active": True}
    )
    assert result.json() == dict(supported=False, active=False)
    assert not native[0]


def test_native_timeout_kills_only_owned_child(native):
    processes, _, _ = native
    awake.set_active("owner", "id", True)
    process = processes[0]
    calls = []

    def wait(timeout):
        calls.append("wait")
        if len(calls) == 1:
            raise awake.subprocess.TimeoutExpired("synthetic", timeout)
        return 0

    process.wait = wait
    awake.set_active("owner", "id", False)
    assert process.done and len(calls) == 2 and not awake._LEASES
