"""Prepare private Docker configuration, preserving existing application identities."""

import json
import os
import secrets
import shlex
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / ".memora/docker"


def read_env(path):
    values = {}
    for line in path.read_text().splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, value = line.split("=", 1)
        parsed = shlex.split(value, comments=False)
        values[key] = parsed[0] if parsed else ""
    return values


def private_write(path, text):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        stream.write(text)
    path.chmod(0o600)


def main():
    source = ROOT / ".memora/backend.env"
    if not source.exists():
        raise SystemExit(
            "Configuration native absente : lancer d’abord python3 scripts/memora-env.py."
        )
    PRIVATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    PRIVATE.chmod(0o700)
    credentials = PRIVATE / "credentials.json"
    if credentials.exists():
        saved = json.loads(credentials.read_text())
    else:
        saved = {
            "postgres_password": secrets.token_urlsafe(36),
            "inference_token": secrets.token_urlsafe(48),
        }
        private_write(credentials, json.dumps(saved) + "\n")
    values = read_env(source)
    postgres = saved["postgres_password"]
    values.update(
        {
            "DATABASE_URL": f"postgresql+psycopg://memora:{postgres}@postgres:5432/memora",
            "MEMORA_DATABASE_URL": f"postgresql://memora:{postgres}@postgres:5432/memora",
            "MEMORA_INFERENCE_TOKEN": saved["inference_token"],
            "MEMORA_INFERENCE_URL": "http://host.docker.internal:8091",
            "MEMORA_OLLAMA_URL": "http://host.docker.internal:11434",
            "MEMORA_DATA_DIR": str(ROOT / ".memora/data"),
            "EMAIL_HOST": "mailpit",
            "EMAIL_PORT": "1025",
            "EMAIL_DOMAIN": "localhost",
            "MEMORA_SMTP_HOST": "mailpit",
            "MEMORA_SMTP_PORT": "1025",
            "MEMORA_SMTP_CAPTURE_ONLY": "1",
            "EMAIL_USERNAME": "",
            "EMAIL_PASSWORD": "",
            "INITIALISE_DATABASE": "false",
            "MEMORA_DOCKER_LOCAL": "1",
            "CACHE_ENABLED": "false",
            "RATE_LIMIT_ENABLED": "false",
            "FRONTEND_URL": "http://127.0.0.1:3000",
        }
    )
    if any("\n" in str(value) or "\r" in str(value) for value in values.values()):
        raise SystemExit(
            "Une valeur de configuration contient un saut de ligne ; aucune écriture env effectuée."
        )
    private_write(
        PRIVATE / "backend.env",
        "\n".join(f"{key}={value}" for key, value in values.items()) + "\n",
    )
    private_write(
        PRIVATE / "bridge.env",
        f"MEMORA_INFERENCE_TOKEN={shlex.quote(saved['inference_token'])}\n",
    )
    for directory in (
        ROOT / ".memora/data",
        ROOT / "backend/static/uploads",
        PRIVATE / "logs",
    ):
        directory.mkdir(parents=True, exist_ok=True)
    compose = {
        "MEMORA_POSTGRES_PASSWORD": postgres,
        "MEMORA_POSTGRES_PORT": "5433",
        "MEMORA_DOCKER_UID": str(os.getuid()),
        "MEMORA_DOCKER_GID": str(os.getgid()),
        "MEMORA_DATA_PATH": str(ROOT / ".memora/data"),
        "MEMORA_UPLOAD_PATH": str(ROOT / "backend/static/uploads"),
        "MEMORA_DOCKER_LOG_PATH": str(PRIVATE / "logs"),
    }
    private_write(
        PRIVATE / "compose.env",
        "\n".join(
            f"{key}={json.dumps(value).replace('$', '$$')}"
            for key, value in compose.items()
        )
        + "\n",
    )
    print("Configuration Docker privée prête (.memora/docker/, aucun secret affiché).")


if __name__ == "__main__":
    main()
