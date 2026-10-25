"""Confirmation d’adresse : secrets hachés, consommation atomique et accès conditionnel."""

from datetime import timedelta
from hashlib import sha256
import secrets
from urllib.parse import urlsplit

from fastapi import HTTPException, Request
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from api.database import User, engine
from api.services import mail
from api.services.password import consume_limit, utc_now
from api.configs.logging import logInfo

PENDING_MESSAGE = "Confirmez votre adresse e-mail avant de vous connecter."
GENERIC_MESSAGE = (
    "Si une confirmation est nécessaire, vous recevrez un nouveau lien par e-mail."
)
INVALID_MESSAGE = (
    "Le lien de confirmation est invalide ou a expiré. Demandez un nouveau lien."
)


def require_verified_email(user: User, config):
    """Appliquer le blocage uniquement aux comptes inscrits ou modifiés sous l’option active."""
    if (
        config.EMAIL_VERIFICATION_ENABLED
        and user.email_verification_required
        and user.email_verified_at is None
    ):
        raise HTTPException(409, PENDING_MESSAGE)


def allow_request(db: Session, request: Request, email: str, config) -> bool:
    """Limiter les envois par IP puis adresse, sans exposer leur existence."""
    ip = request.client.host if request.client else "unknown"
    return consume_limit(
        db,
        [
            (f"verification:ip:{ip}", config.EMAIL_VERIFICATION_IP_LIMIT),
            (f"verification:email:{email}", config.EMAIL_VERIFICATION_EMAIL_LIMIT),
        ],
        config,
        config.EMAIL_VERIFICATION_WINDOW_SECONDS,
    )


def queue_confirmation_email(email: str, language: str, config):
    """Préparer et envoyer après la réponse, avec un lien lié à l’adresse courante."""
    if not config.EMAIL_VERIFICATION_ENABLED:
        return
    try:
        parts = urlsplit(config.FRONTEND_URL)
        if (
            parts.scheme not in {"http", "https"}
            or not parts.netloc
            or parts.username
            or parts.password
            or parts.query
            or parts.fragment
        ):
            logInfo("FRONTEND_URL invalide pour la confirmation d’adresse")
            return
        with Session(engine) as db:
            user = db.scalar(select(User).where(User.email == email).with_for_update())
            if user is None or user.email_verified_at is not None:
                return
            user_id = user.id
            token = secrets.token_urlsafe(32)
            digest = sha256(token.encode()).hexdigest()
            user.email_verification_digest = digest
            user.email_verification_expires_at = utc_now() + timedelta(
                minutes=config.EMAIL_VERIFICATION_EXPIRE_MINUTES
            )
            db.commit()
            link = f"{config.FRONTEND_URL.rstrip('/')}/confirmer-email#token={token}"
            if not mail.send_email_verification(
                email,
                link,
                config.EMAIL_VERIFICATION_EXPIRE_MINUTES,
                language,
                config.APP_NAME,
            ):
                db.execute(
                    update(User)
                    .where(User.id == user_id, User.email_verification_digest == digest)
                    .values(
                        email_verification_digest=None,
                        email_verification_expires_at=None,
                    )
                )
                db.commit()
    except Exception:
        # Aucun traceback SMTP : il pourrait contenir le lien ou le destinataire.
        logInfo("La confirmation d’adresse n’a pas pu être envoyée")


def confirm_email(db: Session, token: str):
    """Un UPDATE conditionnel garantit l’usage unique, y compris entre plusieurs workers."""
    digest = sha256(token.encode()).hexdigest()
    result = db.execute(
        update(User)
        .where(
            User.email_verification_digest == digest,
            User.email_verification_expires_at > utc_now(),
            User.email_verified_at.is_(None),
        )
        .values(
            email_verified_at=utc_now(),
            email_verification_digest=None,
            email_verification_expires_at=None,
            # Révoquer les sessions éventuellement obtenues lorsque l’option était désactivée.
            auth_version=User.auth_version + 1,
            password_reset_digest=None,
            password_reset_expires_at=None,
        )
    )
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(400, INVALID_MESSAGE)
    db.commit()
