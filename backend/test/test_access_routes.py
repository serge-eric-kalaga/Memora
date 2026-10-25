"""Administration des droits via HTTP, exclusivement sur la base de test isolée."""

from uuid import uuid4
import pytest
from sqlalchemy.orm import Session
from api.database import User, engine
from api.services.authorization import (
    create_permission,
    grant_permission,
    revoke_permission,
)
from api.services.jwt import create_token
from .test_profile_and_cache import account_client  # noqa: F401


@pytest.fixture
def access_client(request):
    """Accorder explicitement les deux permissions au seul compte administrateur de test."""
    client, name, headers, other, other_headers, _ = request.getfixturevalue(
        "account_client"
    )
    with Session(engine) as db:
        for permission in ("access.read", "access.manage"):
            create_permission(db, permission)
            grant_permission(db, User.get(db=db, username=name), permission)
        db.commit()
    return client, name, headers, other, other_headers


def test_every_route_is_protected(access_client):
    """Ni un visiteur, ni un compte ordinaire, ni un claim JWT ne donne accès."""
    client, _, _, other, other_headers = access_client
    cases = [
        ("GET", "/roles"),
        ("POST", "/roles"),
        ("GET", "/roles/1"),
        ("GET", "/permissions"),
        ("POST", "/permissions"),
        ("GET", f"/users/{other}"),
    ]
    for base in (
        f"/users/{other}/roles/1",
        f"/users/{other}/permissions/1",
        "/roles/1/permissions/1",
    ):
        cases.extend([(method, base) for method in ("PUT", "DELETE")])
    for method, path in cases:
        assert client.request(method, "/api/access" + path).status_code == 401
        assert (
            client.request(
                method, "/api/access" + path, headers=other_headers
            ).status_code
            == 403
        )
    forged = {
        "Authorization": "Bearer "
        + create_token(
            {"username": other, "role": "admin", "permissions": ["access.manage"]}
        )
    }
    assert (
        client.post(
            "/api/access/roles", headers=forged, json={"name": "forged"}
        ).status_code
        == 403
    )


def test_create_list_assign_and_revoke(access_client):
    """Création idempotente, pagination et cumul des permissions directes/héritées."""
    client, _, headers, other, _ = access_client
    role_name, permission_name = "role-" + uuid4().hex, "reports." + uuid4().hex
    role = client.post(
        "/api/access/roles", json={"name": role_name}, headers=headers
    ).json()["data"]
    permission = client.post(
        "/api/access/permissions", json={"name": permission_name}, headers=headers
    ).json()["data"]
    assert (
        client.post(
            "/api/access/roles", json={"name": role_name}, headers=headers
        ).json()["data"]["id"]
        == role["id"]
    )
    assert (
        client.post(
            "/api/access/permissions", json={"name": permission_name}, headers=headers
        ).json()["data"]["id"]
        == permission["id"]
    )
    for catalogue, name in (("roles", role_name), ("permissions", permission_name)):
        result = client.get(
            "/api/access/" + catalogue,
            params={"q": name, "sort": "name", "page_size": 1},
            headers=headers,
        )
        assert result.status_code == 200
        assert result.json()["data"]["total"] == 1
    role_link = f"/api/access/users/{other}/roles/{role['id']}"
    inherited_link = f"/api/access/roles/{role['id']}/permissions/{permission['id']}"
    direct_link = f"/api/access/users/{other}/permissions/{permission['id']}"
    for link in (role_link, inherited_link, direct_link):
        for _ in range(2):
            assert client.put(link, headers=headers).status_code == 200
    detail = client.get(f"/api/access/roles/{role['id']}", headers=headers).json()[
        "data"
    ]
    assert [p["name"] for p in detail["permissions"]] == [permission_name]

    def access():
        return client.get(f"/api/access/users/{other}", headers=headers).json()["data"]

    assert access()["roles"] == [role_name]
    assert access()["direct_permissions"] == [permission_name]
    assert access()["permissions"] == [permission_name]
    assert client.delete(direct_link, headers=headers).status_code == 200
    assert access()["direct_permissions"] == []
    assert access()["permissions"] == [permission_name]
    for link in (inherited_link, role_link, direct_link):
        for _ in range(2):
            assert client.delete(link, headers=headers).status_code == 200
    assert access()["permissions"] == []
    assert access()["roles"] == []


def test_read_only_and_immediate_revocation(access_client):
    """Un lecteur ne peut pas modifier les droits, même les siens."""
    client, name, headers, _, _ = access_client
    with Session(engine) as db:
        revoke_permission(db, User.get(db=db, username=name), "access.manage")
        db.commit()
    assert client.get("/api/access/roles", headers=headers).status_code == 200
    assert (
        client.post(
            "/api/access/roles", headers=headers, json={"name": "denied"}
        ).status_code
        == 403
    )
    with Session(engine) as db:
        revoke_permission(db, User.get(db=db, username=name), "access.read")
        db.commit()
    assert client.get("/api/access/roles", headers=headers).status_code == 403


def test_invalid_or_unknown_targets(access_client):
    """Aucune cible inconnue n’est créée implicitement et les noms sont validés."""
    client, _, headers, other, _ = access_client
    assert (
        client.get("/api/access/roles/2147483647", headers=headers).status_code == 404
    )
    assert (
        client.put(
            f"/api/access/users/{other}/roles/2147483647", headers=headers
        ).status_code
        == 404
    )
    assert (
        client.get("/api/access/users/missing-account", headers=headers).status_code
        == 404
    )
    for name in ("", "*", "Admin", "x" * 101):
        assert (
            client.post(
                "/api/access/roles", headers=headers, json={"name": name}
            ).status_code
            == 400
        )
    assert (
        client.post(
            "/api/access/roles",
            headers=headers,
            json={"name": "valid", "permissions": ["access.manage"]},
        ).status_code
        == 400
    )
    assert (
        client.get("/api/access/roles?sort=password", headers=headers).status_code
        == 422
    )


def test_disable_restore_and_edit_access(access_client):
    """Une suspension est effective immédiatement et conserve les liens pour la réactivation."""
    from api.services.authorization import (
        create_role,
        grant_role,
        has_role,
        has_permission,
    )

    client, name, headers, other, _ = access_client
    code = "resource." + uuid4().hex
    with Session(engine) as db:
        role = create_role(db, "role." + uuid4().hex)
        permission = create_permission(db, code)
        user = User.get(db=db, username=other)
        grant_role(db, user, role.name)
        grant_permission(db, role, code)
        db.commit()
        role_id, permission_id, role_name = role.id, permission.id, role.name
        assert has_permission(db, user, code)

    def edit(resource, identifier, active):
        return client.patch(
            f"/api/access/{resource}/{identifier}",
            headers=headers,
            json={"description": "Description métier", "is_active": active},
        )

    response = edit("roles", role_id, False)
    assert response.status_code == 200
    assert response.json()["data"]["description"] == "Description métier"
    with Session(engine) as db:
        user = User.get(db=db, username=other)
        assert not has_role(db, user, role_name)
        assert not has_permission(db, user, code)  # rôle suspendu
        grant_permission(db, user, code)
        db.commit()
        assert has_permission(db, user, code)  # autre source active
    assert edit("permissions", permission_id, False).status_code == 200
    with Session(engine) as db:
        user = User.get(db=db, username=other)
        assert not has_permission(db, user, code)
        assert len(user.roles) == 1 and len(user.permissions) == 1
    assert edit("roles", role_id, True).status_code == 200
    assert edit("permissions", permission_id, True).status_code == 200
    with Session(engine) as db:
        user = User.get(db=db, username=other)
        assert has_role(db, user, role_name) and has_permission(db, user, code)
    assert (
        client.patch(
            f"/api/access/permissions/{permission_id}",
            headers=headers,
            json={"name": "renamed", "description": "", "is_active": True},
        ).status_code
        == 400
    )
    assert (
        client.patch(
            f"/api/access/roles/{role_id}", json={"description": "", "is_active": False}
        ).status_code
        == 401
    )
    assert (
        client.patch(
            f"/api/access/roles/{role_id}",
            headers=access_client[4],
            json={"description": "", "is_active": False},
        ).status_code
        == 403
    )
