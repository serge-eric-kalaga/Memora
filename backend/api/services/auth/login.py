from datetime import UTC, datetime
from api.database.models import User
from api.schemas.user import LoginModel
from werkzeug.exceptions import Unauthorized
from api.services.jwt import create_token
from werkzeug.security import check_password_hash


def login(db, credentials: LoginModel, config=None) -> str:
    user_exist: User = User.getOrNone(db=db, username=credentials.username)

    if user_exist is None or not check_password_hash(
        user_exist.password, credentials.password
    ):
        raise Unauthorized(description="Username / Mot de passe incorrest !")

    from api.services.email_verification import require_verified_email
    from api.configs.config import Setting

    require_verified_email(user_exist, config or Setting)

    # Horodatage UTC enregistré uniquement après validation des identifiants.
    user_exist.last_login_at = datetime.now(UTC).replace(tzinfo=None)
    db.commit()
    token = create_token(
        data={
            "username": credentials.username,
            "sub": str(user_exist.id),
            "auth_version": user_exist.auth_version,
            "account_uid": user_exist.account_uid,
        }
    )
    return token


def loginDoc(db, credentials: LoginModel, config=None) -> dict[str, str]:
    token = login(db, credentials, config)
    result = {"access_token": token, "token_type": "bearer"}
    return result
