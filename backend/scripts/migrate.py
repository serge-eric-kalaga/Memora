"""Préparer une base neuve puis appliquer les révisions, sans démarrer l’API."""

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from api.database import Base, engine


def migrate():
    """Créer le schéma uniquement si la base est vide ; migrer les bases existantes avec Alembic."""
    config = Config("alembic.ini")
    with engine.begin() as connection:
        # Les premières révisions du template supposent que les tables initiales existent.
        # Aucune création ORM sur une base contenant déjà des tables métier.
        tables = set(inspect(connection).get_table_names()) - {"alembic_version"}
        if not tables:
            Base.metadata.create_all(connection)
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
        command.check(config)


if __name__ == "__main__":
    migrate()
