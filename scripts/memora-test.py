"""Run backend tests with disposable databases/storage and no running worker."""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix="memora-test-") as folder:
    env = dict(os.environ)
    env.update(
        APP_NAME="Memora test",
        ADMINS_EMAIL="test@example.org",
        SECRET_KEY="isolated-test-only",
        JWT_SECRET="isolated-test-jwt-only",
        ALGORITHM="HS256",
        DATABASE_URL="sqlite:///" + folder + "/accounts.sqlite3",
        TEST_DATABASE_URL="sqlite:///" + folder + "/accounts.sqlite3",
        INITIALISE_DATABASE="false",
        CACHE_ENABLED="false",
        RATE_LIMIT_ENABLED="false",
        MEMORA_DATA_DIR=folder + "/data",
        MEMORA_DISABLE_WORKER="1",
        EMAIL_HOST="127.0.0.1",
        EMAIL_PORT="1025",
        EMAIL_DOMAIN="memora@localhost",
    )
    result = subprocess.run(
        [
            str(root / "backend/.venv/bin/python"),
            "-m",
            "pytest",
            *(sys.argv[1:] or ["test", "-q"]),
        ],
        cwd=root / "backend",
        env=env,
        check=False,
    )
    raise SystemExit(result.returncode)
