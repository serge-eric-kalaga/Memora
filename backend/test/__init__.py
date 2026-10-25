"""Isoler la suite de tests avant tout import de l’application et de son moteur SQL."""

import os
import secrets
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from dotenv import dotenv_values, load_dotenv

# Ne jamais réutiliser implicitement DATABASE_URL du conteneur applicatif.
# Un serveur de test est choisi explicitement ; sinon SQLite est créé puis supprimé.
_test_env = Path(__file__).resolve().parents[2] / ".env.test"
_explicit_test_url = os.environ.get("TEST_DATABASE_URL")
_test_values = dotenv_values(_test_env) if _test_env.is_file() else {}
if _test_env.is_file():
    load_dotenv(_test_env, override=True)

_test_database_directory = None
_test_url = _explicit_test_url or _test_values.get("DATABASE_URL")
if not _test_url:
    _test_database_directory = TemporaryDirectory(prefix="fullstack-tests-")
    _test_url = f"sqlite:///{Path(_test_database_directory.name) / 'tests.db'}"
os.environ["DATABASE_URL"] = _test_url
# Les jetons des comptes de test ne doivent pas être signés avec les clés de l’application.
os.environ["SECRET_KEY"] = _test_values.get("SECRET_KEY") or secrets.token_hex(32)
os.environ["JWT_SECRET"] = _test_values.get("JWT_SECRET") or secrets.token_hex(32)


# Aucun test unitaire ne publie implicitement vers le broker applicatif.
os.environ["CELERY_BROKER_URL"] = "memory://"
os.environ["CELERY_RESULT_BACKEND"] = "cache+memory://"

# Le cache applicatif n’est jamais utilisé par défaut. Les fixtures Redis
# n’activent que TEST_REDIS_URL, sur un préfixe propre à cette session de tests.
os.environ["CACHE_ENABLED"] = "false"
os.environ["RATE_LIMIT_ENABLED"] = "false"
os.environ["REDIS_URL"] = os.environ.get("TEST_REDIS_URL", "")
os.environ["REDIS_DATABASE_URL"] = ""
os.environ["REDIS_PREFIX"] = f"fullstack-tests:{uuid4().hex}"


# Préparer les répertoires relatifs des tests sans tronquer un journal existant.
_log_file = Path.cwd() / "logs" / "app.log"
_log_file.parent.mkdir(parents=True, exist_ok=True)
_log_file.touch(exist_ok=True)
(Path.cwd() / "static" / "fake").mkdir(parents=True, exist_ok=True)
