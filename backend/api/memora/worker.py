"""Single durable worker. Jobs survive restarts, source revisions never overwritten."""

import html
import base64
import fcntl
import hashlib
import json
import logging
import os
import smtplib
import threading
import time
from email.message import EmailMessage

from . import ai, store as s

stop = threading.Event()
_lock_file = None
logger = logging.getLogger(__name__)


def mail_cipher():
    from cryptography.fernet import Fernet
    from api.configs.config import Setting

    return Fernet(
        base64.urlsafe_b64encode(hashlib.sha256(Setting.SECRET_KEY.encode()).digest())
    )


def queue_mail(c, key, owner, recipient, subject, body, owner_uid=None):
    if s.owner_deleted(c, owner_uid):
        return
    encrypted_body = "enc:" + mail_cipher().encrypt(body.encode()).decode()
    c.execute(
        "INSERT OR IGNORE INTO mail(id,owner,recipient,subject,body,state,error,owner_uid) VALUES(?,?,?,?,?,?,?,?)",
        (key, owner, recipient, subject, encrypted_body, "queued", None, owner_uid),
    )


def send_mail():
    with s.db() as c:
        rows = c.execute("SELECT * FROM mail WHERE state='queued'").fetchall()
    for row in rows:
        with s.db() as c:
            c.execute("BEGIN IMMEDIATE")
            current = c.execute(
                "SELECT state FROM mail WHERE id=?", (row["id"],)
            ).fetchone()
            if (
                not current
                or current["state"] != "queued"
                or s.owner_deleted(c, row["owner_uid"])
            ):
                continue
            try:
                msg = EmailMessage()
                msg["From"] = "Memora <memora@localhost>"
                msg["To"] = row["recipient"]
                msg["Subject"] = row["subject"]
                msg.set_content("Memora : consultez la version HTML de ce message.")
                body = row["body"]
                if body.startswith("enc:"):
                    body = mail_cipher().decrypt(body[4:].encode()).decode()
                msg.add_alternative(body, subtype="html")
                # Capture-only policy. No external SMTP destination accepted in local V1.
                host = os.environ.get("MEMORA_SMTP_HOST", "127.0.0.1")
                if host not in ("127.0.0.1", "localhost", "mailpit"):
                    raise ValueError("Serveur SMTP de capture local requis")
                with smtplib.SMTP(
                    host, int(os.environ.get("MEMORA_SMTP_PORT", "1025")), timeout=5
                ) as smtp:
                    smtp.send_message(msg)
                state, error = "sent", None
            except Exception as exc:
                state, error = "failed", type(exc).__name__
            c.execute(
                "UPDATE mail SET state=?,error=?,body=CASE WHEN ?='sent' THEN '' ELSE body END WHERE id=?",
                (state, error, state, row["id"]),
            )


def process(job):
    if job["kind"] == "diarize":
        return process_diarization(job)
    mid = job["meeting"]
    with s.db() as c:
        m = s.meeting(c, mid)
        if not m or s.owner_deleted(c, m.get("owner_uid")):
            return
        # Reload durable checkpoints; callers may hold the pre-crash job dict.
        persisted = c.execute("SELECT * FROM jobs WHERE id=?", (job["id"],)).fetchone()
        if persisted:
            job.update(dict(persisted))
        if job.get("phase") == "complete":
            return
        version = m["version"]
        expected = job.get("source_version")
        if expected is None:
            expected = job["version"]
        if job["kind"] in ("pipeline", "retranscribe") and expected != version:
            return
        resume_report = job.get("phase") == "report"
        segments = (
            []
            if job["kind"] == "retranscribe" and not resume_report
            else s.transcript(c, mid, version)
        )
        job["source_version"] = version
        if segments and job["kind"] in ("pipeline", "retranscribe"):
            c.execute(
                "UPDATE jobs SET phase='report',source_version=? WHERE id=?",
                (version, job["id"]),
            )
        if job["kind"] in ("pipeline", "retranscribe"):
            m["state"] = "transcribing" if not segments else "analyzing"
            m["active_job_id"] = job["id"]
            s.save(c, m)
    if job["kind"] in ("pipeline", "retranscribe", "live") and (
        job["kind"] == "live" or (not segments and not resume_report)
    ):
        audio = s.ROOT / mid / "audio.bin"
        # A snapshot avoids reading bytes being appended concurrently.
        snapshot = s.ROOT / mid / f"snapshot-{job['id']}.bin"
        with s.db() as c:
            source = s.meeting(c, mid)
            if not source or s.owner_deleted(c, source.get("owner_uid")):
                return
            snapshot.write_bytes(audio.read_bytes())
        try:
            segments = (
                ai.transcribe(
                    snapshot,
                    tail_seconds=120,
                    language=m.get("transcription_language", "auto"),
                )
                if job["kind"] == "live"
                else ai.transcribe(
                    snapshot, language=m.get("transcription_language", "auto")
                )
            )
        finally:
            snapshot.unlink(missing_ok=True)
        with s.db() as c:
            m = s.meeting(c, mid)
            if not m or s.owner_deleted(c, m.get("owner_uid")):
                return
            if job["kind"] == "live":
                if m["state"] in ("recording", "paused", "interrupted"):
                    # A silent tail has no replacement boundary. Keep earlier
                    # provisional speech; the final full-file pipeline is separate.
                    if not segments:
                        return
                    previous = [
                        seg
                        for seg in m.get("live_segments", [])
                        if seg["end"] < segments[0]["start"]
                    ]
                    m["live_segments"] = previous + segments
                    for index, seg in enumerate(m["live_segments"]):
                        seg["id"] = f"s{index + 1}"
                    s.save(c, m)
                return
            if m["version"] != version:
                return
            version += 1
            job["source_version"] = version
            c.execute(
                "INSERT INTO transcripts VALUES(?,?,?,?,?)",
                (mid, version, json.dumps(segments), "ASR local", time.time()),
            )
            m.update(version=version, state="analyzing")
            s.save(c, m)
            # Publish transcript and its continuation point atomically. A restart
            # must resume the report phase, including for retranscribe jobs.
            c.execute(
                "UPDATE jobs SET phase='report',source_version=? WHERE id=?",
                (version, job["id"]),
            )
    if not segments:
        raise ai.ProcessingError(
            "Aucune parole reconnue. Vérifiez le son avant de réessayer."
        )
    result = ai.report(segments, m["settings"]["report_language"])
    with s.db() as c:
        current = s.meeting(c, mid)
        if not current or s.owner_deleted(c, current.get("owner_uid")):
            return
        rid = s.uid()
        c.execute(
            "INSERT INTO reports VALUES(?,?,?,?,?)",
            (rid, mid, version, json.dumps(result), time.time()),
        )
        c.execute(
            "UPDATE jobs SET phase='complete',source_version=?,result_report_id=? WHERE id=?",
            (version, rid, job["id"]),
        )
        if current["version"] != version or current.get("active_job_id") not in (
            None,
            job["id"],
        ):
            # Keep historical output but never replace a newer source result.
            return
        current.update(state="ready", report_id=rid, report_version=version, error=None)
        s.save(c, current)
        event = f"report:{rid}"
        c.execute(
            "INSERT OR IGNORE INTO notifications(id,owner,meeting,data) VALUES(?,?,?,?)",
            (
                event,
                current["owner"],
                mid,
                json.dumps(
                    {
                        "text": f"Rapport disponible : {current['title']}",
                        "created": time.time(),
                    }
                ),
            ),
        )
        if current.get("email") and current["settings"]["email_notifications"]:
            url = (
                os.environ.get("FRONTEND_URL", "http://localhost:3000")
                + "/reunions/"
                + mid
            )
            queue_mail(
                c,
                event,
                current["owner"],
                current["email"],
                "Votre rapport Memora est disponible",
                f'<p>Votre rapport est prêt.</p><a href="{html.escape(url)}">Consulter la réunion</a>',
                owner_uid=current.get("owner_uid"),
            )


def process_diarization(job):
    """Publish speaker labels as a new source revision, never overwrite text."""
    from . import diarization

    mid = job["meeting"]
    snapshot = s.ROOT / mid / f"snapshot-{job['id']}.bin"
    with s.db() as c:
        c.execute("BEGIN IMMEDIATE")
        persisted = c.execute("SELECT * FROM jobs WHERE id=?", (job["id"],)).fetchone()
        if persisted:
            job.update(dict(persisted))
        m = s.meeting(c, mid)
        if (
            job.get("phase") == "complete"
            or not m
            or s.owner_deleted(c, m.get("owner_uid"))
        ):
            return
        expected = job.get("source_version")
        if expected is None:
            expected = job["version"]
        if m["version"] != expected or m.get("active_job_id") != job["id"]:
            return
        segments = s.transcript(c, mid, expected)
        if not segments:
            raise ai.ProcessingError(
                "Une transcription est nécessaire pour séparer les intervenants."
            )
        request = m.get("diarization_request", {})
        snapshot.write_bytes((s.ROOT / mid / "audio.bin").read_bytes())
        m.update(state="transcribing")
        s.save(c, m)
    try:
        with ai._lock:
            result = diarization.diarize(
                snapshot, segments, num_speakers=request.get("num_speakers")
            )
    finally:
        snapshot.unlink(missing_ok=True)
    updated = result["segments"]
    # Provider output cannot change source text, ordering or audio boundaries.
    if len(updated) != len(segments) or any(
        any(before.get(key) != after.get(key) for key in ("id", "start", "end", "text"))
        for before, after in zip(segments, updated, strict=True)
    ):
        raise ai.ProcessingError(
            "La séparation a modifié les repères de la source ; résultat refusé."
        )
    with s.db() as c:
        c.execute("BEGIN IMMEDIATE")
        current = s.meeting(c, mid)
        if not current or s.owner_deleted(c, current.get("owner_uid")):
            return
        if current["version"] != expected or current.get("active_job_id") != job["id"]:
            return
        version = expected + 1
        actor = request.get("actor", "Séparation locale des intervenants")
        c.execute(
            "INSERT INTO transcripts VALUES(?,?,?,?,?)",
            (mid, version, json.dumps(updated), actor, time.time()),
        )
        c.execute(
            "INSERT INTO transcript_edits VALUES(?,?,?,?,?,?,?)",
            (
                mid,
                version,
                "local_speaker_separation",
                actor,
                request.get("editor_name"),
                time.time(),
                json.dumps(
                    {
                        "previous_version": expected,
                        "num_speakers": request.get("num_speakers"),
                        "metadata": result["metadata"],
                    }
                ),
            ),
        )
        current.update(
            version=version,
            state="ready",
            error=None,
            diarization=result["metadata"],
            updated=time.time(),
        )
        current.pop("diarization_request", None)
        s.save(c, current)
        c.execute(
            "UPDATE jobs SET phase='complete',source_version=? WHERE id=?",
            (version, job["id"]),
        )
        s.audit(c, actor, mid, "speakers_separated")


def retention():
    with s.db() as c:
        rows = c.execute("SELECT id FROM meetings").fetchall()
        for row in rows:
            m = s.meeting(c, row["id"])
            if m.get("audio_expires_at", float("inf")) < time.time() and not m.get(
                "audio_expired"
            ):
                try:
                    (s.ROOT / m["id"] / "audio.bin").unlink(missing_ok=True)
                except OSError as exc:
                    maintenance_failure("retention", exc)
                    # Preserve audio_expired=False and retry this file later;
                    # other meetings must still receive their retention policy.
                    continue
                m["audio_expired"] = True
                s.save(c, m)
                s.audit(c, "retention", m["id"], "audio_purged")


def maintenance_failure(operation, error):
    # Do not log exception messages/tracebacks: they can contain paths, addresses
    # or queued message bodies. The operation and exception class are enough.
    logger.warning(
        "Memora maintenance %s failed (%s); retry on a future tick.",
        operation,
        type(error).__name__,
    )


def maintenance():
    for operation, task in (("mail", send_mail), ("retention", retention)):
        try:
            task()
        except Exception as exc:  # noqa: BLE001 - isolate maintenance, never log its contents
            maintenance_failure(operation, exc)


def fail_job(job, error):
    with s.db() as c:
        if job.get("id"):
            checkpoint = c.execute(
                "SELECT phase,source_version FROM jobs WHERE id=?", (job["id"],)
            ).fetchone()
            if checkpoint:
                if checkpoint["phase"] == "complete":
                    return
                if checkpoint["source_version"] is not None:
                    job["source_version"] = checkpoint["source_version"]
            c.execute(
                "UPDATE jobs SET state='failed',error=?,finished=? WHERE id=?",
                (error, time.time(), job["id"]),
            )
        m = s.meeting(c, job["meeting"])
        source_version = job.get("source_version")
        if source_version is None:
            source_version = job["version"]
        if m and job.get("id") and m.get("active_job_id") not in (None, job["id"]):
            return
        if (
            m
            and job["kind"] != "live"
            and m["version"] == source_version
            and m["state"] in ("queued", "transcribing", "analyzing")
        ):
            m.update(state="failed", error=error)
            s.save(c, m)


def loop():
    while not stop.wait(1):
        with s.db() as c:
            c.execute("BEGIN IMMEDIATE")
            row = c.execute(
                "SELECT * FROM jobs WHERE state='queued' ORDER BY created LIMIT 1"
            ).fetchone()
            job = dict(row) if row else None
            if job:
                c.execute("UPDATE jobs SET state='running' WHERE id=?", (job["id"],))
        if job:
            try:
                process(job)
                state, error = "done", None
            except Exception as exc:
                state = "failed"
                error = (
                    str(exc)
                    if isinstance(exc, ai.ProcessingError)
                    else f"{type(exc).__name__} : service IA indisponible. Réessayez."
                )
                fail_job(job, error)
            with s.db() as c:
                c.execute(
                    "UPDATE jobs SET state=?,error=?,finished=? WHERE id=?",
                    (state, error, time.time(), job["id"]),
                )
        maintenance()


def start():
    global _lock_file
    s.ROOT.mkdir(parents=True, exist_ok=True)
    candidate = (s.ROOT / "worker.lock").open("a")
    try:
        fcntl.flock(candidate, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        candidate.close()
        raise RuntimeError(
            "Un worker Memora utilise déjà ce stockage. Démarrez une seule instance locale."
        ) from exc
    _lock_file = candidate
    s.init()
    stop.clear()
    t = threading.Thread(target=loop, name="memora-worker", daemon=True)
    t.start()
    return t
