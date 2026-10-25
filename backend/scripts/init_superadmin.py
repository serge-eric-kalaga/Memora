"""Initialiser explicitement un super administrateur depuis un terminal serveur."""

import argparse
from datetime import UTC, datetime
from getpass import getpass
import sys
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from werkzeug.security import generate_password_hash
from api.database import User, engine
from api.schemas.user import CreateUserModel
from api.services.authorization import create_permission


def initialize(
    db: Session,
    *,
    username: str,
    email: str | None = None,
    password: str | None = None,
    promote_existing: bool = False,
) -> User:
    """Créer ou promouvoir explicitement ; ne jamais réinitialiser un mot de passe existant."""
    user = User.getOrNone(db=db, username=username)
    if user is not None and not user.is_superuser and not promote_existing:
        raise ValueError(
            "Compte existant : utiliser --promote-existing pour confirmer la promotion."
        )
    if user is None:
        data = CreateUserModel(username=username, email=email, password=password or "")
        user = User(
            username=data.username,
            telephone=None,
            password=generate_password_hash(data.password),
        )
        user.email = str(data.email).lower() if data.email else None
        user.email_verified_at = datetime.now(UTC) if user.email else None
        user.email_verification_required = False
        db.add(user)
    user.is_superuser = True
    for permission in ("access.read", "access.manage", "users.create"):
        create_permission(db, permission)
    db.flush()
    return user


def main():
    """Demander le secret sans affichage ; stdin sert aux automatisations sécurisées."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--username", required=True)
    parser.add_argument("--email")
    parser.add_argument("--promote-existing", action="store_true")
    parser.add_argument("--password-stdin", action="store_true")
    args = parser.parse_args()
    try:
        with Session(engine) as db:
            existing = User.getOrNone(db=db, username=args.username)
            password = None
            if existing is None:
                if args.password_stdin:
                    password = sys.stdin.readline().rstrip("\r\n")
                else:
                    password = getpass("Mot de passe du super administrateur : ")
                    if password != getpass("Confirmer le mot de passe : "):
                        raise ValueError("Les mots de passe diffèrent.")
            initialize(
                db,
                username=args.username,
                email=args.email,
                password=password,
                promote_existing=args.promote_existing,
            )
            db.commit()
    except ValidationError:
        raise SystemExit(
            "Identifiant, adresse e-mail ou mot de passe invalide."
        ) from None
    except ValueError as error:
        raise SystemExit(str(error)) from None
    except IntegrityError:
        raise SystemExit(
            "Identifiant ou adresse e-mail indisponible ; aucune modification validée."
        ) from None
    print("Super administrateur initialisé ; mot de passe existant conservé.")


if __name__ == "__main__":
    main()
