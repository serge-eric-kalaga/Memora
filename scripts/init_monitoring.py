"""Préparer la configuration monitoring racine sans changer les secrets existants."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import secrets


def initialize(root: Path, production: bool = False) -> list[str]:
    """Ajouter seulement les variables manquantes ; refuser liens et valeurs vides requises."""
    if not (root / "docker-compose.monitoring.yml").is_file():
        raise ValueError("docker-compose.monitoring.yml est requis à la racine.")
    path = root / (".env.grafana.prod" if production else ".env.grafana")
    if path.is_symlink():
        raise ValueError(
            "Le fichier de monitoring ne doit pas être un lien symbolique."
        )
    existing = path.read_text() if path.exists() else ""
    for key in (
        "GF_SECURITY_ADMIN_USER",
        "GF_SECURITY_ADMIN_PASSWORD",
        "MYSQL_MONITORING_PASSWORD",
    ):
        match = re.search(rf"^\s*{key}\s*=([^\n]*)", existing, re.MULTILINE)
        if match and not match.group(1).strip().strip("\"'"):
            raise ValueError(
                "Une variable requise est vide ; renseigner le fichier racine."
            )
    keys = set(re.findall(r"^\s*([A-Z][A-Z0-9_]*)\s*=", existing, re.MULTILINE))
    defaults = {
        "GF_SECURITY_ADMIN_USER": "admin",
        "GF_SECURITY_ADMIN_PASSWORD": None,
        "MYSQL_MONITORING_PASSWORD": None,
        "MONITORING_ENV": "prod" if production else "dev",
        "BACKEND_LOG_SOURCE": "backend_logs" if production else "./backend/logs",
        "ALERTMANAGER_WEBHOOK_URL": "",
    }
    missing = {
        key: (secrets.token_hex(32) if value is None else value)
        for key, value in defaults.items()
        if key not in keys
    }
    if missing:
        # O_NOFOLLOW protège aussi contre un remplacement par lien entre le contrôle et l’ouverture.
        flags = os.O_WRONLY | os.O_APPEND | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path, flags, 0o600)
        with os.fdopen(descriptor, "a", encoding="utf-8") as output:
            if hasattr(os, "fchmod"):
                os.fchmod(output.fileno(), 0o600)
            output.write("\n# Monitoring — ne pas versionner.\n")
            for key, value in missing.items():
                output.write(f"{key}={json.dumps(value)}\n")
    return list(missing)


def main():
    """Configurer le fichier racine sans jamais afficher les secrets."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--production", action="store_true")
    parser.add_argument(
        "--directory", type=Path, default=Path(__file__).resolve().parents[1]
    )
    args = parser.parse_args()
    try:
        added = initialize(args.directory.resolve(), args.production)
    except (ValueError, OSError):
        raise SystemExit(
            "Configuration impossible ; vérifier le dossier et les permissions."
        ) from None
    name = ".env.grafana.prod" if args.production else ".env.grafana"
    print(f"{name} : {len(added)} variables ajoutées ; secrets existants conservés.")


if __name__ == "__main__":
    main()
