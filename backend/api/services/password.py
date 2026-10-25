"""Récupération de compte : jetons hachés, usage unique et révocation des sessions."""

from datetime import UTC, datetime, timedelta
from hashlib import sha256
import hmac
import secrets
from urllib.parse import urlsplit

from fastapi import HTTPException
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from werkzeug.security import check_password_hash, generate_password_hash

from api.database import User, engine
from api.database.models import RecoveryRateLimit
from api.configs.logging import logError
from api.services import mail

GENERIC_RESET_MESSAGE = "Si un compte correspond à cette adresse, vous recevrez un lien de réinitialisation."
INVALID_RESET_MESSAGE = "Le lien est invalide ou a expiré. Demandez un nouveau lien."


def utc_now():
    """Date UTC naïve, cohérente avec les colonnes DATETIME du template."""
    return datetime.now(UTC).replace(tzinfo=None)


def consume_limit(
    db: Session, keys: list[tuple[str, int]], config, window_seconds: int | None = None
) -> bool:
    """Compteurs SQL atomiques communs à tous les workers, pour adresses connues ou non."""
    now = utc_now()
    cutoff = now - timedelta(
        seconds=window_seconds or config.PASSWORD_RESET_WINDOW_SECONDS
    )
    db.execute(
        delete(RecoveryRateLimit).where(
            RecoveryRateLimit.window_start < now - timedelta(days=2)
        )
    )
    allowed = True
    for raw, limit in keys:
        key = hmac.new(config.SECRET_KEY.encode(), raw.encode(), "sha256").hexdigest()
        if db.get(RecoveryRateLimit, key) is None:
            try:
                with db.begin_nested():
                    db.add(RecoveryRateLimit(key=key, window_start=now, attempts=0))
                    db.flush()
            except IntegrityError:
                pass  # Un autre worker a créé ce compteur ; l’incrément reste atomique.
        db.execute(
            update(RecoveryRateLimit)
            .where(
                RecoveryRateLimit.key == key, RecoveryRateLimit.window_start <= cutoff
            )
            .values(window_start=now, attempts=0)
        )
        result = db.execute(
            update(RecoveryRateLimit)
            .where(RecoveryRateLimit.key == key, RecoveryRateLimit.attempts < limit)
            .values(attempts=RecoveryRateLimit.attempts + 1)
        )
        if not result.rowcount:
            allowed = False
            break
    db.commit()
    return allowed


def verify_current_password(user: User, password: str):
    """Réauthentifier avant toute modification des identifiants du compte."""
    if not check_password_hash(user.password, password):
        raise HTTPException(400, "Le mot de passe actuel est incorrect.")


def change_password(db: Session, user: User, current: str, password: str):
    """Changer le hash et la version des sessions dans la même transaction."""
    verify_current_password(user, current)
    if check_password_hash(user.password, password):
        raise HTTPException(400, "Le nouveau mot de passe doit être différent.")
    result = db.execute(
        update(User)
        .where(User.id == user.id, User.auth_version == user.auth_version)
        .values(
            password=generate_password_hash(password),
            auth_version=User.auth_version + 1,
            password_reset_digest=None,
            password_reset_expires_at=None,
        )
    )
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "Le compte a changé. Reconnectez-vous puis réessayez.")
    db.commit()


def change_email(
    db: Session,
    user: User,
    email: str,
    current: str,
    verification_required: bool = False,
):
    """L’adresse de récupération exige le mot de passe et invalide les anciens liens et sessions."""
    verify_current_password(user, current)
    if user.email == email:
        raise HTTPException(400, "La nouvelle adresse doit être différente.")
    try:
        result = db.execute(
            update(User)
            .where(User.id == user.id, User.auth_version == user.auth_version)
            .values(
                email=email,
                email_verified_at=None,
                email_verification_required=verification_required,
                email_verification_digest=None,
                email_verification_expires_at=None,
                auth_version=User.auth_version + 1,
                password_reset_digest=None,
                password_reset_expires_at=None,
            )
        )
        if result.rowcount != 1:
            db.rollback()
            raise HTTPException(
                409, "Le compte a changé. Reconnectez-vous puis réessayez."
            )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(400, "Adresse e-mail indisponible.") from None


def queue_reset_email(email: str, language: str, config):
    """Tâche exécutée après la réponse publique ; aucun jeton dans la réponse ni les logs."""
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
            logError("FRONTEND_URL invalide pour la récupération de compte")
            return
        with Session(engine) as db:
            user = db.scalar(select(User).where(User.email == email).with_for_update())
            if user is None:
                return
            token = secrets.token_urlsafe(32)
            digest = sha256(token.encode()).hexdigest()
            user.password_reset_digest = digest
            user.password_reset_expires_at = utc_now() + timedelta(
                minutes=config.PASSWORD_RESET_EXPIRE_MINUTES
            )
            db.commit()
            # Le fragment n’est envoyé ni au serveur web ni dans l’en-tête Referer.
            link = f"{config.FRONTEND_URL.rstrip('/')}/reinitialiser-mot-de-passe#token={token}"
            sent = mail.send_password_reset(
                email,
                link,
                config.PASSWORD_RESET_EXPIRE_MINUTES,
                language,
                config.APP_NAME,
            )
            if not sent:
                db.execute(
                    update(User)
                    .where(User.id == user.id, User.password_reset_digest == digest)
                    .values(password_reset_digest=None, password_reset_expires_at=None)
                )
                db.commit()
    except Exception:
        # Ne pas inclure les arguments SMTP, l’adresse ni le jeton dans le diagnostic.
        logError("La demande de récupération n’a pas pu être traitée")


def reset_password(db: Session, token: str, password: str) -> str | None:
    """Consommer atomiquement un jeton valide ; deux requêtes concurrentes ne peuvent réussir."""
    digest = sha256(token.encode()).hexdigest()
    now = utc_now()
    user = db.scalar(
        select(User).where(
            User.password_reset_digest == digest, User.password_reset_expires_at > now
        )
    )
    if user is None:
        raise HTTPException(400, INVALID_RESET_MESSAGE)
    user_id, email, current_hash = user.id, user.email, user.password
    # Relâcher la lecture avant le calcul du hash ; l’UPDATE conditionnel décide seul de l’usage unique.
    db.rollback()
    if check_password_hash(current_hash, password):
        raise HTTPException(400, "Le nouveau mot de passe doit être différent.")
    result = db.execute(
        update(User)
        .where(
            User.id == user_id,
            User.password_reset_digest == digest,
            User.password_reset_expires_at > utc_now(),
        )
        .values(
            password=generate_password_hash(password),
            auth_version=User.auth_version + 1,
            password_reset_digest=None,
            password_reset_expires_at=None,
        )
    )
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(400, INVALID_RESET_MESSAGE)
    db.commit()
    return email
