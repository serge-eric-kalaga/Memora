"""Vérifier les migrations publiées sur une base jetable, sans créer le schéma courant."""

from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4
import os

import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy_utils import create_database, drop_database


def check_migrations():
    """Partir du schéma antérieur à Alembic, migrer, comparer et tester le retour d’une révision."""
    root = Path(__file__).resolve().parents[1]
    server_url = os.environ.get("TEST_MIGRATION_DATABASE_URL")
    with TemporaryDirectory(prefix="template-migrations-") as directory:
        url = (
            sa.engine.make_url(server_url).set(database=f"ci_migrations_{uuid4().hex}")
            if server_url
            else sa.engine.make_url(f"sqlite:///{directory}/migrations.db")
        )
        if server_url:
            create_database(url)
        engine = sa.create_engine(url)
        try:
            # Baseline figée : ne pas utiliser Base.metadata.create_all ici.
            # Sinon un nouveau champ sans migration serait créé avant alembic check.
            legacy = sa.MetaData()
            user = sa.Table(
                "user",
                legacy,
                sa.Column(
                    "id", sa.Integer(), primary_key=True, autoincrement=True, index=True
                ),
                sa.Column("username", sa.String(255), nullable=False, unique=True),
                sa.Column("telephone", sa.String(255), nullable=True),
                sa.Column("password", sa.String(255), nullable=False),
                sa.Column("profile_photo", sa.String(255), nullable=True),
                sa.Column(
                    "date_creation",
                    sa.DateTime(),
                    server_default=sa.func.now(),
                    nullable=False,
                ),
                sa.Column("date_modification", sa.DateTime(), nullable=True),
            )
            legacy.create_all(engine)
            config = Config(str(root / "alembic.ini"))
            config.set_main_option("script_location", str(root / "migrations"))
            scripts = ScriptDirectory.from_config(config)
            head = scripts.get_revision(scripts.get_current_head())
            # A security boundary must remain installed. Exercise the preceding
            # reversible migration before installing an irreversible current head.
            roundtrip = (
                head.down_revision
                if getattr(head.module, "irreversible_security", False)
                else head.revision
            )
            with engine.begin() as connection:
                connection.execute(
                    user.insert().values(
                        username="migration_probe",
                        password="preserved-hash",
                        telephone="123",
                    )
                )
                config.attributes["connection"] = connection
                if roundtrip:
                    command.upgrade(config, roundtrip)
                    command.downgrade(config, "-1")
                    command.upgrade(config, roundtrip)
                command.upgrade(config, "head")
                command.check(config)
                row = connection.execute(
                    sa.select(user.c.username, user.c.password, user.c.telephone)
                ).one()
                if row != ("migration_probe", "preserved-hash", "123"):
                    raise RuntimeError(
                        "Les migrations ont modifié les données existantes"
                    )
            print(
                f"Migrations {engine.dialect.name} OK : head {head.revision}, "
                f"upgrade/check, roundtrip {roundtrip or 'aucun prédécesseur réversible'} "
                "et données conservées."
            )
            return {"head": head.revision, "roundtrip": roundtrip}
        finally:
            engine.dispose()
            if server_url:
                drop_database(url)


if __name__ == "__main__":
    check_migrations()
