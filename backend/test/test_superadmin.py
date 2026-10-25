"""Initialisation privilégiée et API, sans accès aux données de développement."""

import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4
import pytest
from fastapi import Depends
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from werkzeug.security import check_password_hash
from api.database import Base, User, engine
from api.services.authorization import has_permission, has_role, require_permissions
from scripts.init_superadmin import initialize
from .test_profile_and_cache import account_client  # noqa: F401


def test_initialize_is_explicit_and_idempotent(tmp_path):
    """La commande ne promeut pas un compte normal implicitement et ne change pas son secret."""
    isolated = create_engine(f"sqlite:///{tmp_path / 'root.db'}")
    Base.metadata.create_all(isolated)
    with Session(isolated) as db:
        user = initialize(
            db,
            username="test-root",
            email="root@example.com",
            password="RootTestPassword!2026",
        )
        db.commit()
        assert user.is_superuser
        assert check_password_hash(user.password, "RootTestPassword!2026")
        before = user.password
        assert has_permission(db, user, "future.permission")
        assert has_role(db, user, "future-role")
        initialize(db, username="test-root", password="DoNotReplace!2026")
        db.commit()
        assert user.password == before
        ordinary = User(username="ordinary", telephone=None, password="unchanged-hash")
        db.add(ordinary)
        db.commit()
        with pytest.raises(ValueError):
            initialize(db, username="ordinary")
        assert not ordinary.is_superuser
        initialize(db, username="ordinary", promote_existing=True)
        db.commit()
        assert ordinary.is_superuser and ordinary.password == "unchanged-hash"
    isolated.dispose()


def test_cli_password_stdin_is_not_logged(tmp_path):
    """Le mode automatisé lit le mot de passe sur stdin et n’affiche jamais sa valeur."""
    url = f"sqlite:///{tmp_path / 'cli.db'}"
    isolated = create_engine(url)
    Base.metadata.create_all(isolated)
    root = Path(__file__).resolve().parents[1]
    environment = {**os.environ, "DATABASE_URL": url}
    secret = "CliTestPassword!2026"
    command = [
        sys.executable,
        "-m",
        "scripts.init_superadmin",
        "--username",
        "cli-root",
        "--email",
        "cli@example.com",
        "--password-stdin",
    ]
    for _ in range(2):
        result = subprocess.run(
            command,
            cwd=root,
            env=environment,
            input=secret + "\n",
            text=True,
            capture_output=True,
        )
        assert result.returncode == 0, result.stderr
        assert secret not in result.stdout + result.stderr
    with Session(isolated) as db:
        user = User.get(db=db, username="cli-root")
        assert user.is_superuser and check_password_hash(user.password, secret)
    isolated.dispose()


def test_superadmin_can_manage_and_create_normal_users(request):
    """Les droits futurs sont accordés au superadmin ; aucun champ public ne permet ce statut."""
    client, name, headers, other, other_headers, _ = request.getfixturevalue(
        "account_client"
    )
    assert (
        client.get("/api/access/me", headers=other_headers).json()["data"][
            "is_superuser"
        ]
        is False
    )
    assert (
        client.post(
            "/api/access/users",
            headers=headers,
            json={"username": "denied", "password": "TestPassword!2026"},
        ).status_code
        == 403
    )
    with Session(engine) as db:
        initialize(db, username=name, promote_existing=True)
        db.commit()

    @client.app.get(
        "/test/future",
        dependencies=[Depends(require_permissions("future.unregistered"))],
    )
    def future():
        return {"ok": True}

    assert client.get("/test/future", headers=headers).status_code == 200
    assert client.get("/test/future", headers=other_headers).status_code == 403
    assert (
        client.get("/api/access/me", headers=headers).json()["data"]["is_superuser"]
        is True
    )
    assert client.get("/api/access/users", headers=headers).status_code == 200
    username = "created_" + uuid4().hex
    payload = {
        "username": username,
        "email": username + "@example.com",
        "password": "NormalPassword!2026",
    }
    response = client.post("/api/access/users", headers=headers, json=payload)
    assert response.status_code == 200, response.text
    assert response.json()["data"]["is_superuser"] is False
    assert "password" not in response.json()["data"]
    payload["username"] += "_privileged"
    payload["is_superuser"] = True
    assert (
        client.post("/api/access/users", headers=headers, json=payload).status_code
        == 400
    )
    with Session(engine) as db:
        user = User.get(db=db, username=name)
        user.is_superuser = False
        db.commit()
    assert client.get("/test/future", headers=headers).status_code == 403
