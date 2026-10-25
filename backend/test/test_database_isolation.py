"""Empêcher les tests d’utiliser la connexion de développement par défaut."""

import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


@pytest.mark.parametrize("source", ["temporary", "explicit", "root-file"])
def test_test_database_never_falls_back_to_application_url(tmp_path, source):
    """Vérifier le choix de la connexion avant l’import du moteur, dans un processus neuf."""
    backend = Path(__file__).resolve().parents[1]
    package = tmp_path / "isolated" / "backend"
    tests = package / "test"
    tests.mkdir(parents=True)
    shutil.copyfile(backend / "test" / "__init__.py", tests / "__init__.py")
    environment = {
        **os.environ,
        "DATABASE_URL": "mysql+pymysql://invalid:invalid@invalid.local/unsafe_application",
        "REDIS_URL": "redis://invalid.local:6379",
        "REDIS_DATABASE_URL": "redis://invalid.local:6379",
        "CACHE_ENABLED": "true",
        "SECRET_KEY": "unsafe-app-secret",
        "JWT_SECRET": "unsafe-app-jwt",
        "PYTHONPATH": os.pathsep.join([str(package), str(backend)]),
    }
    environment.pop("TEST_DATABASE_URL", None)
    environment.pop("TEST_REDIS_URL", None)
    if source == "explicit":
        environment["TEST_DATABASE_URL"] = "sqlite:///:memory:"
    if source == "root-file":
        (package.parent / ".env.test").write_text('DATABASE_URL="sqlite:///:memory:"\n')
    code = "import test; from api.database import engine; assert engine.url.drivername == 'sqlite'; assert engine.url.database != 'unsafe_application'; import os; assert os.environ['CACHE_ENABLED'] == 'false'; assert os.environ['REDIS_URL'] == ''; assert os.environ['REDIS_DATABASE_URL'] == ''; assert os.environ['SECRET_KEY'] != 'unsafe-app-secret'; assert os.environ['JWT_SECRET'] != 'unsafe-app-jwt'"
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
