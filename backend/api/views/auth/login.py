from fastapi import Depends, APIRouter, HTTPException
from api.database import get_db, Session
from api.schemas.user import LoginModel
from api.services.auth import login as loginSVC
from api.schemas.user import LoginResponse

from fastapi.security import (
    OAuth2PasswordRequestForm,
)
from typing import Annotated


from fastapi import BackgroundTasks, Request
from api.schemas.email_verification import (
    ResendConfirmation,
    ConfirmEmail,
    AuthConfiguration,
)
from api.services import email_verification as verificationSVC
from api.schemas.password import ForgotPassword, ResetPassword
from api.schemas.response import Response
from api.services import password as passwordSVC
from api.services.mail import send_password_changed

auth_router = APIRouter()


@auth_router.post(
    "/login", operation_id="authLogin", tags=["AUTH"], response_model=LoginResponse
)
async def login(
    credentials: LoginModel, request: Request, db: Annotated[Session, Depends(get_db)]
):
    """
    Connecte un utilisateur et retourne un token d'accès JWT
    """

    token = loginSVC.login(db, credentials, request.app.state.config)

    return LoginResponse(data={"username": credentials.username, "token": token})


@auth_router.post("/doc-login", tags=["AUTH"], include_in_schema=False)
async def docs_login(
    credentials: Annotated[OAuth2PasswordRequestForm, Depends()],
    request: Request,
    db: Annotated[Session, Depends(get_db)],
):
    """
    Connecte un utilisateur via le formulaire de documentation et retourne un token d'accès JWT
    """

    return loginSVC.loginDoc(db, credentials, request.app.state.config)


@auth_router.post(
    "/forgot-password",
    operation_id="authForgotPassword",
    tags=["AUTH"],
    status_code=202,
    response_model=Response,
    summary="Demander un lien de réinitialisation",
)
def forgot_password(
    body: ForgotPassword,
    request: Request,
    tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
):
    """Réponse identique pour toute adresse ; envoi différé et demandes limitées par adresse/IP."""
    config = request.app.state.config
    email = str(body.email).lower()
    ip = request.client.host if request.client else "unknown"
    allowed = passwordSVC.consume_limit(
        db,
        [
            (f"reset:ip:{ip}", config.PASSWORD_RESET_IP_LIMIT),
            (f"reset:email:{email}", config.PASSWORD_RESET_EMAIL_LIMIT),
        ],
        config,
    )
    if allowed:
        tasks.add_task(passwordSVC.queue_reset_email, email, body.language, config)
    return Response(
        status_code=202, data=None, message=passwordSVC.GENERIC_RESET_MESSAGE
    )


@auth_router.post(
    "/reset-password",
    operation_id="authResetPassword",
    tags=["AUTH"],
    response_model=Response,
    summary="Réinitialiser le mot de passe avec le lien reçu par e-mail",
)
def reset_password(
    body: ResetPassword,
    request: Request,
    tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
):
    """Le jeton est à usage unique ; toute ancienne session ou demande est révoquée."""
    ip = request.client.host if request.client else "unknown"
    if not passwordSVC.consume_limit(
        db, [(f"reset:confirm:{ip}", 30)], request.app.state.config
    ):
        raise HTTPException(429, "Trop de tentatives. Réessayez plus tard.")
    email = passwordSVC.reset_password(
        db, body.token.get_secret_value(), body.new_password.get_secret_value()
    )
    if email:
        language = (
            "en"
            if request.headers.get("Accept-Language", "").startswith("en")
            else "fr"
        )
        tasks.add_task(
            send_password_changed, email, language, request.app.state.config.APP_NAME
        )
    return Response(data=None)


@auth_router.get(
    "/config",
    operation_id="authConfig",
    tags=["AUTH"],
    response_model=Response[AuthConfiguration],
    summary="Options publiques d’inscription",
)
def auth_config(request: Request):
    """Exposer uniquement le drapeau public ; aucune configuration SMTP ni secret."""
    return Response(
        data={
            "email_verification_enabled": request.app.state.config.EMAIL_VERIFICATION_ENABLED
        }
    )


@auth_router.post(
    "/resend-verification",
    operation_id="authResendVerification",
    tags=["AUTH"],
    response_model=Response,
    status_code=202,
    summary="Renvoyer le lien de confirmation",
)
def resend_verification(
    body: ResendConfirmation,
    request: Request,
    tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
):
    """Même réponse pour toute adresse, compte confirmé, limite atteinte ou option désactivée."""
    config = request.app.state.config
    if config.EMAIL_VERIFICATION_ENABLED and verificationSVC.allow_request(
        db, request, str(body.email).lower(), config
    ):
        tasks.add_task(
            verificationSVC.queue_confirmation_email,
            str(body.email).lower(),
            body.language,
            config,
        )
    return Response(status_code=202, data=None, message=verificationSVC.GENERIC_MESSAGE)


@auth_router.post(
    "/verify-email",
    operation_id="authVerifyEmail",
    tags=["AUTH"],
    response_model=Response,
    summary="Confirmer son adresse e-mail",
)
def verify_email(
    body: ConfirmEmail, request: Request, db: Annotated[Session, Depends(get_db)]
):
    """Validation explicite en POST ; ouvrir le lien ne consomme pas le jeton."""
    ip = request.client.host if request.client else "unknown"
    config = request.app.state.config
    if not passwordSVC.consume_limit(
        db,
        [(f"verification:confirm:{ip}", 30)],
        config,
        config.EMAIL_VERIFICATION_WINDOW_SECONDS,
    ):
        raise HTTPException(429, "Trop de tentatives. Réessayez plus tard.")
    verificationSVC.confirm_email(db, body.token.get_secret_value())
    return Response(data=None)
