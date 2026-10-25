"""Prepare a synthetic local demonstration account without printing credentials."""

import json
import os
import secrets
import sys
from pathlib import Path

import httpx
from dotenv import dotenv_values
from sqlalchemy.orm import Session

root = Path(__file__).resolve().parents[1]
docker = root / ".memora/docker"
source = (
    docker / "backend.env"
    if (docker / "import-complete.json").exists()
    else root / ".memora/backend.env"
)
values = {k: v for k, v in dotenv_values(source).items() if v is not None}
if source.parent == docker:
    from sqlalchemy.engine import make_url

    compose = dotenv_values(docker / "compose.env")
    values["DATABASE_URL"] = (
        make_url(values["DATABASE_URL"])
        .set(host="127.0.0.1", port=int(compose.get("MEMORA_POSTGRES_PORT", "5433")))
        .render_as_string(hide_password=False)
    )
os.environ.update(values)
credentials = root / ".memora/demo.json"
if not credentials.exists():
    credentials.write_text(
        json.dumps(
            {
                "username": "demo_memora",
                "password": secrets.token_urlsafe(18),
                "email": "demo@example.org",
            }
        )
    )
    credentials.chmod(0o600)
account = json.loads(credentials.read_text())
with httpx.Client(
    base_url="http://127.0.0.1:8080", timeout=30, trust_env=False
) as client:
    login = client.post(
        "/api/auth/login",
        json={"username": account["username"], "password": account["password"]},
    )
    if login.status_code != 200:
        register = client.post("/api/auth/register", json={**account, "telephone": ""})
        register.raise_for_status()
        login = client.post(
            "/api/auth/login",
            json={"username": account["username"], "password": account["password"]},
        )
    login.raise_for_status()
# Admin is explicit only for the isolated demonstration identity.
sys.path.insert(0, str(root / "backend"))
from api.database import User, engine  # noqa: E402 - configuration privée avant import

with Session(engine) as db:
    user = User.get(db=db, username=account["username"])
    user.is_superuser = True
    db.commit()
print(
    "Compte de démonstration local prêt ; identifiants dans .memora/demo.json (non versionné)."
)
