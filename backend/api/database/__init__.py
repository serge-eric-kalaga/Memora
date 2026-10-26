"""
Ce package contient la logique de la base de données de l'application.
"""

from api.configs.config import Setting
from sqlalchemy import create_engine, Engine
from sqlalchemy.orm import Session
from sqlalchemy_utils import create_database, database_exists


# Domain tables use schema memora; auth must not follow PostgreSQL's "$user"
# search_path when the database role is also named memora.
engine = create_engine(
    Setting.DATABASE_URL,
    connect_args={"options": "-c search_path=public"}
    if Setting.DATABASE_URL.startswith(("postgresql", "postgres:"))
    else {},
)



def get_db():
    with Session(engine, autoflush=True) as session:
        yield session


# -------------- Dans ce bloc sera importés tous les models

from .basetemplate import BaseTemplate as BaseTemplate
from .models import User as User, Base
# -------------------------------------------------


def init_database(engine: Engine):
    if not database_exists(engine.url):
        create_database(engine.url)

    Base.metadata.create_all(engine)
