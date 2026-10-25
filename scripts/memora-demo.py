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
os.environ.update(
    {
        k: v
        for k, v in dotenv_values(root / ".memora/backend.env").items()
        if v is not None
    }
)
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
from api.database import User, engine

with Session(engine) as db:
    user = User.get(db=db, username=account["username"])
    user.is_superuser = True
    db.commit()
print(
    "Compte de démonstration local prêt ; identifiants dans .memora/demo.json (non versionné)."
)
