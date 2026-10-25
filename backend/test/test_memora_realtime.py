"""SSE lifecycle with synthetic identities, no real audio or external services."""

import asyncio
from types import SimpleNamespace

from fastapi import HTTPException
import pytest

from api.memora import realtime


def run(coroutine):
    return asyncio.run(coroutine)


def test_channels_are_scoped_fixed_size_and_contain_no_identity():
    owner = realtime.channel("u", "synthetic-account")
    assert len(owner) < 63
    assert "synthetic" not in owner
    assert owner != realtime.channel("m", "synthetic-account")
    with pytest.raises(ValueError):
        realtime.channel("untrusted", "test")


def test_events_reauthorize_and_close_without_content_on_revocation():
    async def scenario():
        calls = 0

        async def authorize():
            nonlocal calls
            calls += 1
            if calls == 2:
                raise HTTPException(404, "secret reason")

        async def disconnected():
            return False

        class Connection:
            async def notifies(self, **kwargs):
                yield SimpleNamespace(payload="never exposed")

        frames = [
            frame
            async for frame in realtime.events(Connection(), authorize, disconnected)
        ]
        assert calls == 2
        assert frames == [
            "event: refresh\ndata: {}\n\n",
            "event: unavailable\ndata: {}\n\n",
        ]

    run(scenario())


def test_heartbeat_is_not_a_refresh_and_disconnect_stops():
    async def scenario():
        calls = 0

        async def authorize():
            nonlocal calls
            calls += 1

        async def disconnected():
            return calls >= 2

        class Connection:
            async def notifies(self, **kwargs):
                assert kwargs["timeout"] == 15
                return
                yield

        frames = [
            frame
            async for frame in realtime.events(Connection(), authorize, disconnected)
        ]
        assert frames == ["event: refresh\ndata: {}\n\n", ": heartbeat\n\n"]

    run(scenario())


def test_no_database_returns_explicit_fallback(monkeypatch):
    monkeypatch.delenv("MEMORA_DATABASE_URL", raising=False)

    async def scenario():
        with pytest.raises(HTTPException) as exc:
            async with realtime.subscribe("synthetic"):
                pytest.fail("No PostgreSQL configured")
        assert exc.value.status_code == 503
        assert not realtime._LIMITS

    run(scenario())


def test_listener_closes_and_releases_limit_on_disconnect(monkeypatch):
    monkeypatch.setenv("MEMORA_DATABASE_URL", "postgresql://synthetic")
    import psycopg

    class Connection:
        closed = False
        statements = []

        async def execute(self, statement):
            self.statements.append(statement)

        async def close(self):
            self.closed = True

    connection = Connection()

    async def connect(*args, **kwargs):
        assert kwargs["autocommit"]
        return connection

    monkeypatch.setattr(psycopg.AsyncConnection, "connect", connect)

    async def scenario():
        async with realtime.subscribe(realtime.channel("u", "synthetic")):
            assert sum(realtime._LIMITS.values()) == 1
            assert connection.statements
        assert connection.closed
        assert not realtime._LIMITS

    run(scenario())


def test_stream_limit_is_enforced_before_opening_database(monkeypatch):
    monkeypatch.setenv("MEMORA_DATABASE_URL", "postgresql://synthetic")
    scope = realtime.channel("m", "synthetic")

    async def scenario():
        realtime._LIMITS[scope] = 3
        try:
            with pytest.raises(HTTPException) as exc:
                async with realtime.subscribe(scope):
                    pytest.fail("Too many connections")
            assert exc.value.status_code == 429
            assert realtime._LIMITS[scope] == 3
        finally:
            realtime._LIMITS.clear()

    run(scenario())


def test_database_connect_failure_releases_slot(monkeypatch):
    import psycopg

    monkeypatch.setenv("MEMORA_DATABASE_URL", "postgresql://synthetic")

    async def connect(*args, **kwargs):
        raise psycopg.OperationalError("Synthetic unavailable database")

    monkeypatch.setattr(psycopg.AsyncConnection, "connect", connect)

    async def scenario():
        with pytest.raises(psycopg.OperationalError):
            async with realtime.subscribe(realtime.channel("u", "synthetic")):
                pytest.fail("Connection should fail")
        assert not realtime._LIMITS

    run(scenario())
