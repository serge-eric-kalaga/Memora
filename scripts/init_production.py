"""Préparer .env.prod à la racine, avec des secrets indépendants du développement."""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys

from init_project import configurations, project_identity, write_configurations


def production_configuration(name: str, slug: str, domain: str, email: str) -> dict[str, str]:
    """Construire une configuration HTTPS pour un nom DNS public, sans copier de secret local."""
    domain = domain.lower().strip()
    if len(domain) > 253 or not re.fullmatch(
        r"(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?",
        domain,
    ):
        raise ValueError("--domain doit être un nom DNS sans protocole, chemin ni port.")
    if len(email) > 254 or not re.fullmatch(
        r"[A-Za-z0-9_.+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+", email
    ):
        raise ValueError("L’adresse administrateur est invalide.")
    values = configurations(Path('.'), name, slug, email)[".env.dev"]
    for key in ("PMA_HOST", "PMA_PORT", "BACKEND_URL"):
        values.pop(key)
    values.update(
        COMPOSE_PROJECT_NAME=f"{slug}-prod",
        DOMAIN=domain,
        TLS_EMAIL=email,
        APP_ORIGIN=f"https://{domain}",
        FRONTEND_URL=f"https://{domain}",
        REDIS_PREFIX=f"{slug}:prod:v1",
        INITIALISE_DATABASE="false",
        SESSION_COOKIE_SECURE="true",
        ACCESS_TOKEN_EXPIRE_MINUTES="60",
    )
    return values


def main(argv: list[str] | None = None) -> int:
    """Créer uniquement .env.prod ; refuser tout écrasement, y compris un lien symbolique."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True)
    parser.add_argument("--slug")
    parser.add_argument("--domain", required=True)
    parser.add_argument("--admin-email", required=True)
    parser.add_argument("--directory", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)
    try:
        name, slug = project_identity(args.name, args.slug)
        root = args.directory.resolve()
        if not (root / "docker-compose.prod.yml").is_file():
            raise ValueError("Le dossier cible doit contenir docker-compose.prod.yml.")
        values = production_configuration(name, slug, args.domain, args.admin_email)
        write_configurations(root, {".env.prod": values})
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except FileExistsError:
        print(".env.prod existe déjà. Aucun fichier modifié.", file=sys.stderr)
        return 1
    except OSError:
        print("Impossible de créer .env.prod ; aucun secret affiché.", file=sys.stderr)
        return 1
    print(".env.prod créé à la racine (0600), avec de nouveaux secrets.")
    print("Configurer SMTP et le DNS, puis suivre la section Production du README.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
