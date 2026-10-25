from datetime import UTC, datetime, timedelta
from api.configs.config import Setting
from jose import jwt, JWTError
from werkzeug.exceptions import Forbidden
from fastapi.security import OAuth2PasswordBearer
from fastapi import Depends, Request, HTTPException
from typing import Annotated
from api.database import get_db, User, Session

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/doc-login")


def create_token(data: dict, expire_delta: timedelta | None = None):
    """Signer une copie des données avec une expiration UTC explicite ou celle configurée."""
    to_encode = data.copy()
    # Internal helper callers may provide only username. Login always supplies the
    # UID from the actual credential-checked account to avoid incarnation races.
    if "account_uid" not in to_encode and isinstance(to_encode.get("username"), str):
        from api.database import engine

        with Session(engine) as session:
            account = User.getOrNone(db=session, username=to_encode["username"])
            if account is not None:
                to_encode["account_uid"] = account.account_uid
    if expire_delta:
        expire = datetime.now(UTC) + expire_delta
    else:
        expire = datetime.now(UTC) + timedelta(
            minutes=Setting.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, Setting.JWT_SECRET, algorithm=Setting.ALGORITHM)
    return encoded_jwt


def decode_token(token: str):
    """Vérifier la signature et l’expiration du JWT ; retourner None si le jeton est invalide."""
    try:
        payload = jwt.decode(token, Setting.JWT_SECRET, algorithms=[Setting.ALGORITHM])
        return payload
    except JWTError:
        return None


def getPayload(
    request: Request,
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)],
):
    """Vérifier le JWT et la version des identifiants pour révoquer les anciennes sessions."""
    payload = decode_token(token)
    if not payload or not isinstance(payload.get("username"), str):
        raise Forbidden("Token Invalide")
    user = User.getOrNone(db=db, username=payload["username"])
    if user is None or payload.get("auth_version", 0) != user.auth_version:
        raise Forbidden("Session expirée")
    # A deleted account must never regain sessions when SQLite reuses its ID.
    # Legacy JWTs deliberately expire: reconnect after the account UID migration.
    if not payload.get("account_uid") or payload["account_uid"] != user.account_uid:
        raise Forbidden("Session expirée ; reconnectez-vous")
    if "sub" in payload and payload["sub"] != str(user.id):
        raise Forbidden("Session expirée")
    from api.services.email_verification import require_verified_email

    require_verified_email(user, request.app.state.config)
    return payload


def isAdmin(
    token: Annotated[dict, Depends(getPayload)],
    db: Annotated[Session, Depends(get_db)],
):
    """Compatibilité : vérifier le rôle admin en base, jamais un claim fourni par le JWT."""
    from api.services.authorization import has_role

    user = User.get(db=db, username=token["username"])
    if not has_role(db, user, "admin"):
        raise HTTPException(403, "Privilèges insuffisants")
    return token
