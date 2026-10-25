"""Administration RBAC minimale : catalogues et attributions, sans promotion publique."""

from contextlib import contextmanager
from typing import Annotated
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Path,
    Query,
    Request,
    BackgroundTasks,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError
from api.database import User
from api.database.models import Role, Permission
from api.schemas.response import Response
from api.schemas.access import (
    AccessName,
    AccessUpdate,
    AccessItem,
    RoleDetail,
    UserAccess,
    AdminCreateUser,
    AdminUser,
)
from api.services.cache import invalidate_cache
from api.services.pagination import ListParams, Page, paginate
from api.services.authorization import (
    CurrentUser,
    DatabaseSession,
    require_permissions,
    create_role,
    create_permission,
    grant_role,
    revoke_role,
    grant_permission,
    revoke_permission,
    get_access,
)

router = APIRouter(
    tags=["ACCESS"],
    responses={
        401: {"description": "Authentification requise"},
        403: {"description": "Permission access.read ou access.manage requise"},
    },
)
Read = [Depends(require_permissions("access.read"))]
Manage = [Depends(require_permissions("access.manage"))]
Identifier = Annotated[int, Path(ge=1)]


def _get(db, model, identifier):
    """Retourner un objet existant, sans créer implicitement une attribution inconnue."""
    item = db.get(model, identifier)
    if item is None:
        raise HTTPException(404, "Rôle ou permission introuvable")
    return item


@contextmanager
def _transaction(db):
    """Valider une seule opération ; restituer un conflit concurrent sans détail SQL."""
    try:
        yield
        db.commit()
    except (IntegrityError, StaleDataError):
        db.rollback()
        raise HTTPException(409, "Modification concurrente. Réessayez.") from None
    except Exception:
        db.rollback()
        raise


def _catalogue(db, model, params):
    """Réutiliser les conventions de pagination, recherche et tri du template."""
    return Response(
        data=paginate(
            db.query(model),
            params,
            sort_columns={"id": model.id, "name": model.name},
            search_columns=(model.name,),
            tie_breaker=model.id,
        )
    )


@router.get(
    "/roles",
    operation_id="listRoles",
    response_model=Response[Page[AccessItem]],
    dependencies=Read,
)
def list_roles(db: DatabaseSession, params: Annotated[ListParams, Query()]):
    """Lister les rôles ; permission access.read requise."""
    return _catalogue(db, Role, params)


@router.post(
    "/roles",
    operation_id="createRole",
    response_model=Response[AccessItem],
    dependencies=Manage,
)
def add_role(body: AccessName, db: DatabaseSession):
    """Créer un rôle ou retourner celui du même nom ; access.manage requise."""
    with _transaction(db):
        role = create_role(db, body.name)
    return Response(data=role)


@router.get(
    "/roles/{role_id}",
    operation_id="getRole",
    response_model=Response[RoleDetail],
    dependencies=Read,
)
def role_detail(role_id: Identifier, db: DatabaseSession):
    """Consulter un rôle et ses permissions."""
    role = _get(db, Role, role_id)
    return Response(
        data=RoleDetail(
            id=role.id,
            name=role.name,
            description=role.description,
            is_active=role.is_active,
            permissions=[
                AccessItem.model_validate(p)
                for p in sorted(role.permissions, key=lambda p: p.name)
            ],
        )
    )


@router.get(
    "/permissions",
    operation_id="listPermissions",
    response_model=Response[Page[AccessItem]],
    dependencies=Read,
)
def list_permissions(db: DatabaseSession, params: Annotated[ListParams, Query()]):
    """Lister les permissions ; permission access.read requise."""
    return _catalogue(db, Permission, params)


@router.post(
    "/permissions",
    operation_id="createPermission",
    response_model=Response[AccessItem],
    dependencies=Manage,
)
def add_permission(body: AccessName, db: DatabaseSession):
    """Créer une permission ou retourner celle du même nom ; access.manage requise."""
    with _transaction(db):
        permission = create_permission(db, body.name)
    return Response(data=permission)


@router.get(
    "/users/{username}",
    operation_id="getUserAccess",
    response_model=Response[UserAccess],
    dependencies=Read,
)
def user_access(username: str, db: DatabaseSession):
    """Consulter les rôles, permissions directes et permissions effectives d’un compte."""
    user = User.get(db=db, username=username)
    access = get_access(db, user)
    return Response(
        data=UserAccess(
            is_superuser=user.is_superuser,
            username=user.username,
            roles=sorted(role.name for role in user.roles),
            direct_permissions=sorted(p.name for p in user.permissions),
            permissions=sorted(access.permissions),
        )
    )


@router.put(
    "/users/{username}/roles/{role_id}",
    operation_id="grantUserRole",
    response_model=Response[None],
    dependencies=Manage,
)
def assign_role(username: str, role_id: Identifier, db: DatabaseSession):
    """Attribuer un rôle existant ; un lien déjà présent est accepté."""
    user = User.get(db=db, username=username)
    role = _get(db, Role, role_id)
    with _transaction(db):
        grant_role(db, user, role.name)
    return Response(data=None)


@router.delete(
    "/users/{username}/roles/{role_id}",
    operation_id="revokeUserRole",
    response_model=Response[None],
    dependencies=Manage,
)
def unassign_role(username: str, role_id: Identifier, db: DatabaseSession):
    """Retirer le lien de rôle ; un lien déjà absent est accepté."""
    user = User.get(db=db, username=username)
    role = _get(db, Role, role_id)
    with _transaction(db):
        revoke_role(db, user, role.name)
    return Response(data=None)


@router.put(
    "/roles/{role_id}/permissions/{permission_id}",
    operation_id="grantRolePermission",
    response_model=Response[None],
    dependencies=Manage,
)
def assign_role_permission(
    role_id: Identifier, permission_id: Identifier, db: DatabaseSession
):
    """Accorder une permission existante à un rôle."""
    role, permission = _get(db, Role, role_id), _get(db, Permission, permission_id)
    with _transaction(db):
        grant_permission(db, role, permission.name)
    return Response(data=None)


@router.delete(
    "/roles/{role_id}/permissions/{permission_id}",
    operation_id="revokeRolePermission",
    response_model=Response[None],
    dependencies=Manage,
)
def unassign_role_permission(
    role_id: Identifier, permission_id: Identifier, db: DatabaseSession
):
    """Retirer une permission du rôle, donc de tous ses bénéficiaires indirects."""
    role, permission = _get(db, Role, role_id), _get(db, Permission, permission_id)
    with _transaction(db):
        revoke_permission(db, role, permission.name)
    return Response(data=None)


@router.put(
    "/users/{username}/permissions/{permission_id}",
    operation_id="grantUserPermission",
    response_model=Response[None],
    dependencies=Manage,
)
def assign_user_permission(
    username: str, permission_id: Identifier, db: DatabaseSession
):
    """Accorder directement une permission à un compte."""
    user, permission = (
        User.get(db=db, username=username),
        _get(db, Permission, permission_id),
    )
    with _transaction(db):
        grant_permission(db, user, permission.name)
    return Response(data=None)


@router.delete(
    "/users/{username}/permissions/{permission_id}",
    operation_id="revokeUserPermission",
    response_model=Response[None],
    dependencies=Manage,
)
def unassign_user_permission(
    username: str, permission_id: Identifier, db: DatabaseSession
):
    """Retirer le lien direct ; les permissions héritées restent effectives."""
    user, permission = (
        User.get(db=db, username=username),
        _get(db, Permission, permission_id),
    )
    with _transaction(db):
        revoke_permission(db, user, permission.name)
    return Response(data=None)


@router.get("/me", operation_id="getMyAccess", response_model=Response[UserAccess])
def my_access(user: CurrentUser, db: DatabaseSession):
    """Consulter uniquement ses propres droits, pour adapter l’interface."""
    return user_access(user.username, db)


@router.get(
    "/users",
    operation_id="listAdminUsers",
    response_model=Response[Page[AdminUser]],
    dependencies=Read,
)
def list_users(db: DatabaseSession, params: Annotated[ListParams, Query()]):
    """Lister et rechercher les utilisateurs pour gérer leurs attributions."""
    return Response(
        data=paginate(
            db.query(User),
            params,
            sort_columns={"id": User.id, "username": User.username},
            search_columns=(User.username, User.email),
            tie_breaker=User.id,
        )
    )


@router.post(
    "/users",
    operation_id="adminCreateUser",
    response_model=Response[AdminUser],
    dependencies=[
        Depends(require_permissions("users.create")),
        Depends(invalidate_cache("users")),
    ],
)
def create_admin_user(
    body: AdminCreateUser, request: Request, tasks: BackgroundTasks, db: DatabaseSession
):
    """Créer un compte normal en conservant la confirmation d’e-mail configurée."""
    from api.views.auth.user import create_user

    create_user(body, request, tasks, db)
    return Response(data=User.get(db=db, username=body.username))


@router.patch(
    "/roles/{role_id}",
    operation_id="updateRole",
    response_model=Response[AccessItem],
    dependencies=Manage,
)
def update_role(role_id: Identifier, body: AccessUpdate, db: DatabaseSession):
    """Modifier les métadonnées du rôle ; sa désactivation suspend ses droits hérités."""
    role = _get(db, Role, role_id)
    with _transaction(db):
        role.description = body.description
        role.is_active = body.is_active
    return Response(data=role)


@router.patch(
    "/permissions/{permission_id}",
    operation_id="updatePermission",
    response_model=Response[AccessItem],
    dependencies=Manage,
)
def update_permission(
    permission_id: Identifier, body: AccessUpdate, db: DatabaseSession
):
    """Modifier la description ou suspendre la permission ; conserver son code métier."""
    permission = _get(db, Permission, permission_id)
    with _transaction(db):
        permission.description = body.description
        permission.is_active = body.is_active
    return Response(data=permission)
