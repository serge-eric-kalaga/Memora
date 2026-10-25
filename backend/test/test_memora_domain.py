"""Isolated Memora contract/security tests. Synthetic sources; no real SMTP or AI."""

import io
import json
import os
import time
import wave
from types import SimpleNamespace

for key, value in {
    "APP_NAME": "Memora test",
    "ADMINS_EMAIL": "admin@example.test",
    "SECRET_KEY": "synthetic-test-secret",
    "JWT_SECRET": "synthetic-jwt-secret",
    "ALGORITHM": "HS256",
    "DATABASE_URL": "sqlite://",
    "INITIALISE_DATABASE": "false",
}.items():
    os.environ.setdefault(key, value)

import pytest  # noqa: E402
from fastapi import FastAPI, Request  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from api.memora import routes as r, store as s, worker as w  # noqa: E402

PREFIX = "/api/memora"
SEGMENTS = [
    {
        "id": "s0",
        "start": 0.0,
        "end": 1.0,
        "text": "Le budget est ouvert.",
        "speaker": "Intervenant non identifié",
        "language": "fr",
        "uncertain": False,
    }
]
REPORT = {
    k: [] for k in ("summary", "topics", "decisions", "actions", "open_questions")
}
REPORT["summary"] = [{"text": "Le budget reste ouvert.", "sources": ["s0"]}]


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(s, "ROOT", tmp_path / "domain")
    s.init()
    app = FastAPI()
    app.include_router(r.router)

    def identity(request: Request):
        ident = int(request.headers.get("authorization", "Bearer 1").split()[-1])
        return SimpleNamespace(
            id=ident,
            account_uid=f"synthetic-incarnation-{ident}",
            email=f"user{ident}@example.test",
            is_superuser=ident == 9,
        )

    app.dependency_overrides[r.current_user] = identity
    from api import database
    from api.services import jwt

    monkeypatch.setattr(
        jwt, "getPayload", lambda request, token, db: {"username": token}
    )
    monkeypatch.setattr(database, "get_db", lambda: iter([None]))

    # access() calls close(), so use a real generator.
    def db():
        yield None

    monkeypatch.setattr(database, "get_db", db)
    monkeypatch.setattr(
        database.User,
        "get",
        lambda **kw: SimpleNamespace(
            id=int(kw["username"]),
            account_uid=f"synthetic-incarnation-{int(kw['username'])}",
        ),
    )
    with TestClient(app, headers={"Authorization": "Bearer 1"}) as value:
        yield value


def create(client, **body):
    response = client.post(
        PREFIX + "/meetings", json={"title": "Synthetic planning", **body}
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def seed(mid):
    with s.db() as c:
        m = s.meeting(c, mid)
        m.update(
            version=1, duration=1, state="ready", report_version=1, report_id="report1"
        )
        s.save(c, m)
        c.execute(
            "INSERT INTO transcripts VALUES(?,?,?,?,?)",
            (mid, 1, json.dumps(SEGMENTS), "ASR", time.time()),
        )
        c.execute(
            "INSERT INTO reports VALUES(?,?,?,?,?)",
            ("report1", mid, 1, json.dumps(REPORT), time.time()),
        )


def wav():
    out = io.BytesIO()
    with wave.open(out, "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(16000)
        f.writeframes(b"\0\0" * 16000)
    return out.getvalue()


def test_owner_isolation_including_superuser(client):
    mid = create(client)
    with s.db() as connection:
        meeting = s.meeting(connection, mid)
        meeting["live_segments"] = SEGMENTS
        s.save(connection, meeting)
    listed = client.get(PREFIX + "/meetings").json()[0]
    assert listed["id"] == mid
    assert not {"live_segments", "owner_uid", "email", "owner"}.intersection(listed)
    assert client.get(PREFIX + "/meetings/" + mid).json()["live_segments"] == SEGMENTS
    for identity in (2, 9):
        headers = {"Authorization": f"Bearer {identity}"}
        assert client.get(PREFIX + "/meetings", headers=headers).json() == []
        for suffix in ("", "/audio"):
            assert (
                client.get(
                    PREFIX + "/meetings/" + mid + suffix, headers=headers
                ).status_code
                == 404
            )
        assert (
            client.delete(PREFIX + "/meetings/" + mid, headers=headers).status_code
            == 404
        )


def test_chunk_retry_order_integrity_and_resume(client):
    mid = create(client)
    path = PREFIX + "/meetings/" + mid + "/chunks"
    assert client.post(path + "?seq=1", content=b"later").status_code == 409
    assert (
        client.post(
            path, content=b"first", headers={"x-chunk-digest": "invalid"}
        ).status_code
        == 422
    )
    assert client.post(path, content=b"first").status_code == 200
    assert client.post(path, content=b"first").json()["duplicate"]
    assert client.post(path, content=b"changed").status_code == 409
    # A crash may append bytes before the DB commit; next successful chunk truncates them.
    with (s.ROOT / mid / "audio.bin").open("ab") as f:
        f.write(b"orphan bytes")
    assert client.post(path + "?seq=1", content=b"second").status_code == 200
    assert (s.ROOT / mid / "audio.bin").read_bytes() == b"firstsecond"
    assert (
        client.post(
            PREFIX + "/meetings/" + mid + "/finalize", json={"expected_chunks": 3}
        ).status_code
        == 409
    )
    assert (
        client.post(
            PREFIX + "/meetings/" + mid + "/finalize", json={"expected_chunks": 2}
        ).status_code
        == 422
    )


def test_valid_audio_finalize_idempotence_and_upload_closed(client):
    mid = create(client)
    base = PREFIX + "/meetings/" + mid
    assert client.post(base + "/chunks", content=wav()).status_code == 200
    first = client.post(base + "/finalize", json={"expected_chunks": 1})
    assert first.status_code == 200, first.text
    assert client.post(base + "/finalize", json={"expected_chunks": 1}).json()[
        "idempotent"
    ]
    assert client.post(base + "/chunks?seq=1", content=b"more").status_code == 409
    with s.db() as c:
        assert c.execute("SELECT count(*) FROM jobs").fetchone()[0] == 1


def test_upload_limits(client):
    mid = create(client)
    path = PREFIX + "/meetings/" + mid + "/chunks"
    assert client.post(path, content=b"x" * (5 * 1024 * 1024 + 1)).status_code == 413
    assert client.post(path, content=b"").status_code == 422
    assert client.post(path + "?seq=-1", content=b"x").status_code == 422
    with s.db() as c:
        m = s.meeting(c, mid)
        m["settings"]["max_upload_mb"] = 1
        s.save(c, m)
    assert client.post(path, content=b"x" * (1024 * 1024 + 1)).status_code == 413


def test_share_password_expiration_revocation_and_resource_permissions(
    client, monkeypatch
):
    mid = create(client)
    seed(mid)
    base = PREFIX + "/meetings/" + mid
    share = client.post(
        base + "/shares",
        json={
            "password": "test-password",
            "permissions": {"audio": False, "transcript": False},
        },
    ).json()
    guest = {"x-share-token": share["id"], "x-share-password": "incorrect"}
    assert (
        client.get(PREFIX + "/share/" + share["id"], headers=guest).status_code == 401
    )
    guest["x-share-password"] = "test-password"
    result = client.get(base, headers=guest)
    assert result.status_code == 200, result.text
    assert "segments" not in result.json()
    assert result.json()["reports"][0]["data"]["summary"][0]["sources"] == []
    assert client.get(base + "/audio", headers=guest).status_code == 403
    monkeypatch.setattr(
        r.ai,
        "answer",
        lambda segments, question, language: {
            "answer": segments[0]["text"],
            "sources": ["s0"],
        },
    )
    answer = client.post(
        base + "/chat", headers=guest, json={"question": "Quel budget ?"}
    )
    assert answer.status_code == 200, answer.text
    assert answer.json()["sources"] == []
    assert client.patch(base, headers=guest, json={"archived": True}).status_code == 403
    assert client.delete(base + "/shares/" + share["id"]).status_code == 200
    assert client.get(base, headers=guest).status_code == 404
    assert client.post(base + "/shares", json={"expires_at": 0}).status_code == 422
    expiring = client.post(
        base + "/shares", json={"expires_at": time.time() + 60}
    ).json()
    with s.db() as c:
        row = c.execute(
            "SELECT data FROM shares WHERE id=?", (expiring["id"],)
        ).fetchone()
        value = json.loads(row[0])
        value["expires_at"] = time.time() - 1
        c.execute(
            "UPDATE shares SET data=? WHERE id=?", (json.dumps(value), expiring["id"])
        )
    assert client.get(PREFIX + "/share/" + expiring["id"]).status_code == 404


def test_correction_optimistic_lock_and_history(client):
    mid = create(client)
    seed(mid)
    base = PREFIX + "/meetings/" + mid
    segments = [dict(SEGMENTS[0], text="Le budget est confirmé.", speaker="Alice")]
    assert client.put(
        base + "/transcript", json={"version": 1, "segments": segments}
    ).json() == {"version": 2, "stale": True}
    assert (
        client.put(
            base + "/transcript", json={"version": 1, "segments": segments}
        ).status_code
        == 409
    )
    assert (
        client.put(
            base + "/transcript",
            json={"version": 2, "segments": [dict(segments[0], start=3)]},
        ).status_code
        == 422
    )
    detail = client.get(base).json()
    assert len(detail["transcript_versions"]) == 2
    assert detail["report_version"] == 1 and detail["version"] == 2
    assert detail["reports"][0]["version"] == 1


def test_stale_worker_keeps_history_without_overwriting_newer_source(
    client, monkeypatch
):
    mid = create(client)
    seed(mid)

    def during_report(segments, language):
        with s.db() as c:
            m = s.meeting(c, mid)
            m["version"] = 2
            m["report_id"] = "newer"
            s.save(c, m)
            c.execute(
                "INSERT INTO transcripts VALUES(?,?,?,?,?)",
                (mid, 2, json.dumps(SEGMENTS), "editor", time.time()),
            )
        return REPORT

    monkeypatch.setattr(w.ai, "report", during_report)
    w.process({"id": "late", "meeting": mid, "kind": "pipeline", "version": 1})
    with s.db() as c:
        m = s.meeting(c, mid)
        assert m["version"] == 2 and m["report_id"] == "newer"
        assert c.execute("SELECT count(*) FROM reports").fetchone()[0] == 2
        assert c.execute("SELECT count(*) FROM notifications").fetchone()[0] == 0


def test_settings_bounds_nonretroactive_retention_archive_and_delete(client):
    mid = create(client)
    seed(mid)
    base = PREFIX + "/meetings/" + mid
    assert (
        client.put(PREFIX + "/settings", json={"audio_retention_days": 1}).status_code
        == 403
    )
    assert (
        client.put(
            PREFIX + "/settings",
            headers={"Authorization": "Bearer 9"},
            json={"audio_retention_days": 0},
        ).status_code
        == 422
    )
    assert (
        client.put(
            PREFIX + "/settings",
            headers={"Authorization": "Bearer 9"},
            json={"audio_retention_days": 1},
        ).status_code
        == 200
    )
    with s.db() as c:
        assert s.meeting(c, mid)["settings"]["audio_retention_days"] == 30
    assert client.patch(base, json={"archived": True}).status_code == 200
    assert client.get(base).json()["archived"]
    folder = s.ROOT / mid
    folder.mkdir()
    (folder / "audio.bin").write_bytes(wav())
    with s.db() as c:
        m = s.meeting(c, mid)
        m["audio_expires_at"] = time.time() - 1
        s.save(c, m)
    w.retention()
    assert not (folder / "audio.bin").exists()
    assert client.get(base).json()["audio_expired"]
    assert client.get(base).json()["segments"]
    assert client.delete(base).status_code == 200
    assert client.get(base).status_code == 404
    with s.db() as c:
        for table in ("transcripts", "reports", "jobs", "shares", "chunks", "chats"):
            assert c.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 0


def test_queue_mail_idempotent_and_smtp_failure_recoverable(client, monkeypatch):
    with s.db() as c:
        for _ in range(2):
            w.queue_mail(
                c,
                "deduplicated",
                1,
                "synthetic@example.test",
                "Synthetic",
                "<p>Test</p>",
                owner_uid="synthetic-incarnation-1",
            )
        assert c.execute("SELECT count(*) FROM mail").fetchone()[0] == 1
    monkeypatch.setenv("MEMORA_SMTP_HOST", "external.invalid")
    w.send_mail()
    assert client.get(PREFIX + "/mail").json()[0]["state"] == "failed"
    assert client.post(PREFIX + "/mail/deduplicated/retry").status_code == 200
    assert client.get(PREFIX + "/mail").json()[0]["state"] == "queued"


def test_chat_rechecks_revocation_and_source_version_after_inference(
    client, monkeypatch
):
    mid = create(client)
    seed(mid)
    base = PREFIX + "/meetings/" + mid
    token = client.post(base + "/shares", json={}).json()["id"]

    def revoke_during_answer(*args):
        with s.db() as c:
            row = c.execute("SELECT data FROM shares WHERE id=?", (token,)).fetchone()
            data = json.loads(row[0])
            data["revoked"] = True
            c.execute("UPDATE shares SET data=? WHERE id=?", (json.dumps(data), token))
        return {"answer": "Budget ouvert.", "sources": ["s0"]}

    monkeypatch.setattr(r.ai, "answer", revoke_during_answer)
    assert (
        client.post(
            base + "/chat",
            headers={"x-share-token": token},
            json={"question": "Budget ?"},
        ).status_code
        == 404
    )

    def correct_during_answer(*args):
        with s.db() as c:
            m = s.meeting(c, mid)
            m["version"] = 2
            s.save(c, m)
        return {"answer": "Budget ouvert.", "sources": ["s0"]}

    monkeypatch.setattr(r.ai, "answer", correct_during_answer)
    assert client.post(base + "/chat", json={"question": "Budget ?"}).status_code == 409
    with s.db() as c:
        assert c.execute("SELECT count(*) FROM chats").fetchone()[0] == 0


def test_guest_edit_requires_explicit_permission_and_admin_setting(client):
    mid = create(client)
    seed(mid)
    base = PREFIX + "/meetings/" + mid
    assert (
        client.post(base + "/shares", json={"permissions": {"edit": True}}).status_code
        == 422
    )
    settings = client.get(PREFIX + "/settings").json()
    settings.pop("can_administer")
    settings["allow_guest_edit"] = True
    assert (
        client.put(
            PREFIX + "/settings", headers={"Authorization": "Bearer 9"}, json=settings
        ).status_code
        == 200
    )
    token = client.post(base + "/shares", json={"permissions": {"edit": True}}).json()[
        "id"
    ]
    body = {
        "version": 1,
        "segments": [dict(SEGMENTS[0], text="Correction invitée")],
        "editor_name": "Invité synthétique",
    }
    assert (
        client.put(
            base + "/transcript", headers={"x-share-token": token}, json=body
        ).status_code
        == 200
    )
    assert client.delete(base, headers={"x-share-token": token}).status_code == 403
    # Policy can be disabled even for an existing link with edit=True.
    settings["allow_guest_edit"] = False
    client.put(
        PREFIX + "/settings", headers={"Authorization": "Bearer 9"}, json=settings
    )
    body["version"] = 2
    assert (
        client.get(base, headers={"x-share-token": token}).json()["permissions"]["edit"]
        is False
    )
    assert (
        client.put(
            base + "/transcript", headers={"x-share-token": token}, json=body
        ).status_code
        == 403
    )


def test_job_enqueue_idempotent_and_running_recovered(client):
    mid = create(client)
    with s.db() as c:
        first = s.enqueue(c, mid, "pipeline", 0)
        assert s.enqueue(c, mid, "pipeline", 0) == first
        c.execute("UPDATE jobs SET state='running' WHERE id=?", (first,))
    s.init()
    with s.db() as c:
        row = c.execute("SELECT * FROM jobs WHERE id=?", (first,)).fetchone()
        assert row["state"] == "queued"
        assert s.enqueue(c, mid, "pipeline", 0) == first


def test_failed_password_attempts_are_rate_limited(client):
    mid = create(client)
    token = client.post(
        PREFIX + "/meetings/" + mid + "/shares", json={"password": "test-password"}
    ).json()["id"]
    base = PREFIX + "/meetings/" + mid
    for _ in range(20):
        assert (
            client.get(
                base, headers={"x-share-token": token, "x-share-password": "wrong"}
            ).status_code
            == 401
        )
    assert (
        client.get(
            base, headers={"x-share-token": token, "x-share-password": "test-password"}
        ).status_code
        == 429
    )


def test_old_queued_job_cannot_reprocess_newer_revision(client, monkeypatch):
    mid = create(client)
    seed(mid)
    base = PREFIX + "/meetings/" + mid
    response = client.put(
        base + "/transcript",
        json={"version": 1, "segments": [dict(SEGMENTS[0], text="Texte nouveau")]},
    )
    assert response.status_code == 200
    before = client.get(base).json()

    def forbidden(*args):
        pytest.fail("A stale job must not invoke report generation")

    monkeypatch.setattr(w.ai, "report", forbidden)
    w.process({"id": "obsolete", "meeting": mid, "kind": "pipeline", "version": 1})
    after = client.get(base).json()
    assert after["version"] == 2 and after["state"] == before["state"]
    assert after["report_id"] == before["report_id"]
    assert after["state"] != "analyzing"
    assert client.post(base + "/analyze").status_code == 200
    assert client.get(base).json()["state"] == "queued"


def test_completed_report_notifies_once_and_analyze_retry_is_idempotent(
    client, monkeypatch
):
    mid = create(client)
    seed(mid)
    base = PREFIX + "/meetings/" + mid
    assert (
        client.put(
            base + "/transcript",
            json={
                "version": 1,
                "segments": [dict(SEGMENTS[0], text="Budget final confirmé")],
            },
        ).status_code
        == 200
    )
    response = client.post(base + "/analyze")
    assert response.status_code == 200
    monkeypatch.setattr(w.ai, "report", lambda *args: REPORT)
    w.process(
        {
            "id": response.json()["job_id"],
            "meeting": mid,
            "kind": "pipeline",
            "version": 2,
        }
    )
    detail = client.get(base).json()
    assert detail["state"] == "ready" and detail["report_version"] == 2
    assert len(detail["reports"]) == 2
    assert client.post(base + "/analyze").json()["idempotent"]
    assert len(client.get(PREFIX + "/notifications").json()) == 1
    assert len(client.get(PREFIX + "/mail").json()) == 1
    assert (
        client.get(
            PREFIX + "/notifications", headers={"Authorization": "Bearer 2"}
        ).json()
        == []
    )
    assert (
        client.get(PREFIX + "/mail", headers={"Authorization": "Bearer 2"}).json() == []
    )


def test_worker_failure_can_retry_and_stale_failure_cannot_overwrite(client):
    mid = create(client)
    seed(mid)
    base = PREFIX + "/meetings/" + mid
    client.put(
        base + "/transcript",
        json={"version": 1, "segments": [dict(SEGMENTS[0], text="Nouvelle source")]},
    )
    client.post(base + "/analyze")
    w.fail_job({"meeting": mid, "kind": "pipeline", "version": 1}, "old failure")
    assert client.get(base).json()["state"] == "queued"
    w.fail_job(
        {"meeting": mid, "kind": "pipeline", "version": 2},
        "synthetic model unavailable",
    )
    failed = client.get(base).json()
    assert (
        failed["state"] == "failed" and failed["error"] == "synthetic model unavailable"
    )
    assert client.post(base + "/analyze").status_code == 200
    assert client.get(base).json()["state"] == "queued"
    with s.db() as c:
        m = s.meeting(c, mid)
        m.update(state="ready", report_version=2, error=None)
        s.save(c, m)
    w.fail_job(
        {"meeting": mid, "kind": "pipeline", "version": 2}, "late duplicate failure"
    )
    assert client.get(base).json()["state"] == "ready"
    assert client.get(base).json()["error"] is None


def test_invitation_password_encrypted_deduplicated_and_deleted_with_meeting(client):
    mid = create(client)
    base = PREFIX + "/meetings/" + mid
    password = "Synthetic-Password-123"
    token = client.post(base + "/shares", json={"password": password}).json()["id"]
    invite = base + "/shares/" + token + "/invite"
    body = {
        "emails": ["ALICE@example.com", "alice@example.com", "bob@example.com"],
        "summary": "<synthetic>",
        "password": password,
    }
    assert client.post(invite, json=dict(body, password="incorrect")).status_code == 422
    assert client.post(invite, json=dict(body, emails=["invalid"])).status_code == 422
    for _ in range(2):
        response = client.post(invite, json=body)
        assert response.status_code == 200, response.text
        assert response.json()["recipients"] == 2
    with s.db() as c:
        rows = c.execute("SELECT * FROM mail").fetchall()
        assert len(rows) == 2
        for row in rows:
            assert row["id"].startswith("invite:" + mid + ":")
            assert row["body"].startswith("enc:") and password not in row["body"]
            decoded = w.mail_cipher().decrypt(row["body"][4:].encode()).decode()
            assert password in decoded and "&lt;synthetic&gt;" in decoded
        assert password not in c.execute("SELECT data FROM shares").fetchone()[0]
    assert client.delete(base).status_code == 200
    with s.db() as c:
        assert c.execute("SELECT count(*) FROM mail").fetchone()[0] == 0


def test_smtp_success_erases_body_and_never_resends_sent_on_retry(client, monkeypatch):
    from unittest.mock import MagicMock

    smtp = MagicMock()
    monkeypatch.setattr(w.smtplib, "SMTP", smtp)
    monkeypatch.setenv("MEMORA_SMTP_HOST", "localhost")
    with s.db() as c:
        w.queue_mail(
            c,
            "sensitive",
            1,
            "synthetic@example.com",
            "Synthetic",
            "<p>synthetic password</p>",
            owner_uid="synthetic-incarnation-1",
        )
    w.send_mail()
    connection = smtp.return_value.__enter__.return_value
    assert connection.send_message.call_count == 1
    sent = connection.send_message.call_args.args[0]
    assert "synthetic password" in sent.get_body(preferencelist=("html",)).get_content()
    with s.db() as c:
        row = c.execute("SELECT * FROM mail WHERE id=?", ("sensitive",)).fetchone()
        assert row["state"] == "sent" and row["body"] == ""
    client.post(PREFIX + "/mail/sensitive/retry")
    w.send_mail()
    assert connection.send_message.call_count == 1
    assert client.get(PREFIX + "/mail").json()[0]["state"] == "sent"


def test_invitation_requires_manage_and_matching_meeting(client):
    first = create(client)
    second = create(client)
    base = PREFIX + "/meetings/" + first
    token = client.post(base + "/shares", json={}).json()["id"]
    path = base + "/shares/" + token + "/invite"
    body = {"emails": ["synthetic@example.com"]}
    assert (
        client.post(path, headers={"x-share-token": token}, json=body).status_code
        == 403
    )
    assert (
        client.post(
            PREFIX + "/meetings/" + second + "/shares/" + token + "/invite", json=body
        ).status_code
        == 404
    )
    client.delete(base + "/shares/" + token)
    assert client.post(path, json=body).status_code == 409


def test_explicit_regeneration_same_source_and_request_replay(client, monkeypatch):
    mid = create(client)
    seed(mid)
    base = PREFIX + "/meetings/" + mid
    monkeypatch.setattr(w.ai, "report", lambda segments, language: REPORT)
    body = {"request_id": "synthetic_regeneration_01"}
    first = client.post(base + "/analyze", json=body)
    assert first.status_code == 200
    job_id = first.json()["job_id"]
    assert client.post(base + "/analyze", json=body).json()["job_id"] == job_id
    with s.db() as c:
        job = dict(c.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone())
    w.process(job)
    with s.db() as c:
        c.execute("UPDATE jobs SET state='done' WHERE id=?", (job_id,))
    assert client.post(base + "/analyze", json=body).json()["idempotent"]
    detail = client.get(base).json()
    assert len(detail["reports"]) == 2
    assert {report["version"] for report in detail["reports"]} == {1}
    assert {report["revision"] for report in detail["reports"]} == {1, 2}
    second = client.post(
        base + "/analyze", json={"request_id": "synthetic_regeneration_02"}
    )
    assert second.json()["job_id"] != job_id


def test_old_transcript_versions_obey_share_rights(client):
    mid = create(client)
    seed(mid)
    base = PREFIX + "/meetings/" + mid
    client.put(
        base + "/transcript",
        json={"version": 1, "segments": [dict(SEGMENTS[0], text="Source corrigée")]},
    )
    assert (
        client.get(base + "/transcript?version=1").json()["segments"][0]["text"]
        == SEGMENTS[0]["text"]
    )
    assert (
        client.get(base + "/transcript?version=2").json()["segments"][0]["text"]
        == "Source corrigée"
    )
    token = client.post(
        base + "/shares", json={"permissions": {"transcript": False}}
    ).json()["id"]
    assert (
        client.get(
            base + "/transcript?version=1", headers={"x-share-token": token}
        ).status_code
        == 403
    )
    assert client.get(base + "/transcript?version=3").status_code == 404


@pytest.mark.parametrize("language", ["auto", "fr", "en"])
def test_retranscribe_preserves_history_and_forwards_language(
    client, monkeypatch, language
):
    mid = create(client)
    seed(mid)
    base = PREFIX + "/meetings/" + mid
    folder = s.ROOT / mid
    folder.mkdir()
    (folder / "audio.bin").write_bytes(wav())
    request = {"request_id": "asr-request-001", "language": language}
    response = client.post(base + "/retranscribe", json=request)
    assert response.status_code == 200, response.text
    job_id = response.json()["job_id"]
    duplicate = client.post(base + "/retranscribe", json=request)
    assert duplicate.json()["idempotent"] and duplicate.json()["job_id"] == job_id
    seen = []

    def transcribe(path, **kwargs):
        seen.append(kwargs["language"])
        assert path.read_bytes() == wav()
        return [dict(SEGMENTS[0], text="New synthetic transcript")]

    monkeypatch.setattr(w.ai, "transcribe", transcribe)
    monkeypatch.setattr(w.ai, "report", lambda *args: REPORT)
    job = {"id": job_id, "meeting": mid, "kind": "retranscribe", "version": 1}
    w.process(job)
    with s.db() as c:
        c.execute("UPDATE jobs SET state='done' WHERE id=?", (job_id,))
        assert len(s.transcript(c, mid, 1)) == 1
        assert s.transcript(c, mid, 2)[0]["text"] == "New synthetic transcript"
    detail = client.get(base).json()
    assert detail["version"] == 2 and detail["report_version"] == 2
    assert len(detail["reports"]) == 2 and seen == [language]
    repeated = client.post(base + "/retranscribe", json=request)
    assert repeated.json()["idempotent"] and repeated.json()["job_id"] == job_id
    assert client.get(base).json()["version"] == 2


def test_retranscribe_validates_input_audio_and_permissions(client):
    mid = create(client)
    seed(mid)
    base = PREFIX + "/meetings/" + mid
    valid = {"request_id": "synthetic-request", "language": "auto"}
    assert (
        client.post(base + "/retranscribe", json=dict(valid, language="de")).status_code
        == 422
    )
    assert (
        client.post(
            base + "/retranscribe", json=dict(valid, request_id="../unsafe")
        ).status_code
        == 422
    )
    assert client.post(base + "/retranscribe", json=valid).status_code == 404
    folder = s.ROOT / mid
    folder.mkdir()
    (folder / "audio.bin").write_bytes(wav())
    settings = client.get(PREFIX + "/settings").json()
    settings.pop("can_administer")
    settings["allow_guest_edit"] = True
    client.put(
        PREFIX + "/settings", headers={"Authorization": "Bearer 9"}, json=settings
    )
    for permissions in ({"edit": True, "audio": False}, {"edit": False, "audio": True}):
        token = client.post(base + "/shares", json={"permissions": permissions}).json()[
            "id"
        ]
        assert (
            client.post(
                base + "/retranscribe", headers={"x-share-token": token}, json=valid
            ).status_code
            == 403
        )
    with s.db() as c:
        m = s.meeting(c, mid)
        m["audio_expired"] = True
        s.save(c, m)
    assert client.post(base + "/retranscribe", json=valid).status_code == 404


def test_retranscribe_and_analysis_cannot_be_queued_concurrently(client):
    mid = create(client)
    seed(mid)
    base = PREFIX + "/meetings/" + mid
    folder = s.ROOT / mid
    folder.mkdir()
    (folder / "audio.bin").write_bytes(wav())
    assert (
        client.post(
            base + "/retranscribe", json={"request_id": "request-alpha"}
        ).status_code
        == 200
    )
    assert (
        client.post(
            base + "/retranscribe", json={"request_id": "request-bravo"}
        ).status_code
        == 409
    )
    assert (
        client.post(
            base + "/analyze", json={"request_id": "request-analysis"}
        ).status_code
        == 409
    )
    with s.db() as c:
        assert (
            c.execute(
                "SELECT count(*) FROM jobs WHERE state IN ('queued','running')"
            ).fetchone()[0]
            == 1
        )


def test_active_job_id_prevents_same_revision_old_failure_overwrite(client):
    mid = create(client)
    seed(mid)
    with s.db() as c:
        m = s.meeting(c, mid)
        m.update(state="analyzing", active_job_id="latest-job")
        s.save(c, m)
    w.fail_job(
        {"id": "old-job", "meeting": mid, "kind": "pipeline", "version": 1},
        "old failure",
    )
    with s.db() as c:
        assert s.meeting(c, mid)["state"] == "analyzing"
    w.fail_job(
        {"id": "latest-job", "meeting": mid, "kind": "pipeline", "version": 1},
        "current failure",
    )
    with s.db() as c:
        assert s.meeting(c, mid)["state"] == "failed"
        assert s.meeting(c, mid)["error"] == "current failure"


def test_generation_schema_limits_all_citations_to_authorized_ids():
    from api.memora import ai

    allowed = ["s1", "s8"]
    report = ai.generation_schema(ai.Report, allowed)
    item = report["$defs"]["Item"]
    assert item["properties"]["sources"]["items"]["enum"] == allowed
    assert item["properties"]["sources"]["minItems"] == 1
    assert "sources" in item["required"]
    answer = ai.generation_schema(ai.Answer, allowed)
    assert answer["properties"]["sources"]["items"]["enum"] == allowed
    assert "sources" in answer["required"]
    # Pydantic's cached model schema must remain unmodified between requests.
    assert (
        "enum" not in ai.generation_schema(ai.Answer)["properties"]["sources"]["items"]
    )


def test_retranscribe_guest_edit_obeys_current_admin_policy(client):
    mid = create(client)
    seed(mid)
    base = PREFIX + "/meetings/" + mid
    folder = s.ROOT / mid
    folder.mkdir()
    (folder / "audio.bin").write_bytes(wav())
    settings = client.get(PREFIX + "/settings").json()
    settings.pop("can_administer")
    settings["allow_guest_edit"] = True
    admin = {"Authorization": "Bearer 9"}
    assert (
        client.put(PREFIX + "/settings", headers=admin, json=settings).status_code
        == 200
    )
    token = client.post(
        base + "/shares", json={"permissions": {"edit": True, "audio": True}}
    ).json()["id"]
    settings["allow_guest_edit"] = False
    assert (
        client.put(PREFIX + "/settings", headers=admin, json=settings).status_code
        == 200
    )
    response = client.post(
        base + "/retranscribe",
        headers={"x-share-token": token},
        json={"request_id": "policy-current"},
    )
    assert response.status_code == 403, response.text


def test_analyze_retry_requires_audio_only_without_transcript(client):
    mid = create(client)
    base = PREFIX + "/meetings/" + mid
    with s.db() as c:
        settings = s.config(c)
        settings["allow_guest_edit"] = True
        c.execute("UPDATE config SET data=? WHERE id=1", (json.dumps(settings),))
        m = s.meeting(c, mid)
        m.update(state="failed", duration=1, version=0)
        s.save(c, m)
    folder = s.ROOT / mid
    folder.mkdir()
    (folder / "audio.bin").write_bytes(wav())
    token = client.post(
        base + "/shares",
        json={
            "permissions": {
                "edit": True,
                "transcript": True,
                "audio": False,
            }
        },
    ).json()["id"]
    headers = {"x-share-token": token}
    assert client.post(base + "/analyze", headers=headers).status_code == 403
    with s.db() as c:
        assert (
            c.execute("SELECT COUNT(*) FROM jobs WHERE meeting=?", (mid,)).fetchone()[0]
            == 0
        )
    seed(mid)
    (folder / "audio.bin").unlink()
    with s.db() as c:
        m = s.meeting(c, mid)
        m["audio_expired"] = True
        s.save(c, m)
    result = client.post(
        base + "/analyze", headers=headers, json={"request_id": "with-transcript"}
    )
    assert result.status_code == 200
    repeated = client.post(
        base + "/analyze", headers=headers, json={"request_id": "with-transcript"}
    )
    assert repeated.json()["idempotent"]
    assert repeated.json()["job_id"] == result.json()["job_id"]


@pytest.mark.parametrize("expired", [True, False])
def test_analyze_retry_missing_audio_and_idempotence(client, expired):
    mid = create(client)
    base = PREFIX + "/meetings/" + mid
    with s.db() as c:
        m = s.meeting(c, mid)
        m.update(state="failed", duration=1, version=0, audio_expired=expired)
        s.save(c, m)
    response = client.post(base + "/analyze", json={"request_id": "retry-no-audio"})
    assert response.status_code == (410 if expired else 404)
    with s.db() as c:
        m = s.meeting(c, mid)
        job = s.enqueue(c, mid, "pipeline", 0)
        c.execute(
            "INSERT INTO analysis_requests VALUES(?,?,?)", (mid, "already-asked", job)
        )
    repeated = client.post(base + "/analyze", json={"request_id": "already-asked"})
    assert repeated.status_code == 200 and repeated.json()["idempotent"]
    assert repeated.json()["job_id"] == job
