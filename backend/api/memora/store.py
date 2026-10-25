"""Memora durable local domain store. All mutations use SQLite transactions."""

import json
import os
import sqlite3
import shutil
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(os.environ.get("MEMORA_DATA_DIR", "../.memora/data")).resolve()
DEFAULTS = {
    "max_duration_minutes": 120,
    "max_upload_mb": 250,
    "audio_retention_days": 30,
    "allow_guest_edit": False,
    "report_language": "fr",
    "email_notifications": True,
}


def uid():
    return uuid.uuid4().hex


@contextmanager
def db():
    ROOT.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(ROOT / "memora.sqlite3", timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    try:
        yield con
        con.commit()
    except BaseException:
        con.rollback()
        raise
    finally:
        con.close()


def init():
    with db() as c:
        c.executescript(
            (Path(__file__).parent / "migrations/001_initial.sql").read_text()
        )
        c.executescript(
            (Path(__file__).parent / "migrations/002_config_history.sql").read_text()
        )
        c.executescript(
            (Path(__file__).parent / "migrations/003_analysis_requests.sql").read_text()
        )
        # SQLite ADD COLUMN is additive; legacy mail remains inaccessible until
        # an explicit reviewed owner binding associates it with a meeting UID.
        if "owner_uid" not in {row[1] for row in c.execute("PRAGMA table_info(mail)")}:
            c.execute("ALTER TABLE mail ADD COLUMN owner_uid TEXT")
        c.executescript(
            (Path(__file__).parent / "migrations/004_owner_incarnation.sql").read_text()
        )
        c.executescript(
            (
                Path(__file__).parent / "migrations/005_account_tombstones.sql"
            ).read_text()
        )
        columns = {row[1] for row in c.execute("PRAGMA table_info(jobs)")}
        for name, declaration in (
            ("phase", "TEXT NOT NULL DEFAULT 'source'"),
            ("source_version", "INTEGER"),
            ("result_report_id", "TEXT"),
        ):
            if name not in columns:
                c.execute(f"ALTER TABLE jobs ADD COLUMN {name} {declaration}")
        c.executescript(
            (Path(__file__).parent / "migrations/006_job_checkpoints.sql").read_text()
        )
        c.execute("INSERT OR IGNORE INTO config VALUES(1,?)", (json.dumps(DEFAULTS),))
        c.commit()
        # Startup runs before the worker; take the writer lock for recovery and
        # reconcile only metadata with no active job, never launch inference.
        c.execute("BEGIN IMMEDIATE")
        c.execute(
            "UPDATE jobs SET state='queued',error='Reprise après interruption' WHERE state='running'"
        )
        for row in c.execute("SELECT id FROM meetings").fetchall():
            m = meeting(c, row["id"])
            if m.get("state") not in ("queued", "transcribing", "analyzing"):
                continue
            if c.execute(
                "SELECT 1 FROM jobs WHERE meeting=? AND state IN ('queued','running')",
                (m["id"],),
            ).fetchone():
                continue
            m.update(
                state="failed",
                error="Traitement interrompu sans tâche active. Relancez l’analyse ou la transcription si nécessaire.",
            )
            save(c, m)


def config(c):
    return json.loads(c.execute("SELECT data FROM config WHERE id=1").fetchone()[0])


def meeting(c, mid):
    row = c.execute("SELECT owner,data FROM meetings WHERE id=?", (mid,)).fetchone()
    if not row:
        return None
    return {**json.loads(row["data"]), "id": mid, "owner": row["owner"]}


def save(c, m):
    c.execute("UPDATE meetings SET data=? WHERE id=?", (json.dumps(m), m["id"]))


def audit(c, actor, mid, action):
    c.execute(
        "INSERT INTO audit VALUES(?,?,?,?,?)",
        (uid(), str(actor), mid, action, time.time()),
    )


def transcript(c, mid, version=None):
    if version is None:
        row = c.execute(
            "SELECT data FROM transcripts WHERE meeting=? ORDER BY version DESC LIMIT 1",
            (mid,),
        ).fetchone()
    else:
        row = c.execute(
            "SELECT data FROM transcripts WHERE meeting=? AND version=?", (mid, version)
        ).fetchone()
    return json.loads(row[0]) if row else []


def enqueue(c, mid, kind, version):
    row = c.execute(
        "SELECT id FROM jobs WHERE meeting=? AND kind=? AND (version=? OR source_version=?) AND state IN ('queued','running')",
        (mid, kind, version, version),
    ).fetchone()
    if row:
        return row[0]
    job = uid()
    c.execute(
        "INSERT INTO jobs(id,meeting,kind,version,state,error,created,finished) VALUES(?,?,?,?,?,?,?,?)",
        (job, mid, kind, version, "queued", None, time.time(), None),
    )
    return job


def owner_deleted(c, owner_uid):
    return bool(
        owner_uid
        and c.execute(
            "SELECT 1 FROM account_tombstones WHERE owner_uid=?", (owner_uid,)
        ).fetchone()
    )


def purge_meeting(c, mid):
    """Delete files first; keep DB references if an I/O failure requires retry."""
    folder = ROOT / mid
    if folder.exists():
        shutil.rmtree(folder)
    c.execute(
        "DELETE FROM mail WHERE id LIKE ? OR id IN (SELECT 'report:' || id FROM reports WHERE meeting=?)",
        ("invite:" + mid + ":%", mid),
    )
    c.execute("DELETE FROM notifications WHERE meeting=?", (mid,))
    c.execute("DELETE FROM meetings WHERE id=?", (mid,))


def delete_owner(owner_uid):
    """Commit security barrier before fallible file cleanup; retry by stable UID only."""
    if not owner_uid:
        raise ValueError("Missing account incarnation")
    with db() as c:
        c.execute("BEGIN IMMEDIATE")
        c.execute(
            "INSERT OR IGNORE INTO account_tombstones VALUES(?,?)",
            (owner_uid, time.time()),
        )
    with db() as c:
        c.execute("BEGIN IMMEDIATE")
        mids = [
            row["id"]
            for row in c.execute("SELECT id,data FROM meetings").fetchall()
            if json.loads(row["data"]).get("owner_uid") == owner_uid
        ]
        for mid in mids:
            purge_meeting(c, mid)
        c.execute("DELETE FROM mail WHERE owner_uid=?", (owner_uid,))
        audit(c, "account:" + owner_uid, None, "account_deleted")
