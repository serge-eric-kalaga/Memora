"""Parcours de récupération sur base jetable ; aucun e-mail réel n’est envoyé."""

from datetime import timedelta
from hashlib import sha256
import re
import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, update
from sqlalchemy.orm import Session
from werkzeug.security import check_password_hash, generate_password_hash

from api import createApp, SETTINGS
from api.database import User, engine
from api.services import mail, password as service
from api.services.jwt import create_token

PASSWORD = "Original-password!2026"
NEW_PASSWORD = "Updated-password!2026"


@pytest.fixture
def recovery():
    """Compte isolé et capture du contenu SMTP juste avant son envoi."""
    from unittest.mock import patch

    config = SETTINGS()
    config.CACHE_ENABLED = bool(os.environ.get("TEST_REDIS_URL"))
    config.REDIS_URL = os.environ.get("TEST_REDIS_URL")
    config.REDIS_DATABASE_URL = None
    config.REDIS_PREFIX = f"password-tests:{uuid4().hex}"
    config.SECRET_KEY = uuid4().hex
    config.FRONTEND_URL = "https://template.example.com"
    config.PASSWORD_RESET_EMAIL_LIMIT = 3
    config.PASSWORD_RESET_IP_LIMIT = 30
    with patch.object(mail, "send_email", return_value=True) as outgoing:
        with TestClient(createApp(config)) as client:
            name = f"password_{uuid4().hex[:12]}"
            email = f"{name}@example.com"
            with Session(engine) as db:
                user = User(
                    username=name,
                    telephone=None,
                    password=generate_password_hash(PASSWORD),
                )
                user.email = email
                user.saveWithCommit(db)
                user_id = user.id

            def login(password=PASSWORD):
                return client.post(
                    "/api/auth/login", json={"username": name, "password": password}
                )

            token = login().json()["data"]["token"]
            headers = {"Authorization": f"Bearer {token}"}
            yield client, name, email, user_id, headers, outgoing, config, login
            if config.CACHE_ENABLED:
                from redis import Redis

                redis = Redis.from_url(config.REDIS_URL)
                keys = list(redis.scan_iter(match=f"{config.REDIS_PREFIX}:*"))
                if keys:
                    redis.delete(*keys)
                redis.close()
            with Session(engine) as db:
                db.execute(delete(User).where(User.id == user_id))
                db.commit()


def issue(client, email, outgoing, language="fr"):
    """Lire le jeton uniquement depuis le message capturé, jamais depuis l’API."""
    response = client.post(
        "/api/auth/forgot-password", json={"email": email, "language": language}
    )
    assert response.status_code == 202
    content = str(outgoing.call_args.args[1])
    token = re.search(r"#token=([A-Za-z0-9_-]+)", content).group(1)
    assert token not in response.text
    return token, content


def test_change_password_reauthenticates_revokes_sessions_and_hashes(recovery):
    c, name, _, user_id, headers, outgoing, _, login = recovery
    assert (
        c.put(
            "/api/user/me/password",
            json={"current_password": PASSWORD, "new_password": NEW_PASSWORD},
        ).status_code
        == 401
    )
    assert (
        c.put(
            "/api/user/me/password",
            headers=headers,
            json={"current_password": "wrong", "new_password": NEW_PASSWORD},
        ).status_code
        == 400
    )
    assert c.get("/api/user/me", headers=headers).status_code == 200
    assert c.get("/api/user/", headers=headers).status_code == 200
    result = c.put(
        "/api/user/me/password",
        headers=headers,
        json={"current_password": PASSWORD, "new_password": NEW_PASSWORD},
    )
    assert result.status_code == 200
    assert c.get("/api/user/me", headers=headers).status_code == 403
    assert c.get("/api/user/", headers=headers).status_code == 403
    assert (
        c.get(
            "/api/user/me",
            headers={"Authorization": f"Bearer {create_token({'username': name})}"},
        ).status_code
        == 403
    )
    assert login().status_code == 401 and login(NEW_PASSWORD).status_code == 200
    with Session(engine) as db:
        user = db.get(User, user_id)
        assert user.password != NEW_PASSWORD and check_password_hash(
            user.password, NEW_PASSWORD
        )
        assert user.auth_version == 1
    assert outgoing.call_count == 1
    assert NEW_PASSWORD not in str(outgoing.call_args)


def test_forgot_response_does_not_reveal_accounts_and_stores_only_digest(recovery):
    c, _, email, user_id, _, outgoing, _, _ = recovery
    unknown = c.post("/api/auth/forgot-password", json={"email": "unknown@example.com"})
    assert outgoing.call_count == 0
    token, content = issue(c, email.upper(), outgoing, "en")
    known = c.post("/api/auth/forgot-password", json={"email": email})
    assert (
        known.status_code == unknown.status_code == 202
        and known.json() == unknown.json()
    )
    assert "https://template.example.com/reinitialiser-mot-de-passe#token=" in content
    assert 'lang="en"' in content and "single-use" in content
    assert len(token) == 43
    # La dernière demande peut remplacer le lien ; aucun jeton en clair n’est stocké.
    with Session(engine) as db:
        user = db.get(User, user_id)
        latest_token = re.search(
            r"#token=([A-Za-z0-9_-]+)", str(outgoing.call_args.args[1])
        ).group(1)
        assert user.password_reset_digest == sha256(latest_token.encode()).hexdigest()
        assert user.password_reset_digest != token
        assert user.password_reset_expires_at > service.utc_now()


def test_reset_is_single_use_and_revokes_access_and_previous_links(recovery):
    c, _, email, user_id, headers, outgoing, _, login = recovery
    first, _ = issue(c, email, outgoing)
    second, _ = issue(c, email, outgoing)
    assert (
        c.post(
            "/api/auth/reset-password",
            json={"token": first, "new_password": NEW_PASSWORD},
        ).status_code
        == 400
    )
    result = c.post(
        "/api/auth/reset-password", json={"token": second, "new_password": NEW_PASSWORD}
    )
    assert result.status_code == 200
    assert (
        c.post(
            "/api/auth/reset-password",
            json={"token": second, "new_password": "Another-password!"},
        ).status_code
        == 400
    )
    assert c.get("/api/user/me", headers=headers).status_code == 403
    assert login().status_code == 401 and login(NEW_PASSWORD).status_code == 200
    with Session(engine) as db:
        user = db.get(User, user_id)
        assert (
            user.password_reset_digest is None
            and user.password_reset_expires_at is None
        )
    assert NEW_PASSWORD not in str(outgoing.call_args)


def test_expired_and_unknown_tokens_do_not_change_password(recovery):
    c, _, email, user_id, _, outgoing, _, login = recovery
    token, _ = issue(c, email, outgoing)
    with Session(engine) as db:
        db.execute(
            update(User)
            .where(User.id == user_id)
            .values(password_reset_expires_at=service.utc_now() - timedelta(seconds=1))
        )
        db.commit()
    invalid = c.post(
        "/api/auth/reset-password",
        json={"token": "x" * 43, "new_password": NEW_PASSWORD},
    )
    expired = c.post(
        "/api/auth/reset-password", json={"token": token, "new_password": NEW_PASSWORD}
    )
    assert (
        invalid.status_code == expired.status_code == 400
        and invalid.json() == expired.json()
    )
    assert login().status_code == 200


def test_reset_request_rate_limits_known_and_unknown_addresses(recovery):
    c, _, email, _, _, outgoing, config, _ = recovery
    config.PASSWORD_RESET_EMAIL_LIMIT = 1
    first = c.post("/api/auth/forgot-password", json={"email": email})
    second = c.post("/api/auth/forgot-password", json={"email": email})
    assert first.json() == second.json() and outgoing.call_count == 1
    config.PASSWORD_RESET_IP_LIMIT = 1
    unknown = c.post("/api/auth/forgot-password", json={"email": "nobody@example.com"})
    assert unknown.json() == first.json() and outgoing.call_count == 1


def test_smtp_failure_is_generic_and_clears_pending_token(recovery):
    c, _, email, user_id, _, outgoing, _, login = recovery
    outgoing.return_value = False
    result = c.post("/api/auth/forgot-password", json={"email": email})
    assert result.status_code == 202 and login().status_code == 200
    with Session(engine) as db:
        assert db.get(User, user_id).password_reset_digest is None


def test_email_change_requires_password_and_is_private(recovery):
    c, _, email, user_id, headers, outgoing, _, login = recovery
    same = c.patch(
        "/api/user/me/email",
        headers=headers,
        json={"email": email, "current_password": PASSWORD},
    )
    assert same.status_code == 400
    assert c.get("/api/user/me", headers=headers).status_code == 200
    token, _ = issue(c, email, outgoing)
    assert (
        c.patch(
            "/api/user/me/email",
            headers=headers,
            json={"email": "new@example.com", "current_password": "wrong"},
        ).status_code
        == 400
    )
    assert (
        c.patch(
            "/api/user/me/email",
            headers=headers,
            json={"email": "new@example.com", "current_password": PASSWORD},
        ).status_code
        == 200
    )
    assert c.get("/api/user/me", headers=headers).status_code == 403
    assert (
        c.post(
            "/api/auth/reset-password",
            json={"token": token, "new_password": NEW_PASSWORD},
        ).status_code
        == 400
    )
    new_token = login().json()["data"]["token"]
    new_headers = {"Authorization": f"Bearer {new_token}"}
    assert (
        c.get("/api/user/me", headers=new_headers).json()["data"]["email"]
        == "new@example.com"
    )
    assert all(
        "email" not in user
        for user in c.get("/api/user/", headers=new_headers).json()["data"]
    )


def test_email_uniqueness_canonicalization_and_legacy_password_route(recovery):
    c, name, email, _, headers, _, _, _ = recovery
    duplicate = c.post(
        "/api/auth/register",
        json={
            "username": f"another_{uuid4().hex[:8]}",
            "email": email.upper(),
            "password": PASSWORD,
        },
    )
    assert duplicate.status_code == 400
    assert (
        c.put(
            f"/api/user/{name}", headers=headers, json={"password": NEW_PASSWORD}
        ).status_code
        == 400
    )
    assert (
        c.put(
            "/api/user/someone_else", headers=headers, json={"telephone": "123"}
        ).status_code
        == 403
    )
    assert c.delete("/api/user/someone_else", headers=headers).status_code == 403


def test_password_change_invalidates_pending_reset_and_rejects_same_password(recovery):
    c, _, email, _, headers, outgoing, _, _ = recovery
    token, _ = issue(c, email, outgoing)
    assert (
        c.put(
            "/api/user/me/password",
            headers=headers,
            json={"current_password": PASSWORD, "new_password": PASSWORD},
        ).status_code
        == 400
    )
    assert (
        c.put(
            "/api/user/me/password",
            headers=headers,
            json={"current_password": PASSWORD, "new_password": NEW_PASSWORD},
        ).status_code
        == 200
    )
    assert (
        c.post(
            "/api/auth/reset-password",
            json={"token": token, "new_password": "Different-password!"},
        ).status_code
        == 400
    )


def test_validation_does_not_echo_secrets_or_write_them_to_logs(recovery, caplog):
    c, _, _, _, headers, _, _, _ = recovery
    secret = "never-log-this-secret" * 10
    result = c.put(
        "/api/user/me/password",
        headers=headers,
        json={"current_password": secret, "new_password": secret},
    )
    assert result.status_code == 400
    assert secret not in result.text and secret not in caplog.text


def test_email_collision_rolls_back_and_keeps_session(recovery):
    c, _, _, _, headers, _, _, _ = recovery
    name = f"collision_{uuid4().hex[:8]}"
    email = f"{name}@example.com"
    response = c.post(
        "/api/auth/register",
        json={"username": name, "email": email, "password": PASSWORD},
    )
    assert response.status_code == 200
    try:
        result = c.patch(
            "/api/user/me/email",
            headers=headers,
            json={"email": email.upper(), "current_password": PASSWORD},
        )
        assert result.status_code == 400
        assert c.get("/api/user/me", headers=headers).status_code == 200
    finally:
        with Session(engine) as db:
            db.execute(delete(User).where(User.username == name))
            db.commit()


def test_concurrent_reset_has_only_one_success(recovery, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from fastapi import HTTPException

    c, _, email, _, _, outgoing, _, _ = recovery
    token, _ = issue(c, email, outgoing)
    barrier = Barrier(2)
    original = service.generate_password_hash

    def synchronized_hash(value):
        barrier.wait(timeout=10)
        return original(value)

    monkeypatch.setattr(service, "generate_password_hash", synchronized_hash)

    def consume(number):
        with Session(engine) as db:
            try:
                service.reset_password(db, token, f"Concurrent-password-{number}!")
                return 200
            except HTTPException as exc:
                return exc.status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(consume, [1, 2]))
    assert sorted(results) == [200, 400]
