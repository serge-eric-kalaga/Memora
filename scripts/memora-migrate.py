"""Migrate only Memora's private local databases, with SQLite backups and worker lock."""

import fcntl
import os
import sqlite3
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

root = Path(__file__).resolve().parents[1]
private = root / ".memora"
env = dict(os.environ)
for line in (private / "backend.env").read_text().splitlines():
    if line and not line.startswith("#"):
        key, value = line.split("=", 1)
        env[key] = value
expected = "sqlite:///" + str(private / "accounts.sqlite3")
if (
    env.get("DATABASE_URL") != expected
    or Path(env.get("MEMORA_DATA_DIR", "")).resolve() != private / "data"
):
    raise SystemExit(
        "Migration refusée : configuration différente des bases locales privées de ce projet."
    )
data = private / "data"
data.mkdir(exist_ok=True)
with (data / "worker.lock").open("a") as lock:
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise SystemExit(
            "Arrêtez l’API Memora avant cette migration ; aucune donnée modifiée."
        ) from None
    backup = (
        private
        / "backups"
        / (datetime.now(UTC).strftime("%Y%m%d-%H%M%S") + "-" + uuid4().hex[:6])
    )
    backup.mkdir(parents=True, mode=0o700)
    for source in (private / "accounts.sqlite3", data / "memora.sqlite3"):
        if source.is_file():
            with (
                sqlite3.connect(source.as_uri() + "?mode=ro", uri=True) as original,
                sqlite3.connect(backup / source.name) as copy,
            ):
                original.backup(copy)
    python = str(root / "backend/.venv/bin/python")
    subprocess.run(
        [python, "scripts/migrate.py"], cwd=root / "backend", env=env, check=True
    )
    subprocess.run(
        [python, "-c", "from api.memora import store; store.init()"],
        cwd=root / "backend",
        env=env,
        check=True,
    )
    subprocess.run(
        [python, str(root / "scripts/memora-bind-owners.py"), "--dry-run"],
        cwd=root,
        env=env,
        check=True,
    )
    subprocess.run(
        [python, str(root / "scripts/memora-bind-owners.py"), "--apply"],
        cwd=root,
        env=env,
        check=True,
    )
    print(
        "Migration locale terminée. Sauvegardes privées : "
        + str(backup.relative_to(root))
    )
    print("Les anciennes sessions doivent se reconnecter.")
