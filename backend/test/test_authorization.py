"""Vérifier les droits persistants avec l’authentification réelle, sur la base de test."""

from typing import Annotated
from uuid import uuid4
from fastapi import Depends
import pytest
from sqlalchemy.orm import Session
from api.database import User, engine
from api.database.models import Role, Permission
from api.services.authorization import (
    create_role,
    create_permission,
    grant_role,
    revoke_role,
    grant_permission,
    revoke_permission,
    has_role,
    has_permission,
    require_roles,
    require_permissions,
    require_access,
    get_access,
)
from api.services.jwt import create_token, isAdmin
from .test_profile_and_cache import account_client  # noqa: F401


@pytest.fixture
def secured(request):
    """Installer les trois formes de dépendances sur l’application de test uniquement."""
    client, name, headers, _, _, config = request.getfixturevalue("account_client")
    app = client.app

    @app.get("/test/role", dependencies=[Depends(require_roles("editor", "admin"))])
    def role_route():
        return {"ok": True}

    @app.get("/test/permission")
    def permission_route(
        user: Annotated[
            User, Depends(require_permissions("reports.read", "reports.export"))
        ],
    ):
        return {"username": user.username}

    @app.get(
        "/test/both",
        dependencies=[
            Depends(require_access(roles=("editor",), permissions=("reports.export",)))
        ],
    )
    def both_route():
        return {"ok": True}

    @app.get(
        "/test/either",
        dependencies=[
            Depends(
                require_access(
                    roles=("editor",), permissions=("reports.export",), mode="any"
                )
            )
        ],
    )
    def either_route():
        return {"ok": True}

    @app.get("/test/admin", dependencies=[Depends(isAdmin)])
    def admin_route():
        return {"ok": True}

    with Session(engine) as db:
        for role in ("editor", "admin"):
            create_role(db, role)
        for permission in ("reports.read", "reports.export"):
            create_permission(db, permission)
        db.commit()
    yield client, name, headers, config


def test_dependencies_and_immediate_revocation(secured):
    """La même session JWT reflète immédiatement les attributions et révocations."""
    client, name, headers, _ = secured
    assert client.get("/test/role").status_code == 401
    for path in ("role", "permission", "both", "either"):
        assert client.get("/test/" + path, headers=headers).status_code == 403
    with Session(engine) as db:
        user = User.get(db=db, username=name)
        grant_role(db, user, "editor")
        role = db.query(Role).filter_by(name="editor").one()
        grant_permission(db, role, "reports.read")
        db.commit()
    assert client.get("/test/role", headers=headers).status_code == 200
    assert client.get("/test/either", headers=headers).status_code == 200
    assert client.get("/test/both", headers=headers).status_code == 403
    with Session(engine) as db:
        user = User.get(db=db, username=name)
        grant_permission(db, user, "reports.export")
        db.commit()
    assert client.get("/test/permission", headers=headers).json()["username"] == name
    assert client.get("/test/both", headers=headers).status_code == 200
    with Session(engine) as db:
        role = db.query(Role).filter_by(name="editor").one()
        revoke_permission(db, role, "reports.read")
        db.commit()
    assert client.get("/test/permission", headers=headers).status_code == 403
    with Session(engine) as db:
        grant_permission(
            db, db.query(Role).filter_by(name="editor").one(), "reports.read"
        )
        db.commit()
    with Session(engine) as db:
        user = User.get(db=db, username=name)
        revoke_role(db, user, "editor")
        db.commit()
    assert client.get("/test/role", headers=headers).status_code == 403
    assert client.get("/test/permission", headers=headers).status_code == 403
    assert client.get("/test/either", headers=headers).status_code == 200
    with Session(engine) as db:
        revoke_permission(db, User.get(db=db, username=name), "reports.export")
        db.commit()
    assert client.get("/test/either", headers=headers).status_code == 403


def test_jwt_cannot_grant_admin_and_admin_has_no_implicit_permissions(secured):
    """Un claim role=admin n’accorde rien ; le rôle SQL n’a pas de bypass implicite."""
    client, name, headers, _ = secured
    forged_claims = {
        "Authorization": "Bearer "
        + create_token(
            {"username": name, "role": "admin", "permissions": ["reports.export"]}
        )
    }
    assert client.get("/test/admin", headers=forged_claims).status_code == 403
    with Session(engine) as db:
        grant_role(db, User.get(db=db, username=name), "admin")
        db.commit()
    assert client.get("/test/admin", headers=headers).status_code == 200
    assert client.get("/test/permission", headers=forged_claims).status_code == 403
    with Session(engine) as db:
        revoke_role(db, User.get(db=db, username=name), "admin")
        db.commit()
    assert client.get("/test/admin", headers=headers).status_code == 403


def test_helpers_transactions_and_duplicate_grants(secured):
    """Les utilitaires n’imposent pas de commit, ni de doublons, et cumulent les sources."""
    _, name, _, _ = secured
    with Session(engine) as db:
        user = User.get(db=db, username=name)
        role = create_role(db, "custom-" + uuid4().hex)
        permission = create_permission(db, "custom." + uuid4().hex)
        assert create_role(db, role.name).id == role.id
        assert create_permission(db, permission.name).id == permission.id
        grant_role(db, user, role.name)
        grant_role(db, user, role.name)
        grant_permission(db, role, permission.name)
        grant_permission(db, user, permission.name)
        assert has_role(db, user, role.name)
        assert has_permission(db, user, permission.name)
        assert not has_permission(db, user, permission.name, "missing")
        assert has_permission(db, user, permission.name, "missing", match="any")
        revoke_permission(db, user, permission.name)
        assert has_permission(db, user, permission.name)
        revoke_role(db, user, role.name)
        assert not has_permission(db, user, permission.name)
        db.rollback()
        assert not has_role(db, user, role.name)
        with pytest.raises(ValueError):
            grant_role(db, user, "unknown")
        with pytest.raises(ValueError):
            grant_permission(db, user, "unknown")


def test_invalid_rules_fail_closed():
    """Une faute de configuration ne doit jamais ouvrir silencieusement une route."""
    for factory in (require_roles, require_permissions):
        for names in ((), ("",), ("*",), ("Admin",)):
            with pytest.raises(ValueError):
                factory(*names)
    with pytest.raises(ValueError):
        require_access(roles="admin")
    with pytest.raises(ValueError):
        require_access()
    with pytest.raises(ValueError):
        require_roles("editor", match="invalid")


def test_deletion_cleans_associations(secured):
    """Supprimer un utilisateur ou un rôle ne laisse pas d’attribution ORM résiduelle."""
    _, name, _, _ = secured
    with Session(engine) as db:
        user = User.get(db=db, username=name)
        role = create_role(db, "delete-" + uuid4().hex)
        permission = create_permission(db, "delete." + uuid4().hex)
        grant_role(db, user, role.name)
        grant_permission(db, role, permission.name)
        db.delete(role)
        db.flush()
        assert permission.name not in get_access(db, user).permissions
        grant_permission(db, user, permission.name)
        db.delete(user)
        db.flush()
        assert db.query(Permission).filter_by(id=permission.id).one().users == []
        db.rollback()
