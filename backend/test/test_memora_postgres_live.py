"""Opt-in real PostgreSQL contracts, exclusively on a fresh synthetic database.

MEMORA_TEST_POSTGRES_URL must name memora_test_<16 hex digits>; the schema must
not exist. Ordinary test runs skip this module without opening a connection.
"""

import json
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

import pytest

from api.memora import store

URL = os.environ.get("MEMORA_TEST_POSTGRES_URL", "")
pytestmark = pytest.mark.skipif(
    not URL, reason="Explicit isolated PostgreSQL URL required"
)


@pytest.fixture(scope="module")
def domain(tmp_path_factory):
    import psycopg

    name = urlparse(URL).path.lstrip("/")
    if not re.fullmatch(r"memora_test_[0-9a-f]{16}", name):
        pytest.fail("Refusing PostgreSQL database without isolated random test name")
    with psycopg.connect(URL) as connection:
        exists = connection.execute(
            "SELECT 1 FROM information_schema.schemata WHERE schema_name='memora'"
        ).fetchone()
        if exists:
            pytest.fail("Refusing existing Memora schema; use a fresh test database")
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("MEMORA_DATABASE_URL", URL)
    monkeypatch.setattr(store, "ROOT", tmp_path_factory.mktemp("postgres-domain"))
    try:
        store.init()
        yield
    finally:
        monkeypatch.undo()
        with psycopg.connect(URL) as connection:
            connection.execute("DROP SCHEMA IF EXISTS memora CASCADE")


def test_schema_initialization_and_idempotence(domain):
    store.init()
    with store.db() as connection:
        assert [
            r[0]
            for r in connection.execute(
                "SELECT version FROM schema_version ORDER BY version"
            )
        ] == list(range(1, 8))
        assert store.config(connection) == store.DEFAULTS
        connection.execute(
            "INSERT INTO meetings VALUES(?,?,?)",
            ("synthetic", 1, json.dumps({"owner_uid": "test-account", "version": 1})),
        )
        connection.execute(
            "INSERT INTO transcripts VALUES(?,?,?,?,?)",
            ("synthetic", 1, "[]", "owner", 123.123456789),
        )
        connection.execute(
            "INSERT INTO reports VALUES(?,?,?,?,?)",
            ("report", "synthetic", 1, "{}", 123.123456789),
        )
        connection.execute(
            "INSERT OR IGNORE INTO notifications(id,owner,meeting,data) VALUES(?,?,?,?)",
            ("notice", 1, "synthetic", '{"created":123.123456789}'),
        )
        connection.execute(
            "INSERT OR IGNORE INTO notifications(id,owner,meeting,data) VALUES(?,?,?,?)",
            ("notice", 1, "synthetic", "{}"),
        )
    with store.db() as connection:
        row = connection.execute(
            "SELECT * FROM transcripts WHERE meeting=?", ("synthetic",)
        ).fetchone()
        assert row["created"] == 123.123456789
        assert row[0] == "synthetic"
        assert store.meeting(connection, "synthetic")["owner_uid"] == "test-account"
        assert (
            connection.execute(
                "SELECT length(CAST(data AS BLOB)) FROM reports WHERE id=?", ("report",)
            ).fetchone()[0]
            == 2
        )
        assert (
            connection.execute(
                "SELECT json_extract(data,'$.owner_uid') FROM meetings WHERE id=?",
                ("synthetic",),
            ).fetchone()[0]
            == "test-account"
        )
        assert (
            connection.execute(
                "SELECT n.* FROM notifications n ORDER BY n.rowid DESC"
            ).fetchone()["id"]
            == "notice"
        )


def test_rate_upsert_and_bound_input(domain):
    sql = "INSERT INTO limits VALUES(?,?,1) ON CONFLICT(key) DO UPDATE SET count=CASE WHEN window=? THEN count+1 ELSE 1 END,window=?"
    malicious = "'; DROP TABLE meetings; -- ? %"
    with store.db() as connection:
        for _ in range(2):
            connection.execute(sql, (malicious, 123, 123, 123))
        assert (
            connection.execute(
                "SELECT count FROM limits WHERE key=?", (malicious,)
            ).fetchone()[0]
            == 2
        )
        connection.execute(sql, (malicious, 124, 124, 124))
        assert (
            connection.execute(
                "SELECT count FROM limits WHERE key=?", (malicious,)
            ).fetchone()[0]
            == 1
        )


def test_rollback_and_cascade(domain):
    with pytest.raises(RuntimeError):
        with store.db() as connection:
            connection.execute(
                "INSERT INTO meetings VALUES(?,?,?)", ("rollback", 1, "{}")
            )
            raise RuntimeError("Synthetic cancellation")
    with store.db() as connection:
        assert store.meeting(connection, "rollback") is None
        connection.execute("INSERT INTO meetings VALUES(?,?,?)", ("cascade", 1, "{}"))
        connection.execute(
            "INSERT INTO transcripts VALUES(?,?,?,?,?)",
            ("cascade", 1, "[]", "owner", 1.0),
        )
        connection.execute(
            "INSERT INTO transcript_edits VALUES(?,?,?,?,?,?,?)",
            ("cascade", 1, "edit", "owner", None, 1.0, "{}"),
        )
        store.purge_meeting(connection, "cascade")
        assert (
            connection.execute(
                "SELECT 1 FROM transcript_edits WHERE meeting=?", ("cascade",)
            ).fetchone()
            is None
        )


def test_serialized_transactions_and_idempotent_jobs(domain):
    entered = threading.Event()
    release = threading.Event()
    contender_entered = threading.Event()

    def first():
        with store.db() as connection:
            connection.execute("BEGIN IMMEDIATE")
            store.enqueue(connection, "synthetic", "report", 1)
            entered.set()
            assert release.wait(5)

    def second():
        assert entered.wait(5)
        with store.db() as connection:
            connection.execute("BEGIN IMMEDIATE")
            contender_entered.set()
            return store.enqueue(connection, "synthetic", "report", 1)

    with ThreadPoolExecutor(max_workers=2) as pool:
        first_future = pool.submit(first)
        second_future = pool.submit(second)
        assert entered.wait(5)
        time.sleep(0.15)
        assert not contender_entered.is_set()
        release.set()
        first_future.result(timeout=5)
        job = second_future.result(timeout=5)
    with store.db() as connection:
        assert (
            connection.execute(
                "SELECT count(*) FROM jobs WHERE meeting=?", ("synthetic",)
            ).fetchone()[0]
            == 1
        )
        assert (
            connection.execute(
                "SELECT id FROM jobs WHERE meeting=?", ("synthetic",)
            ).fetchone()[0]
            == job
        )
        connection.commit()
        connection.execute("BEGIN IMMEDIATE")
        assert store.meeting(connection, "synthetic")


def test_first_upload_chunk_and_aggregate_unpacking(domain, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from api.memora import routes

    mid = "synthetic-upload"
    meeting = {
        "id": mid,
        "owner": 1,
        "owner_uid": "synthetic-owner",
        "state": "draft",
        "mode": "import",
        "version": 0,
        "settings": dict(store.DEFAULTS),
    }
    with store.db() as connection:
        connection.execute(
            "INSERT INTO meetings VALUES(?,?,?)", (mid, 1, json.dumps(meeting))
        )
        row = connection.execute(
            "SELECT count(*),coalesce(sum(bytes),0) FROM chunks WHERE meeting=?", (mid,)
        ).fetchone()
        count, total = row
        assert (count, total) == (0, 0)
        assert tuple(row) == (0, 0)
        assert dict(row) == {"count": 0, "coalesce": 0}

    async def synthetic_access(request, requested_mid, capability="view"):
        assert requested_mid == mid
        assert capability == "manage"
        with store.db() as connection:
            return store.meeting(connection, mid), {"manage": True}, "synthetic-owner"

    monkeypatch.setattr(routes, "access", synthetic_access)
    app = FastAPI()
    app.include_router(routes.router)
    with TestClient(app) as client:
        first = client.post(
            f"/api/memora/meetings/{mid}/chunks?seq=0", content=b"synthetic-first"
        )
        assert first.status_code == 200, first.text
        duplicate = client.post(
            f"/api/memora/meetings/{mid}/chunks?seq=0", content=b"synthetic-first"
        )
        assert duplicate.status_code == 200
        assert duplicate.json()["duplicate"] is True
        second = client.post(
            f"/api/memora/meetings/{mid}/chunks?seq=1", content=b"-second"
        )
        assert second.status_code == 200, second.text
        gap = client.post(
            f"/api/memora/meetings/{mid}/chunks?seq=3", content=b"missing"
        )
        assert gap.status_code == 409
    with store.db() as connection:
        count, total = connection.execute(
            "SELECT count(*),coalesce(sum(bytes),0) FROM chunks WHERE meeting=?", (mid,)
        ).fetchone()
        assert count == 2
        assert total == len(b"synthetic-first-second")
    assert (store.ROOT / mid / "audio.bin").read_bytes() == b"synthetic-first-second"
