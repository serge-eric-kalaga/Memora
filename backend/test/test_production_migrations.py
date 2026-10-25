"""Vérifier le démarrage production sur base vide et la conservation des données."""

import os
from pathlib import Path
import subprocess
import sys

import sqlalchemy as sa
from alembic.config import Config
from alembic.script import ScriptDirectory


def test_production_migrations_on_empty_database_and_rerun(tmp_path):
    database = tmp_path / "production.db"
    environment = {**os.environ, "DATABASE_URL": f"sqlite:///{database}"}
    root = Path(__file__).resolve().parents[1]
    expected_revision = ScriptDirectory.from_config(Config(str(root / "alembic.ini"))).get_current_head()
    subprocess.run([sys.executable, "-m", "scripts.migrate"], cwd=root, env=environment, check=True)
    engine = sa.create_engine(environment["DATABASE_URL"])
    try:
        with engine.begin() as connection:
            assert connection.execute(sa.text("SELECT version_num FROM alembic_version")).scalar() == expected_revision
            connection.execute(sa.text("INSERT INTO user (username,password,telephone) VALUES ('production-probe','hash','123')"))
        subprocess.run([sys.executable, "-m", "scripts.migrate"], cwd=root, env=environment, check=True)
        with engine.connect() as connection:
            assert connection.execute(sa.text("SELECT username FROM user")).scalar() == "production-probe"
    finally:
        engine.dispose()
