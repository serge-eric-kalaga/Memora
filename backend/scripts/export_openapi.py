"""Exporter un contrat OpenAPI déterministe, sans SQL, Redis, SMTP ni serveur en cours."""

import argparse
import json
import os
from pathlib import Path


def export_openapi(output: Path, *, check: bool = False):
    """Construire les routes sans initialiser la base et comparer ou écrire le schéma public."""
    # Configuration propre à ce processus : aucune valeur privée ne doit influencer l’export.
    os.environ.update(
        {
            "APP_NAME": "Fullstack API",
            "ADMINS_EMAIL": "schema@example.com",
            "SECRET_KEY": "schema-export-only",
            "JWT_SECRET": "schema-export-only",
            "ALGORITHM": "HS256",
            "DATABASE_URL": "sqlite://",
            "CACHE_ENABLED": "false",
            "REDIS_URL": "",
            "REDIS_DATABASE_URL": "",
        }
    )
    from api import SETTINGS, createApp

    app = createApp(SETTINGS(), initialise_database=False)
    content = (
        json.dumps(app.openapi(), ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    )
    if check:
        if not output.exists() or output.read_text(encoding="utf-8") != content:
            raise SystemExit(
                "OpenAPI obsolète : exécutez python scripts/export_openapi.py puis régénérez le client frontend."
            )
        print("Export OpenAPI à jour.")
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content, encoding="utf-8")
        print(f"Contrat OpenAPI exporté : {output.name}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Échouer si le fichier versionné diffère, sans le modifier.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "openapi.json",
    )
    args = parser.parse_args()
    export_openapi(args.output, check=args.check)
