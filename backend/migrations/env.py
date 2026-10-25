"""Migrations SQLAlchemy configurées par DATABASE_URL, sans démarrer l’API."""

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool
from api.database import Base

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name, disable_existing_loggers=False)
target_metadata = config.attributes.get("target_metadata", Base.metadata)


def database_url():
    """Lire l’URL sans l’inscrire dans alembic.ini ni interpoler les caractères %."""
    url = config.attributes.get("database_url") or os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL est requise pour exécuter Alembic")
    return url


def run_with_connection(connection):
    """Partager une connexion fournie ou ouverte par la CLI, avec détection des types."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        render_as_batch=connection.dialect.name == "sqlite",
    )
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    context.configure(url=database_url(), target_metadata=target_metadata,
                      literal_binds=True, dialect_opts={"paramstyle": "named"},
                      compare_type=True, compare_server_default=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    connection = config.attributes.get("connection")
    if connection is not None:
        run_with_connection(connection)
    else:
        engine = create_engine(database_url(), poolclass=pool.NullPool)
        try:
            with engine.connect() as connection:
                run_with_connection(connection)
        finally:
            engine.dispose()
