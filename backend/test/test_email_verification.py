"""Recette du drapeau, des liens et de leur renvoi, sans SMTP réel."""

from datetime import timedelta
from hashlib import sha256
from unittest.mock import patch
from uuid import uuid4
import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, update
from sqlalchemy.orm import Session

from api import SETTINGS, createApp
from api.database import User, engine
from api.database.models import RecoveryRateLimit
from api.services import mail, email_verification as service
from api.services.jwt import create_token
from api.services.password import utc_now

PASSWORD = "Verification-password!2026"


@pytest.fixture
def verification():
    """Chaque recette possède sa configuration et ses comptes, tous supprimés à la fin."""
    config = SETTINGS()
    config.EMAIL_VERIFICATION_ENABLED = True
    config.CACHE_ENABLED = False
    config.SECRET_KEY = uuid4().hex
    config.FRONTEND_URL = "https://template.example.com"
    config.EMAIL_VERIFICATION_EMAIL_LIMIT = 5
    names = []
    with patch.object(mail, "send_email", return_value=True) as outgoing:
        with TestClient(createApp(config)) as client:

            def register(email=True, language="fr"):
                name = f"verify_{uuid4().hex[:12]}"
                names.append(name)
                address = f"{name}@example.com"
                response = client.post(
                    "/api/auth/register",
                    json={
                        "username": name,
                        "password": PASSWORD,
                        "email": address if email else None,
                        "language": language,
                    },
                )
                return response, name, address

            yield client, config, outgoing, register
    with Session(engine) as db:
        db.execute(delete(User).where(User.username.in_(names)))
        db.execute(delete(RecoveryRateLimit))
        db.commit()


def token_from(outgoing):
    """Extraire le secret de la boîte de réception simulée uniquement."""
    return re.search(r"#token=([A-Za-z0-9_-]{43})", outgoing.call_args.args[1]).group(1)


def login(client, name):
    return client.post("/api/auth/login", json={"username": name, "password": PASSWORD})


def test_enabled_requires_email_and_blocks_access_until_confirmation(verification):
    c, _, outgoing, register = verification
    assert c.get("/api/auth/config").json()["data"] == {
        "email_verification_enabled": True
    }
    assert register(email=False)[0].status_code == 400
    assert not outgoing.called
    response, name, email = register(language="en")
    assert response.status_code == 200
    assert response.json()["data"]["verification_required"] is True
    assert "token" not in response.json()["data"]
    assert "Confirm your email" in outgoing.call_args.args[2]
    token = token_from(outgoing)
    with Session(engine) as db:
        user = User.get(db=db, username=name)
        assert user.email_verification_digest == sha256(token.encode()).hexdigest()
        assert user.email_verified_at is None
        fake_token = create_token(
            {"username": name, "sub": str(user.id), "auth_version": 0}
        )
    assert login(c, name).status_code == 409
    assert (
        c.post(
            "/api/auth/doc-login", data={"username": name, "password": PASSWORD}
        ).status_code
        == 409
    )
    assert (
        c.get(
            "/api/user/me", headers={"Authorization": f"Bearer {fake_token}"}
        ).status_code
        == 409
    )
    result = c.post("/api/auth/verify-email", json={"token": token})
    assert result.status_code == 200 and token not in result.text
    logged = login(c, name)
    assert logged.status_code == 200
    headers = {"Authorization": f"Bearer {logged.json()['data']['token']}"}
    current = c.get("/api/user/me", headers=headers).json()["data"]
    assert current["email"] == email and current["email_verified_at"].endswith("Z")
    assert c.post("/api/auth/verify-email", json={"token": token}).status_code == 400
    assert (
        c.get(
            "/api/user/me", headers={"Authorization": f"Bearer {fake_token}"}
        ).status_code
        == 403
    )


def test_disabled_mode_and_existing_accounts_are_preserved(verification):
    c, config, outgoing, register = verification
    config.EMAIL_VERIFICATION_ENABLED = False
    response, name, _ = register(email=False)
    assert response.json()["data"]["verification_required"] is False
    assert not outgoing.called
    assert login(c, name).status_code == 200
    config.EMAIL_VERIFICATION_ENABLED = True
    assert login(c, name).status_code == 200
    response, pending, email = register()
    config.EMAIL_VERIFICATION_ENABLED = False
    assert login(c, pending).status_code == 200
    outgoing.reset_mock()
    assert (
        c.post("/api/auth/resend-verification", json={"email": email}).status_code
        == 202
    )
    assert not outgoing.called
    config.EMAIL_VERIFICATION_ENABLED = True
    assert login(c, pending).status_code == 409


def test_resend_invalidates_old_link_and_hides_existence(verification):
    c, _, outgoing, register = verification
    _, name, email = register()
    old = token_from(outgoing)
    known = c.post(
        "/api/auth/resend-verification", json={"email": email.upper(), "language": "en"}
    )
    new = token_from(outgoing)
    assert new != old and "Confirm your email" in outgoing.call_args.args[2]
    assert c.post("/api/auth/verify-email", json={"token": old}).status_code == 400
    outgoing.reset_mock()
    unknown = c.post(
        "/api/auth/resend-verification", json={"email": "unknown@example.com"}
    )
    assert unknown.json() == known.json() and unknown.status_code == 202
    assert not outgoing.called
    assert c.post("/api/auth/verify-email", json={"token": new}).status_code == 200
    confirmed = c.post("/api/auth/resend-verification", json={"email": email})
    assert confirmed.json() == known.json() and not outgoing.called
    assert login(c, name).status_code == 200


def test_expiry_tampering_smtp_failure_and_untrusted_frontend_url(verification):
    c, config, outgoing, register = verification
    _, name, email = register()
    token = token_from(outgoing)
    with Session(engine) as db:
        db.execute(
            update(User)
            .where(User.username == name)
            .values(email_verification_expires_at=utc_now() - timedelta(seconds=1))
        )
        db.commit()
    assert c.post("/api/auth/verify-email", json={"token": token}).status_code == 400
    assert c.post("/api/auth/verify-email", json={"token": "x" * 43}).status_code == 400
    outgoing.return_value = False
    assert (
        c.post("/api/auth/resend-verification", json={"email": email}).status_code
        == 202
    )
    with Session(engine) as db:
        assert User.get(db=db, username=name).email_verification_digest is None
    outgoing.reset_mock()
    config.FRONTEND_URL = "https://evil.example/?redirect=secret"
    c.post("/api/auth/resend-verification", json={"email": email})
    assert not outgoing.called


def test_limits_include_initial_send_and_are_generic(verification):
    c, config, outgoing, register = verification
    config.EMAIL_VERIFICATION_EMAIL_LIMIT = 1
    _, _, email = register()
    outgoing.reset_mock()
    limited = c.post("/api/auth/resend-verification", json={"email": email})
    assert limited.status_code == 202 and not outgoing.called
    config.EMAIL_VERIFICATION_IP_LIMIT = 1
    result, _, _ = register()
    assert result.status_code == 429
    assert not outgoing.called


def test_address_change_requires_new_confirmation_and_revokes_old_links(verification):
    c, _, outgoing, register = verification
    _, name, email = register()
    c.post("/api/auth/verify-email", json={"token": token_from(outgoing)})
    headers = {"Authorization": f"Bearer {login(c, name).json()['data']['token']}"}
    new_email = f"changed-{email}"
    assert (
        c.patch(
            "/api/user/me/email",
            headers=headers,
            json={"email": new_email, "current_password": PASSWORD},
        ).status_code
        == 200
    )
    # Le premier e-mail de la modification confirme la nouvelle adresse ; le second prévient l’ancienne.
    content = next(
        call.args[1]
        for call in reversed(outgoing.call_args_list)
        if call.args[0] == new_email
    )
    token = re.search(r"#token=([A-Za-z0-9_-]{43})", content).group(1)
    assert login(c, name).status_code == 409
    assert c.get("/api/user/me", headers=headers).status_code == 403
    assert c.post("/api/auth/verify-email", json={"token": token}).status_code == 200
    assert login(c, name).status_code == 200


def test_confirmation_does_not_activate_other_users_or_leak_secrets(
    verification, caplog
):
    c, _, outgoing, register = verification
    _, first, _ = register()
    token = token_from(outgoing)
    _, second, _ = register()
    assert c.post("/api/auth/verify-email", json={"token": token}).status_code == 200
    assert login(c, first).status_code == 200 and login(c, second).status_code == 409
    secret = "do-not-log-confirmation" * 10
    response = c.post("/api/auth/verify-email", json={"token": secret})
    assert (
        response.status_code == 400
        and secret not in response.text
        and secret not in caplog.text
    )
    assert token not in caplog.text


def test_password_reset_does_not_bypass_email_confirmation(verification):
    c, _, outgoing, register = verification
    _, name, email = register()
    confirmation = token_from(outgoing)
    c.post("/api/auth/forgot-password", json={"email": email})
    reset = token_from(outgoing)
    assert (
        c.post(
            "/api/auth/reset-password",
            json={"token": reset, "new_password": "Recovered-verification!2026"},
        ).status_code
        == 200
    )
    assert (
        c.post(
            "/api/auth/login",
            json={"username": name, "password": "Recovered-verification!2026"},
        ).status_code
        == 409
    )
    assert (
        c.post("/api/auth/verify-email", json={"token": confirmation}).status_code
        == 200
    )
    assert (
        c.post(
            "/api/auth/login",
            json={"username": name, "password": "Recovered-verification!2026"},
        ).status_code
        == 200
    )


def test_concurrent_confirmation_has_only_one_success(verification):
    from concurrent.futures import ThreadPoolExecutor
    from fastapi import HTTPException

    _, _, outgoing, register = verification
    register()
    token = token_from(outgoing)

    def confirm(_):
        with Session(engine) as db:
            try:
                service.confirm_email(db, token)
                return 200
            except HTTPException as exc:
                return exc.status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(confirm, range(2)))
    assert sorted(results) == [200, 400]
