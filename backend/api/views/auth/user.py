from typing import Annotated
from fastapi import Query
from api.services.pagination import ListParams, Page, paginate
from sqlalchemy.orm import Session
from api.schemas.user import (
    UserModel,
    RegistrationModel,
    UpdateUserModel,
    CreateUserModel,
    Response,
    CurrentUserModel,
    OwnProfileUpdate,
)
from api.services.jwt import getPayload
from api.database import get_db
from api.database import User
from api.services.auth import user as userSVC
from fastapi import Depends, File, Request, UploadFile, BackgroundTasks, HTTPException
from fastapi.responses import Response as BinaryResponse
from api.services.cache import cached_response, invalidate_cache
from api.services.profile_photo import (
    update_profile_photo,
    read_profile_photo,
    remove_profile_photo_file,
)
from fastapi import APIRouter
from .login import auth_router
from api.schemas.password import ChangePassword, ChangeEmail
from api.services import password as passwordSVC
from api.services.mail import send_password_changed, send_recovery_email_changed

# Dépendances partagées : FastAPI conserve la résolution et la fermeture de la session.
DatabaseSession = Annotated[Session, Depends(get_db)]
AuthenticatedPayload = Annotated[dict, Depends(getPayload)]

user_router = APIRouter(dependencies=[Depends(getPayload)], tags=["USER"])


@auth_router.post(
    "/register",
    operation_id="authRegister",
    response_model=Response[RegistrationModel],
    tags=["AUTH"],
    dependencies=[Depends(invalidate_cache("users"))],
)
def create_user(
    user: CreateUserModel, request: Request, tasks: BackgroundTasks, db: DatabaseSession
):
    """Créer un compte ; en mode vérification, exiger l’e-mail et différer son accès."""
    from api.services import email_verification as verification

    config = request.app.state.config
    if config.EMAIL_VERIFICATION_ENABLED:
        if not user.email:
            raise HTTPException(
                400, "Une adresse e-mail est requise pour confirmer votre compte."
            )
        if not verification.allow_request(db, request, str(user.email).lower(), config):
            raise HTTPException(429, "Trop de tentatives. Réessayez plus tard.")
    new_user = userSVC.create_user(user, db, config.EMAIL_VERIFICATION_ENABLED)
    if config.EMAIL_VERIFICATION_ENABLED:
        tasks.add_task(
            verification.queue_confirmation_email, new_user.email, user.language, config
        )
    data = UserModel.model_validate(new_user, from_attributes=True).model_dump()
    return Response(
        data=RegistrationModel(
            **data, verification_required=config.EMAIL_VERIFICATION_ENABLED
        )
    )


@user_router.get(
    "/me",
    operation_id="getCurrentUser",
    response_model=Response[CurrentUserModel],
    summary="Consulter son profil",
)
def current_user(payload: AuthenticatedPayload, db: DatabaseSession):
    """Retourner le compte du JWT et son dernier horodatage de connexion."""
    return Response(data=User.get(username=payload["username"], db=db))


@user_router.patch(
    "/me",
    operation_id="updateCurrentUser",
    response_model=Response[CurrentUserModel],
    dependencies=[Depends(invalidate_cache("users"))],
    summary="Modifier son profil",
)
def update_own_profile(
    profile: OwnProfileUpdate, payload: AuthenticatedPayload, db: DatabaseSession
):
    """Modifier uniquement les champs autorisés du compte connecté."""
    user = User.get(username=payload["username"], db=db)
    if "telephone" in profile.model_fields_set:
        user.telephone = (
            profile.telephone.strip() or None if profile.telephone is not None else None
        )
    user.saveWithCommit(db)
    return Response(data=user)


@user_router.put(
    "/me/password",
    operation_id="changePassword",
    response_model=Response,
    summary="Modifier son mot de passe",
)
def change_own_password(
    body: ChangePassword,
    request: Request,
    tasks: BackgroundTasks,
    payload: AuthenticatedPayload,
    db: DatabaseSession,
):
    """Réauthentifier le compte, changer le hash et révoquer toutes ses sessions."""
    user = User.get(username=payload["username"], db=db)
    if not passwordSVC.consume_limit(
        db, [(f"credentials:{user.id}", 10)], request.app.state.config
    ):
        raise HTTPException(429, "Trop de tentatives. Réessayez plus tard.")
    passwordSVC.change_password(
        db,
        user,
        body.current_password.get_secret_value(),
        body.new_password.get_secret_value(),
    )
    if user.email:
        language = (
            "en"
            if request.headers.get("Accept-Language", "").startswith("en")
            else "fr"
        )
        tasks.add_task(
            send_password_changed,
            user.email,
            language,
            request.app.state.config.APP_NAME,
        )
    return Response(data=None)


@user_router.patch(
    "/me/email",
    operation_id="changeEmail",
    response_model=Response,
    summary="Définir son adresse de récupération",
)
def change_own_email(
    body: ChangeEmail,
    request: Request,
    tasks: BackgroundTasks,
    payload: AuthenticatedPayload,
    db: DatabaseSession,
):
    """Exiger le mot de passe actuel ; révoquer les sessions et les liens de l’ancienne adresse."""
    user = User.get(username=payload["username"], db=db)
    if not passwordSVC.consume_limit(
        db, [(f"credentials:{user.id}", 10)], request.app.state.config
    ):
        raise HTTPException(429, "Trop de tentatives. Réessayez plus tard.")
    previous_email = user.email
    passwordSVC.change_email(
        db,
        user,
        str(body.email),
        body.current_password.get_secret_value(),
        request.app.state.config.EMAIL_VERIFICATION_ENABLED,
    )
    if request.app.state.config.EMAIL_VERIFICATION_ENABLED:
        from api.services.email_verification import queue_confirmation_email

        tasks.add_task(
            queue_confirmation_email,
            user.email,
            "en"
            if request.headers.get("Accept-Language", "").startswith("en")
            else "fr",
            request.app.state.config,
        )
    if previous_email:
        language = (
            "en"
            if request.headers.get("Accept-Language", "").startswith("en")
            else "fr"
        )
        tasks.add_task(
            send_recovery_email_changed,
            previous_email,
            language,
            request.app.state.config.APP_NAME,
        )
    return Response(data=None)


@user_router.get(
    "/",
    response_model=Response[list[UserModel]],
    dependencies=[Depends(cached_response("users"))],
)
def get_all_user(db: DatabaseSession):
    """Get all users"""

    users = User.getAll(db=db)
    return Response(data=users)


@user_router.get(
    "/page",
    operation_id="listUsersPage",
    response_model=Response[Page[UserModel]],
    summary="Lister les utilisateurs avec pagination, recherche et tri",
    description="Recherche sur username et telephone. Tri autorisé : id ou username. Authentification requise.",
    dependencies=[Depends(cached_response("users"))],
)
def list_users_page(db: DatabaseSession, params: Annotated[ListParams, Query()]):
    """Illustrer les conventions de listes sans modifier l’ancienne route de liste."""
    return Response(
        data=paginate(
            db.query(User),
            params,
            sort_columns={"id": User.id, "username": User.username},
            search_columns=(User.username, User.telephone),
            tie_breaker=User.id,
        )
    )


@user_router.get(
    "/{username}",
    response_model=Response[UserModel],
    dependencies=[Depends(cached_response("users"))],
)
def get_user_Details(username: str, db: DatabaseSession):
    """Get users details"""

    user = User.get(db=db, username=username)
    return Response(data=user)


@user_router.put(
    "/{username}",
    response_model=Response[UserModel],
    dependencies=[Depends(invalidate_cache("users"))],
)
def update_user(
    username: str,
    user: UpdateUserModel,
    payload: AuthenticatedPayload,
    db: DatabaseSession,
):
    """Update User"""

    if payload["username"] != username:
        raise HTTPException(403, "Vous pouvez uniquement modifier votre propre compte.")
    user_exist = userSVC.update_user(username, user, db)
    return Response(data=user_exist)


@user_router.delete(
    "/{username}",
    response_model=Response,
    dependencies=[Depends(invalidate_cache("users"))],
)
def delete_user(
    username: str, request: Request, payload: AuthenticatedPayload, db: DatabaseSession
):
    """Delete user"""

    if payload["username"] != username:
        raise HTTPException(
            403, "Vous pouvez uniquement supprimer votre propre compte."
        )
    user_exist = User.get(username=username, db=db)
    from api.memora import store as memora_store

    try:
        memora_store.delete_owner(user_exist.account_uid)
    except OSError:
        raise HTTPException(
            503,
            "Suppression des fichiers interrompue. Le compte est conservé, ses réunions sont bloquées. Réessayez la suppression.",
        ) from None
    user_exist.deleteWithCommit(db=db)
    remove_profile_photo_file(user_exist, request.app.state.config)

    return Response(data=f"User {username} deleted !")


@user_router.put(
    "/me/photo",
    operation_id="uploadProfilePhoto",
    response_model=Response[UserModel],
    dependencies=[Depends(invalidate_cache("users"))],
    summary="Ajouter ou remplacer sa photo de profil",
    responses={
        400: {"description": "Image illisible"},
        413: {"description": "Limite de taille ou de pixels dépassée"},
        415: {"description": "Format non accepté ou incohérent"},
        404: {"description": "Compte introuvable"},
    },
)
def upload_my_profile_photo(
    request: Request,
    photo: Annotated[
        UploadFile,
        File(
            description="Photo fixe JPEG, PNG ou WebP, 5 Mio maximum par défaut. Réencodée en WebP, 1024 × 1024 maximum, sans métadonnées."
        ),
    ],
    payload: AuthenticatedPayload,
    db: DatabaseSession,
):
    """Modifier uniquement la photo du compte désigné par le JWT, sans choisir un autre utilisateur."""
    user = update_profile_photo(
        db, payload["username"], photo, request.app.state.config
    )
    return Response(data=user)


@user_router.get(
    "/{username}/photo",
    operation_id="getProfilePhoto",
    summary="Consulter une photo de profil (authentification requise)",
    response_class=BinaryResponse,
    responses={
        200: {
            "content": {
                "image/webp": {"schema": {"type": "string", "format": "binary"}}
            }
        },
        404: {"description": "Compte ou photo introuvable"},
    },
)
def get_profile_photo(username: str, request: Request, db: DatabaseSession):
    """Lire la photo sans la mettre en cache HTTP ni stocker de binaire dans Redis."""
    return BinaryResponse(
        content=read_profile_photo(db, username, request.app.state.config),
        media_type="image/webp",
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
