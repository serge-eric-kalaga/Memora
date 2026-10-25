"""Initialiser un projet cloné : identité et configurations racine, sans écrasement."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import secrets
import sys
import unicodedata

ENV_FILES = (".env.dev", ".env.test", ".env.grafana")


def project_identity(name: str, slug: str | None = None) -> tuple[str, str]:
    """Valider le nom affiché et construire un identifiant compatible Compose/MySQL."""
    name = name.strip()
    if not 1 <= len(name) <= 80 or any(
        not (
            character.isalnum()
            or character in " -_.&'()"
            or unicodedata.category(character).startswith("M")
        )
        for character in name
    ):
        raise ValueError(
            "Le nom doit contenir 1 à 80 caractères : lettres, chiffres, espaces ou -_.&'()."
        )
    if slug is None:
        ascii_name = (
            unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
        )
        slug = re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")
    if not re.fullmatch(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*", slug or "") or len(slug) > 48:
        raise ValueError(
            "Choisir --slug avec 1 à 48 lettres minuscules, chiffres ou tirets, commençant par une lettre."
        )
    return name, slug


def validate_directory(directory: Path) -> Path:
    """Limiter l’initialisation à une racine du template et refuser toute configuration existante."""
    directory = directory.resolve()
    if not (directory / "docker-compose.yml").is_file() or not all(
        (directory / child).is_dir() for child in ("backend", "frontend")
    ):
        raise ValueError(
            "Le dossier cible doit contenir docker-compose.yml, backend/ et frontend/."
        )
    existing = [name for name in ENV_FILES if os.path.lexists(directory / name)]
    if existing:
        raise ValueError(
            "Configuration déjà présente : "
            + ", ".join(existing)
            + ". Aucun fichier n’a été modifié."
        )
    return directory


def configurations(
    directory: Path, name: str, slug: str, admin_email: str
) -> dict[str, dict[str, str]]:
    """Générer des secrets indépendants, avec des identifiants cohérents entre services."""
    database = slug.replace("-", "_")
    database_password = secrets.token_hex(32)
    broker_password = secrets.token_hex(32)
    dev = {
        "COMPOSE_PROJECT_NAME": slug,
        "APP_NAME": name,
        "NEXT_PUBLIC_APP_NAME": name,
        "ADMINS_EMAIL": admin_email,
        "SECRET_KEY": secrets.token_hex(32),
        "JWT_SECRET": secrets.token_hex(32),
        "ALGORITHM": "HS256",
        "ACCESS_TOKEN_EXPIRE_MINUTES": "480",
        "MYSQL_ROOT_PASSWORD": secrets.token_hex(32),
        "MYSQL_DATABASE": database,
        "MYSQL_USER": "application",
        "MYSQL_PASSWORD": database_password,
        "DATABASE_URL": f"mysql+pymysql://application:{database_password}@mysql:3306/{database}",
        "PMA_HOST": "mysql",
        "PMA_PORT": "3306",
        "REDIS_URL": "redis://redis:6379/0",
        "REDIS_PREFIX": f"{slug}:dev:v1",
        "RATE_LIMIT_ENABLED": "true",
        "RATE_LIMIT_GLOBAL_LIMIT": "300",
        "RATE_LIMIT_GLOBAL_WINDOW_SECONDS": "60",
        "RATE_LIMIT_FAIL_CLOSED": "true",
        "CACHE_ENABLED": "true",
        "CACHE_TTL_SECONDS": "60",
        "CELERY_BROKER_URL": f"amqp://worker:{broker_password}@task-broker:5672//",
        "CELERY_RESULT_BACKEND": "redis://redis:6379/1",
        "RABBITMQ_DEFAULT_USER": "worker",
        "RABBITMQ_DEFAULT_PASS": broker_password,
        "FRONTEND_URL": "http://localhost:3000",
        "BACKEND_URL": "http://127.0.0.1:8080",
        "APP_ORIGIN": "http://localhost:3000",
        "STORAGE_BACKEND": "local",
        "S3_BUCKET": "",
        "S3_ENDPOINT_URL": "",
        "S3_REGION": "us-east-1",
        "S3_ACCESS_KEY_ID": "",
        "S3_SECRET_ACCESS_KEY": "",
        "S3_ADDRESSING_STYLE": "auto",
        "PROFILE_PHOTO_DIR": "static/uploads/profile_photos",
        "PROFILE_PHOTO_MAX_BYTES": "5242880",
        "PROFILE_PHOTO_MAX_PIXELS": "16000000",
        "EMAIL_HOST": "",
        "EMAIL_PORT": "587",
        "EMAIL_DOMAIN": "example.com",
        "EMAIL_USERNAME": "",
        "EMAIL_PASSWORD": "",
        "EMAIL_VERIFICATION_ENABLED": "false",
        "EMAIL_VERIFICATION_EXPIRE_MINUTES": "60",
        "EMAIL_VERIFICATION_WINDOW_SECONDS": "900",
        "EMAIL_VERIFICATION_EMAIL_LIMIT": "3",
        "EMAIL_VERIFICATION_IP_LIMIT": "30",
        "PASSWORD_RESET_EXPIRE_MINUTES": "30",
        "PASSWORD_RESET_WINDOW_SECONDS": "900",
        "PASSWORD_RESET_EMAIL_LIMIT": "3",
        "PASSWORD_RESET_IP_LIMIT": "30",
    }
    tests = {
        "APP_NAME": f"{name} Tests",
        "ADMINS_EMAIL": "tests@example.com",
        "SECRET_KEY": secrets.token_hex(32),
        "JWT_SECRET": secrets.token_hex(32),
        "ALGORITHM": "HS256",
        "ACCESS_TOKEN_EXPIRE_MINUTES": "15",
        "DATABASE_URL": "sqlite:///.test.db",
        "CACHE_ENABLED": "false",
        "RATE_LIMIT_ENABLED": "false",
        "REDIS_URL": "",
        "REDIS_DATABASE_URL": "",
        "REDIS_PREFIX": f"{slug}:test:v1",
        "CELERY_BROKER_URL": "memory://",
        "CELERY_RESULT_BACKEND": "cache+memory://",
        "EMAIL_VERIFICATION_ENABLED": "false",
        "EMAIL_HOST": "127.0.0.1",
        "EMAIL_PORT": "9",
        "EMAIL_DOMAIN": "example.com",
        "EMAIL_USERNAME": "tests",
        "EMAIL_PASSWORD": "tests-only",
    }
    grafana = {
        "GF_SECURITY_ADMIN_USER": "admin",
        "GF_SECURITY_ADMIN_PASSWORD": secrets.token_hex(32),
        "MYSQL_MONITORING_PASSWORD": secrets.token_hex(32),
        "MONITORING_ENV": "dev",
        "BACKEND_LOG_SOURCE": "./backend/logs",
        "ALERTMANAGER_WEBHOOK_URL": "",
    }
    return dict(zip(ENV_FILES, (dev, tests, grafana)))


def write_configurations(directory: Path, configs: dict[str, dict[str, str]]):
    """Créer les fichiers en mode 0600 ; annuler les créations si une écriture échoue."""
    created = []
    try:
        for name, values in configs.items():
            path = directory / name
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            created.append(path)
            with os.fdopen(descriptor, "w", encoding="utf-8") as output:
                output.write("# Configuration locale — ne pas versionner.\n")
                for key, value in values.items():
                    # Les valeurs générées ne contiennent pas d’interpolation $ ni de retour à la ligne.
                    output.write(f"{key}={json.dumps(value, ensure_ascii=False)}\n")
                output.flush()
                os.fsync(output.fileno())
    except OSError:
        for path in created:
            path.unlink(missing_ok=True)
        raise


def main(argv: list[str] | None = None) -> int:
    """Point d’entrée CLI ; ne jamais afficher de secret, même lors d’un échec."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", help="Nom affiché dans l’API et le frontend.")
    parser.add_argument(
        "--slug", help="Identifiant technique, par exemple ma-boutique."
    )
    parser.add_argument(
        "--admin-email",
        default="admin@example.com",
        help="Destinataire des alertes administrateur.",
    )
    parser.add_argument(
        "--directory",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Racine du template à initialiser.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Afficher les fichiers prévus sans générer ni écrire de secrets.",
    )
    args = parser.parse_args(argv)
    if args.name is None:
        if not sys.stdin.isatty():
            parser.error("--name est requis sans terminal interactif.")
        try:
            args.name = input("Nom du projet : ")
        except (EOFError, KeyboardInterrupt):
            print("\nInitialisation annulée.", file=sys.stderr)
            return 1
    try:
        name, slug = project_identity(args.name, args.slug)
        if len(args.admin_email) > 254 or not re.fullmatch(
            r"[A-Za-z0-9_.+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+", args.admin_email
        ):
            raise ValueError("L’adresse administrateur est invalide.")
        directory = validate_directory(args.directory)
        if args.dry_run:
            print(
                f"Projet : {name} ({slug})\nFichiers à créer : {', '.join(ENV_FILES)}\nAucun fichier créé."
            )
            return 0
        write_configurations(
            directory, configurations(directory, name, slug, args.admin_email)
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except OSError:
        print(
            "Impossible de créer la configuration. Les créations de cette exécution ont été annulées.",
            file=sys.stderr,
        )
        return 1
    print(f"Projet initialisé : {name} ({slug}).")
    print("Fichiers créés à la racine : " + ", ".join(ENV_FILES) + ".")
    print("Secrets générés et enregistrés dans les fichiers privés, sans affichage.")
    print("Renseignez SMTP pour les e-mails, puis lancez :")
    print("docker compose --env-file .env.dev up -d --build")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
