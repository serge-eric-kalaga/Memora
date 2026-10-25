"""Real temporary auth SQL + JWT probe for account reincarnation isolation."""

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from werkzeug.exceptions import Forbidden
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from werkzeug.security import generate_password_hash

from api import database
from api.configs.config import Setting
from api.database.models import Base, User
from api.memora import store as s
from api.memora.routes import router as memora_router
from api.services.jwt import create_token
from api.views.auth.user import user_router, auth_router


@pytest.mark.parametrize("delete_method", ["http", "sql"])
@pytest.mark.parametrize(
    "replacement_username", ["synthetic_replacement", "synthetic_previous"]
)
def test_deleted_account_id_reuse_does_not_inherit_meetings(
    tmp_path, monkeypatch, replacement_username, delete_method
):
    engine = create_engine(
        "sqlite:///" + str(tmp_path / "auth.sqlite3"),
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    original_db = database.get_db

    def isolated_db():
        with Session(engine) as session:
            yield session

    monkeypatch.setattr(database, "get_db", isolated_db)
    monkeypatch.setattr(s, "ROOT", tmp_path / "domain")
    s.init()
    app = FastAPI()

    @app.exception_handler(Forbidden)
    def forbidden(request, exc):
        return JSONResponse({"detail": "Session expired"}, status_code=403)

    app.state.config = Setting.model_copy(
        update={
            "CACHE_ENABLED": False,
            "EMAIL_VERIFICATION_ENABLED": False,
            "PROFILE_PHOTO_DIR": tmp_path / "photos",
        }
    )
    app.dependency_overrides[original_db] = isolated_db
    app.include_router(memora_router)
    app.include_router(user_router, prefix="/api/user")
    app.include_router(auth_router, prefix="/api/auth")
    with Session(engine) as session:
        previous = User(
            username="synthetic_previous",
            telephone=None,
            password=generate_password_hash("SyntheticPassword!2026"),
        )
        previous.email = "previous@example.com"
        previous.saveWithCommit(session)
        previous_id = previous.id
        previous_uid = previous.account_uid
    old_headers = {
        "Authorization": "Bearer "
        + create_token(
            {
                "username": "synthetic_previous",
                "sub": str(previous_id),
                "account_uid": previous_uid,
            }
        )
    }
    with TestClient(app) as client:
        login = client.post(
            "/api/auth/login",
            json={
                "username": "synthetic_previous",
                "password": "SyntheticPassword!2026",
            },
        )
        assert login.status_code == 200
        old_headers = {"Authorization": "Bearer " + login.json()["data"]["token"]}
        response = client.post(
            "/api/memora/meetings",
            headers=old_headers,
            json={"title": "Private prior incarnation"},
        )
        assert response.status_code == 201, response.text
        mid = response.json()["id"]
        from api.memora.worker import queue_mail

        with s.db() as connection:
            connection.execute(
                "INSERT INTO notifications(id,owner,meeting,data) VALUES(?,?,?,?)",
                (
                    "previous-event",
                    previous_id,
                    mid,
                    '{"title":"Private previous notification"}',
                ),
            )
            queue_mail(
                connection,
                "previous-message",
                previous_id,
                "previous@example.test",
                "Private previous mail",
                "<p>Synthetic</p>",
                owner_uid=previous_uid,
            )
            connection.execute(
                "UPDATE mail SET state='failed' WHERE id='previous-message'"
            )
        if delete_method == "http":
            assert (
                client.delete(
                    "/api/user/synthetic_previous", headers=old_headers
                ).status_code
                == 200
            )
        else:
            # Bypass any future account-delete cleanup hook: incarnation isolation
            # must independently reject access if an auth row is removed directly.
            with Session(engine) as session:
                session.delete(User.get(db=session, username="synthetic_previous"))
                session.commit()
        response = client.post(
            "/api/auth/register",
            json={
                "username": replacement_username,
                "password": "SyntheticPassword!2026",
                "email": "replacement@example.com",
            },
        )
        assert response.status_code == 200, response.text
        with Session(engine) as session:
            replacement = User.get(db=session, username=replacement_username)
            replacement_id = replacement.id
            replacement_uid = replacement.account_uid
        new_headers = {
            "Authorization": "Bearer "
            + create_token(
                {
                    "username": replacement_username,
                    "sub": str(replacement_id),
                    "account_uid": replacement_uid,
                }
            )
        }
        login = client.post(
            "/api/auth/login",
            json={
                "username": replacement_username,
                "password": "SyntheticPassword!2026",
            },
        )
        assert login.status_code == 200
        new_headers = {"Authorization": "Bearer " + login.json()["data"]["token"]}
        if replacement_username == "synthetic_previous":
            previous_session = client.get("/api/user/me", headers=old_headers)
            assert previous_session.status_code == 403, (
                "Deleted account JWT resurrected after re-registration"
            )
        listing = client.get("/api/memora/meetings", headers=new_headers)
        assert listing.status_code == 200, listing.text
        assert mid not in [meeting["id"] for meeting in listing.json()], (
            f"Account IDs reused {previous_id}->{replacement_id}, old meeting exposed"
        )
        assert client.get("/api/memora/notifications", headers=new_headers).json() == []
        assert client.get("/api/memora/mail", headers=new_headers).json() == []
        client.patch("/api/memora/notifications/previous-event", headers=new_headers)
        client.post("/api/memora/mail/previous-message/retry", headers=new_headers)
        with s.db() as connection:
            notice = connection.execute(
                "SELECT seen FROM notifications WHERE id='previous-event'"
            ).fetchone()
            mail = connection.execute(
                "SELECT state FROM mail WHERE id='previous-message'"
            ).fetchone()
            if delete_method == "http":
                assert notice is None and mail is None
            else:
                assert notice[0] == 0 and mail[0] == "failed"
        assert (
            client.get("/api/memora/meetings/" + mid, headers=new_headers).status_code
            == 404
        )


def test_account_uid_migration_preserves_existing_rows_without_table_rebuild(tmp_path):
    from pathlib import Path
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import text

    engine = create_engine("sqlite:///" + str(tmp_path / "legacy-auth.sqlite3"))
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE user (id INTEGER PRIMARY KEY, username TEXT UNIQUE, marker TEXT)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO user VALUES (3,'legacy_one','preserved-one'),(9,'legacy_two','preserved-two')"
            )
        )
        original_root = connection.execute(
            text("SELECT rootpage FROM sqlite_master WHERE name='user'")
        ).scalar_one()
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.stamp(config, "0006_access_status")
        command.upgrade(config, "0007_account_uid")
        rows = connection.execute(
            text("SELECT id,username,marker,account_uid FROM user ORDER BY id")
        ).fetchall()
        assert [(row.id, row.username, row.marker) for row in rows] == [
            (3, "legacy_one", "preserved-one"),
            (9, "legacy_two", "preserved-two"),
        ]
        assert len({row.account_uid for row in rows}) == 2
        assert all(
            len(row.account_uid) == 32 and int(row.account_uid, 16) >= 0 for row in rows
        )
        assert (
            connection.execute(
                text("SELECT rootpage FROM sqlite_master WHERE name='user'")
            ).scalar_one()
            == original_root
        )
        # Re-running upgrade is safe and keeps incarnation identity stable.
        before = [row.account_uid for row in rows]
        command.upgrade(config, "0007_account_uid")
        assert (
            list(
                connection.execute(
                    text("SELECT account_uid FROM user ORDER BY id")
                ).scalars()
            )
            == before
        )


def test_legacy_session_without_account_uid_is_rejected(tmp_path):
    from starlette.requests import Request
    from api.services.jwt import getPayload

    engine = create_engine("sqlite:///" + str(tmp_path / "legacy-token.sqlite3"))
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        account = User(
            username="synthetic_legacy",
            telephone=None,
            password=generate_password_hash("SyntheticPassword!2026"),
        )
        account.saveWithCommit(session)
        # Explicit None prevents compatibility helper lookup: emulate legacy signed JWT.
        legacy_token = create_token(
            {"username": account.username, "sub": str(account.id), "account_uid": None}
        )
        app = FastAPI()
        app.state.config = Setting
        request = Request({"type": "http", "app": app, "headers": []})
        with pytest.raises(Forbidden):
            getPayload(request, legacy_token, session)


def test_account_uid_migration_matches_orm_for_alembic_check(tmp_path):
    from pathlib import Path
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import text

    engine = create_engine("sqlite:///" + str(tmp_path / "migration-check.sqlite3"))
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(text("DROP INDEX ix_user_account_uid"))
        connection.execute(text("ALTER TABLE user DROP COLUMN account_uid"))
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.stamp(config, "0006_access_status")
        command.upgrade(config, "0007_account_uid")
        command.check(config)


@pytest.mark.parametrize("fail_cleanup", [False, True])
def test_account_delete_removes_guest_share_and_audio_access(
    tmp_path, monkeypatch, fail_cleanup
):
    from .test_memora_domain import wav

    engine = create_engine(
        "sqlite:///" + str(tmp_path / "delete-auth.sqlite3"),
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    original_db = database.get_db

    def isolated_db():
        with Session(engine) as session:
            yield session

    monkeypatch.setattr(database, "get_db", isolated_db)
    monkeypatch.setattr(s, "ROOT", tmp_path / "delete-domain")
    s.init()
    app = FastAPI()
    app.state.config = Setting.model_copy(
        update={
            "CACHE_ENABLED": False,
            "EMAIL_VERIFICATION_ENABLED": False,
            "PROFILE_PHOTO_DIR": tmp_path / "photos",
        }
    )
    app.dependency_overrides[original_db] = isolated_db
    app.include_router(memora_router)
    app.include_router(user_router, prefix="/api/user")
    app.include_router(auth_router, prefix="/api/auth")
    with Session(engine) as session:
        account = User(
            username="synthetic_deleted_owner",
            telephone=None,
            password=generate_password_hash("SyntheticPassword!2026"),
        )
        account.saveWithCommit(session)
    with TestClient(app) as owner:
        login = owner.post(
            "/api/auth/login",
            json={
                "username": "synthetic_deleted_owner",
                "password": "SyntheticPassword!2026",
            },
        )
        assert login.status_code == 200
        headers = {"Authorization": "Bearer " + login.json()["data"]["token"]}
        response = owner.post(
            "/api/memora/meetings",
            headers=headers,
            json={"title": "Deleted owner private meeting"},
        )
        assert response.status_code == 201
        mid = response.json()["id"]
        base = "/api/memora/meetings/" + mid
        assert (
            owner.post(base + "/chunks", headers=headers, content=wav()).status_code
            == 200
        )
        share = owner.post(base + "/shares", headers=headers, json={})
        assert share.status_code == 201
        token = share.json()["id"]
        guest = {"x-share-token": token}
        assert owner.get("/api/memora/share/" + token).status_code == 200
        assert owner.get(base + "/audio", headers=guest).status_code == 200
        from api.memora import worker
        from unittest.mock import MagicMock

        with Session(engine) as session:
            account_uid = User.get(
                db=session, username="synthetic_deleted_owner"
            ).account_uid
        with s.db() as connection:
            connection.execute(
                "INSERT INTO notifications(id,owner,meeting,data) VALUES('cleanup-event',1,?,'{}')",
                (mid,),
            )
            worker.queue_mail(
                connection,
                "cleanup-message",
                1,
                "synthetic@example.com",
                "Synthetic",
                "<p>Test</p>",
                owner_uid=account_uid,
            )
        if fail_cleanup:

            def io_error(path):
                raise OSError("Synthetic file deletion failure")

            with monkeypatch.context() as patch:
                patch.setattr(s.shutil, "rmtree", io_error)
                failed = owner.delete(
                    "/api/user/synthetic_deleted_owner", headers=headers
                )
            assert failed.status_code == 503
            with Session(engine) as session:
                assert (
                    User.getOrNone(db=session, username="synthetic_deleted_owner")
                    is not None
                )
            with s.db() as connection:
                assert s.owner_deleted(connection, account_uid)
                assert s.meeting(connection, mid) is not None
            assert owner.get("/api/memora/share/" + token).status_code == 404
            assert owner.get(base + "/audio", headers=guest).status_code == 404
            stale_create = owner.post(
                "/api/memora/meetings",
                headers=headers,
                json={"title": "stale authenticated request"},
            )
            assert stale_create.status_code == 403
            smtp = MagicMock()
            with monkeypatch.context() as patch:
                patch.setattr(worker.smtplib, "SMTP", smtp)
                worker.send_mail()
            assert smtp.call_count == 0
        assert (
            owner.delete(
                "/api/user/synthetic_deleted_owner", headers=headers
            ).status_code
            == 200
        )
        assert not (s.ROOT / mid).exists()
        with s.db() as connection:
            assert s.meeting(connection, mid) is None
            assert (
                connection.execute(
                    "SELECT count(*) FROM mail WHERE owner_uid=?", (account_uid,)
                ).fetchone()[0]
                == 0
            )
            assert (
                connection.execute(
                    "SELECT count(*) FROM notifications WHERE meeting=?", (mid,)
                ).fetchone()[0]
                == 0
            )

        share_response = owner.get("/api/memora/share/" + token)
        audio_response = owner.get(base + "/audio", headers=guest)
        assert (share_response.status_code, audio_response.status_code) == (404, 404), (
            "Deleted account still exposes guest share and stored audio"
        )
