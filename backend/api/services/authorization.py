"""Rôles et permissions persistants : contrôles métier et dépendances FastAPI."""

from dataclasses import dataclass
import re
from typing import Annotated, Literal
from fastapi import Depends, HTTPException
from sqlalchemy import select, union
from sqlalchemy.orm import Session
from api.database import get_db, User
from api.database.models import (
    Role,
    Permission,
    user_roles,
    role_permissions,
    user_permissions,
)
from api.services.jwt import getPayload

Match = Literal["all", "any"]
DatabaseSession = Annotated[Session, Depends(get_db)]
Payload = Annotated[dict, Depends(getPayload)]


def _names(names):
    """Refuser les noms vides, jokers et caractères ambigus dès la configuration."""
    if isinstance(names, (str, bytes)):
        raise ValueError("Fournir une collection de noms, pas une chaîne seule")
    names = tuple(names)
    if not names or any(
        not isinstance(n, str) or not re.fullmatch(r"[a-z][a-z0-9_.:-]{0,99}", n)
        for n in names
    ):
        raise ValueError("Nom de rôle/permission invalide")
    return names


def _matches(actual, expected, match: Match):
    """Appliquer une règle explicite ; une règle inconnue est une erreur de configuration."""
    if match not in ("all", "any"):
        raise ValueError("Utiliser all ou any")
    return (
        set(expected) <= actual
        if match == "all"
        else bool(actual.intersection(expected))
    )


@dataclass(frozen=True)
class Access:
    """Instantané des droits effectifs : union des permissions directes et des rôles."""

    roles: frozenset[str]
    permissions: frozenset[str]
    is_superuser: bool = False


def get_access(db: Session, user: User) -> Access:
    """Lire les droits SQL actuels sans utiliser les claims du JWT ni un cache Redis."""
    roles = db.scalars(
        select(Role.name)
        .join(user_roles)
        .where(user_roles.c.user_id == user.id, Role.is_active.is_(True))
    ).all()
    direct = (
        select(Permission.name)
        .join(user_permissions)
        .where(user_permissions.c.user_id == user.id, Permission.is_active.is_(True))
    )
    inherited = (
        select(Permission.name)
        .join(role_permissions)
        .join(Role, Role.id == role_permissions.c.role_id)
        .join(user_roles, user_roles.c.role_id == role_permissions.c.role_id)
        .where(
            user_roles.c.user_id == user.id,
            Role.is_active.is_(True),
            Permission.is_active.is_(True),
        )
    )
    permissions = db.scalars(
        select(Permission.name) if user.is_superuser else union(direct, inherited)
    ).all()
    return Access(frozenset(roles), frozenset(permissions), user.is_superuser)


def has_role(db: Session, user: User, *names: str, match: Match = "any") -> bool:
    """Vérifier un des rôles demandés, ou tous avec match=all."""
    names = _names(names)
    access = get_access(db, user)
    matched = _matches(access.roles, names, match)
    return access.is_superuser or matched


def has_permission(db: Session, user: User, *names: str, match: Match = "all") -> bool:
    """Vérifier toutes les permissions demandées, ou une seule avec match=any."""
    names = _names(names)
    access = get_access(db, user)
    matched = _matches(access.permissions, names, match)
    return access.is_superuser or matched


def current_user(payload: Payload, db: DatabaseSession) -> User:
    """Réutiliser la validation de session et d’e-mail de l’authentification existante."""
    return User.get(db=db, username=payload["username"])


CurrentUser = Annotated[User, Depends(current_user)]


def require_access(
    *,
    roles: tuple[str, ...] = (),
    permissions: tuple[str, ...] = (),
    mode: Match = "all",
    role_match: Match = "any",
    permission_match: Match = "all",
):
    """Construire une dépendance rôle ET/OU permission ; retourner l’utilisateur autorisé."""
    if not roles and not permissions:
        raise ValueError("Spécifier au moins un rôle ou une permission")
    if roles:
        roles = _names(roles)
    if permissions:
        permissions = _names(permissions)
    for match in (mode, role_match, permission_match):
        _matches(frozenset(), (), match)

    def dependency(user: CurrentUser, db: DatabaseSession) -> User:
        """Contrôler les droits avant le corps de route ; refuser avec HTTP 403."""
        access = get_access(db, user)
        if access.is_superuser:
            return user
        checks = []
        if roles:
            checks.append(_matches(access.roles, roles, role_match))
        if permissions:
            checks.append(_matches(access.permissions, permissions, permission_match))
        if not (all(checks) if mode == "all" else any(checks)):
            raise HTTPException(403, "Privilèges insuffisants")
        return user

    return dependency


def require_roles(*names: str, match: Match = "any"):
    """Protéger une route par un rôle, ou plusieurs selon match."""
    return require_access(roles=_names(names), role_match=match)


def require_permissions(*names: str, match: Match = "all"):
    """Protéger une route par des permissions effectives directes ou héritées."""
    return require_access(permissions=_names(names), permission_match=match)


def create_role(db: Session, name: str) -> Role:
    """Créer un rôle s’il n’existe pas ; laisser le commit à l’appelant."""
    _names((name,))
    role = db.scalar(select(Role).where(Role.name == name))
    if role is None:
        role = Role(name=name)
        db.add(role)
        db.flush()
    return role


def create_permission(db: Session, name: str) -> Permission:
    """Créer une permission s’il n’existe pas ; laisser le commit à l’appelant."""
    _names((name,))
    permission = db.scalar(select(Permission).where(Permission.name == name))
    if permission is None:
        permission = Permission(name=name)
        db.add(permission)
        db.flush()
    return permission


def grant_role(db: Session, user: User, name: str):
    """Attribuer un rôle existant sans doublon et sans commit implicite."""
    role = db.scalar(select(Role).where(Role.name == _names((name,))[0]))
    if role is None:
        raise ValueError("Rôle inconnu")
    if role not in user.roles:
        user.roles.append(role)
    db.flush()


def revoke_role(db: Session, user: User, name: str):
    """Retirer un rôle sans affecter les autres rôles ou permissions directes."""
    _names((name,))
    user.roles[:] = [role for role in user.roles if role.name != name]
    db.flush()


def grant_permission(db: Session, target: User | Role, name: str):
    """Accorder une permission existante à un rôle ou directement à un utilisateur."""
    permission = db.scalar(
        select(Permission).where(Permission.name == _names((name,))[0])
    )
    if permission is None:
        raise ValueError("Permission inconnue")
    if permission not in target.permissions:
        target.permissions.append(permission)
    db.flush()


def revoke_permission(db: Session, target: User | Role, name: str):
    """Retirer un lien de permission ; les autres sources de droit restent effectives."""
    _names((name,))
    target.permissions[:] = [
        permission for permission in target.permissions if permission.name != name
    ]
    db.flush()
