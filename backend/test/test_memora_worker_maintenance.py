"""Worker liveness regression: isolated SQLite and synthetic failures, no SMTP/AI."""

import json
import os
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

for key, value in {
    "APP_NAME": "Memora maintenance test",
    "ADMINS_EMAIL": "admin@example.test",
    "SECRET_KEY": "synthetic-test-secret",
    "JWT_SECRET": "synthetic-jwt-secret",
    "ALGORITHM": "HS256",
    "DATABASE_URL": "sqlite://",
    "INITIALISE_DATABASE": "false",
}.items():
    os.environ.setdefault(key, value)

import pytest  # noqa: E402
from api.memora import store as s, worker as w  # noqa: E402

MARKER = "SYNTHETIC_PRIVATE_FAILURE_DETAIL"


class TwoTicks:
    def __init__(self):
        self.calls = 0

    def wait(self, _seconds):
        self.calls += 1
        return self.calls > 2


@pytest.fixture
def worker_store(tmp_path, monkeypatch):
    monkeypatch.setattr(s, "ROOT", tmp_path / "maintenance-domain")
    s.init()
    monkeypatch.setattr(w, "stop", TwoTicks())
    jobs = []
    with s.db() as c:
        for index in range(2):
            mid = f"synthetic-maintenance-{index}"
            meeting = {
                "id": mid,
                "version": 1,
                "state": "queued",
                "audio_expired": False,
                "audio_expires_at": time.time() - 10
                if index == 0
                else time.time() + 3600,
            }
            c.execute(
                "INSERT INTO meetings VALUES(?,?,?)", (mid, 1, json.dumps(meeting))
            )
            jobs.append(s.enqueue(c, mid, "pipeline", 1))

    def process(job):
        with s.db() as c:
            meeting = s.meeting(c, job["meeting"])
            meeting["state"] = "ready"
            s.save(c, meeting)

    monkeypatch.setattr(w, "process", process)
    return jobs


def assert_jobs_finished(jobs):
    with s.db() as c:
        rows = c.execute(
            "SELECT id,state,error,finished FROM jobs ORDER BY created"
        ).fetchall()
        assert {row["id"] for row in rows} == set(jobs)
        assert all(
            row["state"] == "done"
            and row["error"] is None
            and row["finished"] is not None
            for row in rows
        )
        assert all(
            s.meeting(c, f"synthetic-maintenance-{i}")["state"] == "ready"
            for i in range(2)
        )


def test_retention_permission_error_does_not_stop_jobs_and_retries(
    worker_store, monkeypatch, caplog
):
    jobs = worker_store
    audio = s.ROOT / "synthetic-maintenance-0" / "audio.bin"
    audio.parent.mkdir()
    audio.write_bytes(b"synthetic audio")
    original_unlink = Path.unlink
    attempts = []

    def unlink(path, *args, **kwargs):
        if path == audio:
            attempts.append(True)
            if len(attempts) == 1:
                raise PermissionError(MARKER)
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", unlink)
    monkeypatch.setattr(w, "send_mail", lambda: None)
    w.loop()
    assert_jobs_finished(jobs)
    assert len(attempts) == 2 and not audio.exists()
    with s.db() as c:
        assert s.meeting(c, "synthetic-maintenance-0")["audio_expired"] is True
    assert MARKER not in caplog.text
    assert all(record.exc_info is None for record in caplog.records)


def test_mail_database_error_does_not_stop_jobs_or_other_maintenance(
    worker_store, monkeypatch, caplog
):
    jobs = worker_store
    with s.db() as c:
        w.queue_mail(
            c,
            "synthetic-retry-mail",
            1,
            "capture@example.test",
            "Synthetic",
            "<p>Synthetic capture only</p>",
        )
    sent = []

    class CaptureSMTP:
        def __init__(self, *_args, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def send_message(self, _message):
            sent.append(True)

    monkeypatch.setattr(w.smtplib, "SMTP", CaptureSMTP)
    original_db = s.db
    mail_attempts = []

    class Connection:
        def __init__(self, connection):
            self.connection = connection

        def execute(self, sql, *args):
            if sql == "SELECT * FROM mail WHERE state='queued'":
                mail_attempts.append(True)
                if len(mail_attempts) == 1:
                    raise sqlite3.OperationalError(MARKER)
            return self.connection.execute(sql, *args)

        def __getattr__(self, key):
            return getattr(self.connection, key)

    @contextmanager
    def db():
        with original_db() as connection:
            yield Connection(connection)

    monkeypatch.setattr(s, "db", db)
    retained = []

    def retention():
        with s.db() as c:
            retained.append(
                c.execute(
                    "SELECT state FROM mail WHERE id='synthetic-retry-mail'"
                ).fetchone()[0]
            )

    monkeypatch.setattr(w, "retention", retention)
    w.loop()
    assert_jobs_finished(jobs)
    assert len(mail_attempts) == 2 and retained == ["queued", "sent"] and len(sent) == 1
    with s.db() as c:
        mail = c.execute(
            "SELECT state,error,body FROM mail WHERE id='synthetic-retry-mail'"
        ).fetchone()
        assert mail["state"] == "sent" and mail["error"] is None and mail["body"] == ""
    assert MARKER not in caplog.text
    assert all(record.exc_info is None for record in caplog.records)


def test_one_unpurgeable_audio_does_not_block_other_retention(
    worker_store, monkeypatch, caplog
):
    jobs = worker_store
    bad = s.ROOT / "synthetic-maintenance-0" / "audio.bin"
    good = s.ROOT / "synthetic-maintenance-1" / "audio.bin"
    for path in (bad, good):
        path.parent.mkdir()
        path.write_bytes(b"synthetic audio")
    with s.db() as c:
        meeting = s.meeting(c, "synthetic-maintenance-1")
        meeting["audio_expires_at"] = time.time() - 10
        s.save(c, meeting)
    unlink = Path.unlink

    def blocked(path, *args, **kwargs):
        if path == bad:
            raise PermissionError(MARKER)
        return unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", blocked)
    monkeypatch.setattr(w, "send_mail", lambda: None)
    w.loop()
    assert_jobs_finished(jobs)
    assert bad.exists() and not good.exists()
    with s.db() as c:
        assert s.meeting(c, "synthetic-maintenance-0")["audio_expired"] is False
        assert s.meeting(c, "synthetic-maintenance-1")["audio_expired"] is True
    assert MARKER not in caplog.text
    assert all(record.exc_info is None for record in caplog.records)
