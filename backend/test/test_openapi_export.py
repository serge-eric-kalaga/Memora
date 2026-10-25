"""Le contrat doit être exportable hors ligne et signaler toute dérive sans écriture."""

from pathlib import Path
import json
import os
import subprocess
import sys


def test_offline_export_is_deterministic_and_check_rejects_drift(tmp_path):
    root = Path(__file__).resolve().parents[1]
    script = root / "scripts/export_openapi.py"
    output = tmp_path / "openapi.json"
    environment = {
        **os.environ,
        "DATABASE_URL": "mysql+pymysql://unavailable:unavailable@127.0.0.1:9/unavailable",
        "APP_NAME": "private-name-must-not-be-exported",
        "JWT_SECRET": "private-value-must-not-be-exported",
    }

    def run(*args):
        return subprocess.run(
            [sys.executable, str(script), "--output", str(output), *args],
            cwd=tmp_path,
            env=environment,
            capture_output=True,
            text=True,
            timeout=30,
        )

    assert run().returncode == 0
    first = output.read_bytes()
    assert b"private-name-must-not-be-exported" not in first
    assert b"private-value-must-not-be-exported" not in first
    schema = json.loads(first)
    assert schema["info"]["title"] == "Fullstack API"
    assert schema["paths"]["/api/auth/login"]["post"]["operationId"] == "authLogin"
    assert (
        "current_password" in schema["components"]["schemas"]["ChangeEmail"]["required"]
    )
    assert run().returncode == 0 and output.read_bytes() == first
    assert run("--check").returncode == 0
    output.write_text("{}\n")
    assert run("--check").returncode != 0
    assert output.read_text() == "{}\n"


def test_schema_factory_never_initializes_database(monkeypatch):
    from api import SETTINGS, createApp
    from api import database

    def forbidden(_):
        raise AssertionError("L’export ne doit pas initialiser la base")

    monkeypatch.setattr(database, "init_database", forbidden)
    config = SETTINGS()
    config.CACHE_ENABLED = False
    app = createApp(config, initialise_database=False)
    assert "/api/auth/login" in app.openapi()["paths"]
