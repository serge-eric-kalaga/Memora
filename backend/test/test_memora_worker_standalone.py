"""Dedicated worker ownership, database recovery and process death, synthetic only."""

import json
import os
import sqlite3
import subprocess
import sys
import time
from contextlib import contextmanager

import pytest
from api.memora import store as s, worker as w


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.delenv("MEMORA_DATABASE_URL", raising=False)
    monkeypatch.setattr(s, "ROOT", tmp_path / "domain")
    s.init()
    with s.db() as c:
        c.execute(
            "INSERT INTO meetings VALUES(?,?,?)",
            ("synthetic", 1, json.dumps({"version": 0, "state": "queued"})),
        )
        jid = s.enqueue(c, "synthetic", "pipeline", 0)
    return jid


def test_api_initialization_never_recovers_external_running_job(isolated):
    with s.db() as c:
        c.execute("UPDATE jobs SET state='running' WHERE id=?", (isolated,))
    s.init(recover_jobs=False)
    with s.db() as c:
        assert c.execute("SELECT state FROM jobs").fetchone()[0] == "running"
    s.init()
    with s.db() as c:
        assert c.execute("SELECT state FROM jobs").fetchone()[0] == "queued"


def test_duplicate_worker_cannot_recover_active_job(isolated):
    code = """
from api.memora import store, worker
worker.acquire_worker_lock()
store.init()
"""
    env = dict(os.environ, MEMORA_DATA_DIR=str(s.ROOT))
    w.acquire_worker_lock()
    try:
        with s.db() as c:
            c.execute("UPDATE jobs SET state='running' WHERE id=?", (isolated,))
        result = subprocess.run(
            [sys.executable, "-c", code], env=env, capture_output=True, timeout=10
        )
        assert result.returncode != 0
        with s.db() as c:
            assert c.execute("SELECT state FROM jobs").fetchone()[0] == "running"
    finally:
        w.release_worker_lock()


@pytest.mark.parametrize(
    "failure_stage", ["claim", "inference", "final_commit", "claim_ack", "final_ack"]
)
def test_database_outage_retries_without_stranding_job(
    isolated, monkeypatch, failure_stage, caplog
):
    class Ticks:
        calls = 0

        def wait(self, _):
            self.calls += 1
            return self.calls > 4

    monkeypatch.setattr(w, "stop", Ticks())
    monkeypatch.setattr(w, "maintenance", lambda: None)
    attempts = []
    processing = []
    real_db = s.db
    ack_lost = []

    class FaultConnection:
        def __init__(self, connection):
            self.connection = connection

        def execute(self, sql, *args):
            chosen = (
                failure_stage == "claim" and sql.startswith("SELECT * FROM jobs")
            ) or (
                failure_stage == "final_commit"
                and sql.startswith("UPDATE jobs SET state=?,error=?")
            )
            ack_stage = (
                failure_stage == "claim_ack"
                and sql.startswith("UPDATE jobs SET state='running'")
            ) or (
                failure_stage == "final_ack"
                and sql.startswith("UPDATE jobs SET state=?,error=?")
            )
            if ack_stage and not attempts:
                attempts.append(True)
                ack_lost.append(True)
            if chosen and not attempts:
                attempts.append(True)
                raise sqlite3.OperationalError("PRIVATE_DETAIL_NEVER_LOG")
            return self.connection.execute(sql, *args)

        def __getattr__(self, name):
            return getattr(self.connection, name)

    @contextmanager
    def db():
        with real_db() as connection:
            yield FaultConnection(connection)
        if ack_lost:
            ack_lost.pop()
            raise sqlite3.OperationalError("PRIVATE_DETAIL_NEVER_LOG")

    monkeypatch.setattr(s, "db", db)

    def process(job):
        processing.append(job["id"])
        if failure_stage == "inference" and not attempts:
            attempts.append(True)
            raise sqlite3.OperationalError("PRIVATE_DETAIL_NEVER_LOG")

    monkeypatch.setattr(w, "process", process)
    w.loop()
    with real_db() as c:
        assert c.execute("SELECT state FROM jobs").fetchone()[0] == "done"
    assert attempts and processing
    if failure_stage in ("final_commit", "claim_ack", "final_ack"):
        assert processing == [isolated]
    assert "PRIVATE_DETAIL_NEVER_LOG" not in caplog.text


def test_sigkill_worker_resumes_report_checkpoint_without_repeating_asr(
    isolated, tmp_path
):
    mid = s.ROOT / "synthetic"
    mid.mkdir()
    (mid / "audio.bin").write_bytes(b"synthetic")
    marker = tmp_path / "checkpoint"
    code = """
import json, os, time
from pathlib import Path
from api.memora import store as s, worker as w
w.acquire_worker_lock()
s.init()
w.ai.transcribe=lambda *a, **k: [dict(id='s1',start=0,end=1,text='Synthetic')]
def report(*a, **k):
    Path(os.environ['MARKER']).touch()
    time.sleep(60)
w.ai.report=report
with s.db() as c:
    m=s.meeting(c,'synthetic')
    m.update(settings=dict(s.DEFAULTS),title='Synthetic')
    s.save(c,m)
w.loop()
"""
    env = dict(os.environ, MEMORA_DATA_DIR=str(s.ROOT), MARKER=str(marker))
    child = subprocess.Popen([sys.executable, "-c", code], env=env)
    try:
        deadline = time.monotonic() + 15
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        assert marker.exists(), "worker did not commit ASR checkpoint"
        child.kill()
        child.wait(timeout=5)
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=5)
    resume = """
from api.memora import store as s, worker as w
w.acquire_worker_lock()
s.init()
def no_asr(*a, **k):
    raise AssertionError('ASR checkpoint must survive SIGKILL')
w.ai.transcribe=no_asr
w.ai.report=lambda *a, **k: dict(summary=[],topics=[],actions=[],decisions=[],open_questions=[])
original=w.process
def process(job):
    original(job)
    w.stop.set()
w.process=process
w.loop()
"""
    completed = subprocess.run(
        [sys.executable, "-c", resume], env=env, capture_output=True, timeout=15
    )
    assert completed.returncode == 0, completed.stderr.decode()
    with s.db() as c:
        assert c.execute("SELECT state FROM jobs").fetchone()[0] == "done"
        assert c.execute("SELECT COUNT(*) FROM transcripts").fetchone()[0] == 1
        assert c.execute("SELECT COUNT(*) FROM reports").fetchone()[0] == 1
        assert s.meeting(c, "synthetic")["state"] == "ready"


def test_standalone_entrypoint_health_and_graceful_stop(tmp_path, monkeypatch):
    from api.memora import worker_main

    root = tmp_path / "entrypoint"
    monkeypatch.setattr(s, "ROOT", root)
    env = dict(os.environ, MEMORA_DATA_DIR=str(root))
    env.pop("MEMORA_DATABASE_URL", None)
    child = subprocess.Popen([sys.executable, "-m", "api.memora.worker_main"], env=env)
    try:
        deadline = time.monotonic() + 10
        while not worker_main.healthy() and time.monotonic() < deadline:
            time.sleep(0.05)
        assert worker_main.healthy()
        check = subprocess.run(
            [sys.executable, "-m", "api.memora.worker_main", "--healthcheck"],
            env=env,
            timeout=10,
        )
        assert check.returncode == 0
        child.terminate()
        assert child.wait(timeout=10) == 0
        assert not worker_main.healthy()
        w.acquire_worker_lock()
        w.release_worker_lock()
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=5)
