"""Opt-in import acceptance using a fresh random PostgreSQL DB and synthetic SQLite."""

import importlib.util
import json
import os
from pathlib import Path
import re
from urllib.parse import urlparse

import pytest


@pytest.mark.skipif(
    not os.environ.get("MEMORA_TEST_IMPORT_URL"),
    reason="Explicit isolated import database required",
)
def test_exact_import_and_refuse_nonempty_target(tmp_path, monkeypatch):
    from sqlalchemy import create_engine, text
    from api.database import Base
    from api.memora import store

    url = os.environ["MEMORA_TEST_IMPORT_URL"]
    assert re.fullmatch(r"memora_test_[0-9a-f]{16}", urlparse(url).path.lstrip("/"))
    accounts = tmp_path / "accounts.sqlite3"
    source = create_engine("sqlite:///" + str(accounts))
    Base.metadata.create_all(source)
    with source.begin() as c:
        c.execute(
            text("CREATE TABLE alembic_version(version_num VARCHAR(32) PRIMARY KEY)")
        )
        c.execute(text("INSERT INTO alembic_version VALUES('0007_account_uid')"))

    with source.begin() as c:
        table = Base.metadata.tables["user"]
        c.execute(
            table.insert().values(
                id=7,
                username="synthetic-user",
                password="synthetic-hash",
                telephone=None,
                account_uid="a" * 32,
            )
        )
    source.dispose()
    monkeypatch.delenv("MEMORA_DATABASE_URL", raising=False)
    monkeypatch.setattr(store, "ROOT", tmp_path / "data")
    store.init()
    with store.db() as c:
        c.execute(
            "INSERT INTO meetings VALUES(?,?,?)",
            (
                "b" * 32,
                7,
                json.dumps(
                    {
                        "title": "Réunion synthétique",
                        "owner_uid": "a" * 32,
                        "state": "ready",
                    }
                ),
            ),
        )
        c.execute(
            "INSERT INTO transcripts VALUES(?,?,?,?,?)",
            ("b" * 32, 1, '[{"text":"Bonjour — hello"}]', "test", 1234.123456789),
        )
        c.execute(
            "INSERT INTO reports VALUES(?,?,?,?,?)",
            ("report", "b" * 32, 1, '{"summary":[]}', 1234.123456789),
        )
        c.execute("INSERT INTO limits VALUES(?,?,?)", ("synthetic", 123, 2))
    root = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location(
        "memora_pg_import", root / "scripts/memora-import-postgres.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    proof = tmp_path / "proof.json"
    result = module.migrate(
        accounts,
        store.ROOT / "memora.sqlite3",
        url.replace("postgresql://", "postgresql+psycopg://"),
        proof,
        tmp_path / "backup",
    )
    assert result["tables"]["public.user"]["rows"] == 1
    assert result["tables"]["memora.meetings"]["rows"] == 1
    assert proof.exists()
    # Explicit IDs survive, and the next account must not collide after import.
    target = create_engine(
        url.replace("postgresql://", "postgresql+psycopg://"),
        connect_args={"options": "-c search_path=public"},
    )
    with target.begin() as c:
        user = Base.metadata.tables["user"]
        new_id = c.execute(
            user.insert()
            .values(
                username="synthetic-next",
                password="synthetic-next-hash",
                telephone=None,
                account_uid="c" * 32,
            )
            .returning(user.c.id)
        ).scalar_one()
        assert new_id == 8
    target.dispose()

    with pytest.raises(ValueError, match="not empty"):
        module.migrate(
            accounts,
            store.ROOT / "memora.sqlite3",
            url.replace("postgresql://", "postgresql+psycopg://"),
            tmp_path / "second-proof.json",
            tmp_path / "second-backup",
        )
    assert not (tmp_path / "second-proof.json").exists()
