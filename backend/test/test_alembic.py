"""Vérifier une future migration générée, appliquée et annulée sur une base jetable."""
from pathlib import Path
import io
import os
import shutil
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy_utils import create_database, drop_database
from api.database import Base


@pytest.fixture
def migration_engine(tmp_path):
    """Créer un schéma jetable indépendant de la base de l’application."""
    url = os.environ.get("TEST_MIGRATION_DATABASE_URL")
    if url:
        database_url = sa.engine.make_url(url).set(database=f"migration_{uuid4().hex}")
        create_database(database_url)
        engine = sa.create_engine(database_url)
    else:
        database_url = None
        engine = sa.create_engine(f"sqlite:///{tmp_path / 'migration.db'}")
    try:
        Base.metadata.create_all(engine)
        yield engine
    finally:
        engine.dispose()
        if database_url:
            drop_database(database_url)


def test_future_migration_generation_upgrade_and_downgrade(migration_engine, tmp_path):
    root = Path(__file__).resolve().parents[1]
    scripts = tmp_path / "migrations"
    shutil.copytree(root / "migrations", scripts)
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(scripts))
    initial_files = set((root / "migrations" / "versions").glob("*.py"))
    with migration_engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    target = sa.MetaData()
    for table in Base.metadata.sorted_tables:
        table.to_metadata(target)
    target.tables["user"].append_column(sa.Column("migration_probe", sa.String(80), nullable=True))
    config.attributes["target_metadata"] = target
    config.attributes["database_url"] = migration_engine.url

    with migration_engine.begin() as connection:
        connection.execute(sa.text("INSERT INTO user (username,password,telephone) VALUES ('existing','hash','123')"))
        config.attributes["connection"] = connection
        revision = command.revision(config, message="Future test column", autogenerate=True)
        assert revision and "migration_probe" in Path(revision.path).read_text()
        # L’autogénération produit un fichier, mais ne modifie pas le schéma.
        assert "migration_probe" not in {c["name"] for c in sa.inspect(connection).get_columns("user")}
        command.upgrade(config, "head")
        assert "migration_probe" in {c["name"] for c in sa.inspect(connection).get_columns("user")}
        command.check(config)
        assert connection.execute(sa.text("SELECT username,password,telephone FROM user")).one() == ("existing", "hash", "123")
        command.downgrade(config, "-1")
        assert "migration_probe" not in {c["name"] for c in sa.inspect(connection).get_columns("user")}
        assert connection.execute(sa.text("SELECT username FROM user")).scalar_one() == "existing"

    # La même future migration peut être rendue en SQL sans connexion.
    config.attributes.pop("connection")
    config.output_buffer = io.StringIO()
    command.upgrade(config, "head", sql=True)
    assert "migration_probe" in config.output_buffer.getvalue()
    assert set((root / "migrations" / "versions").glob("*.py")) == initial_files
