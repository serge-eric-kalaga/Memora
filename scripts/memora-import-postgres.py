"""Offline, transactional SQLite -> PostgreSQL import with exact row verification.

No source is changed. Private snapshots and fingerprints remain under .memora.
Run only after stopping Memora; an existing non-empty target is never replaced.
"""

import argparse
from datetime import UTC, datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def fingerprint(rows):
    def normalized(value):
        if isinstance(value, datetime):
            return value.isoformat(sep=" ")
        if isinstance(value, bool):
            return int(value)
        return value

    values = [tuple(normalized(v) for v in row) for row in rows]
    return hashlib.sha256(
        json.dumps(sorted(values, key=repr), ensure_ascii=False, default=str).encode()
    ).hexdigest()


def migrate(accounts, domain, url, proof, backup_dir):
    """Reusable for synthetic fixtures. URL must identify the intended local DB."""
    from sqlalchemy import MetaData, create_engine, inspect, select, text
    from sqlalchemy.engine import make_url
    from alembic import command
    from alembic.config import Config

    target_url = make_url(url)
    if target_url.get_backend_name() != "postgresql" or target_url.host not in (
        "127.0.0.1",
        "localhost",
        "postgres",
    ):
        raise ValueError("Only the local PostgreSQL target is allowed")
    if target_url.database != "memora" and not target_url.database.startswith(
        "memora_test_"
    ):
        raise ValueError("Unexpected target database")
    backup_dir.mkdir(parents=True, mode=0o700)
    for source in (accounts, domain):
        with sqlite3.connect(source.as_uri() + "?mode=ro", uri=True) as original:
            if original.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise ValueError("Source integrity failed")
            with sqlite3.connect(backup_dir / source.name) as copy:
                original.backup(copy)
        (backup_dir / source.name).chmod(0o600)

    # Import model definitions only after the CLI has installed the target env.
    from api.database import Base
    from api.memora.postgres import Connection, DOMAIN_LOCK

    domain_schema = Connection(url.replace("postgresql+psycopg://", "postgresql://"))
    try:
        domain_schema.initialize_schema(ROOT / "backend/api/memora/migrations")
        domain_schema.commit()
    finally:
        domain_schema.close()
    engine = create_engine(
        target_url, connect_args={"options": "-c search_path=public"}
    )
    sources = {
        "public": create_engine("sqlite:///" + str(backup_dir / accounts.name)),
        "memora": create_engine("sqlite:///" + str(backup_dir / domain.name)),
    }
    result = {
        "tables": {},
        "audio": {},
        "target": target_url.database,
        "import_id": uuid4().hex,
    }
    try:
        with engine.begin() as target:
            target.execute(
                text("SELECT pg_advisory_xact_lock(:key)"), {"key": DOMAIN_LOCK}
            )
            # Source table layout is trusted repository schema, not input SQL.
            for schema in ("public", "memora"):
                for table in inspect(target).get_table_names(schema=schema):
                    if schema == "memora" and table == "schema_version":
                        continue
                    count = target.exec_driver_sql(
                        f'SELECT count(*) FROM "{schema}"."{table}"'
                    ).scalar_one()
                    if count:
                        raise ValueError("Target is not empty; import refused")
            Base.metadata.create_all(target)
            config = Config(str(ROOT / "backend/alembic.ini"))
            config.set_main_option("script_location", str(ROOT / "backend/migrations"))
            config.attributes["connection"] = target
            command.upgrade(config, "head")
            metadata = MetaData()
            metadata.reflect(target, schema="public")
            domain_metadata = MetaData()
            domain_metadata.reflect(target, schema="memora")
            for schema, source_engine in sources.items():
                source_meta = MetaData()
                source_meta.reflect(source_engine)
                with source_engine.connect() as source:
                    for source_table in source_meta.sorted_tables:
                        name = source_table.name
                        if name == "alembic_version":
                            original = source.execute(select(source_table)).all()
                            destination = metadata.tables["public.alembic_version"]
                            selected = target.execute(select(destination)).all()
                            if fingerprint(original) != fingerprint(selected):
                                raise ValueError(
                                    "Source migration version differs; upgrade bootstrap first"
                                )
                            result["tables"]["public.alembic_version"] = {
                                "rows": len(original),
                                "sha256": fingerprint(selected),
                            }
                            continue
                        dest_meta = metadata if schema == "public" else domain_metadata
                        destination = dest_meta.tables.get(f"{schema}.{name}")
                        if destination is None:
                            raise ValueError(
                                f"Unknown source table {schema}.{name}; targets={list(dest_meta.tables)}; import refused"
                            )
                        columns = [c.name for c in source_table.columns]
                        if set(columns) != set(destination.columns.keys()):
                            raise ValueError("Column layout differs; import refused")
                        rows = source.execute(select(source_table)).mappings().all()
                        target.execute(destination.delete())
                        if rows:
                            from sqlalchemy import Boolean

                            records = [dict(row) for row in rows]
                            for record in records:
                                for column in destination.columns:
                                    if (
                                        isinstance(column.type, Boolean)
                                        and record[column.name] is not None
                                    ):
                                        record[column.name] = bool(record[column.name])
                            target.execute(destination.insert(), records)
                        selected = target.execute(
                            select(*(destination.c[c] for c in columns))
                        ).all()
                        original = [tuple(row[c] for c in columns) for row in rows]
                        if fingerprint(original) != fingerprint(selected):
                            raise ValueError(
                                "Row fingerprint mismatch; transaction rolled back"
                            )
                        result["tables"][f"{schema}.{name}"] = {
                            "rows": len(rows),
                            "sha256": fingerprint(selected),
                        }
            # Preserve explicit account IDs while advancing sequences for new accounts.
            for table in metadata.sorted_tables:
                for column in table.primary_key.columns:
                    if column.autoincrement is True or (
                        column.autoincrement == "auto"
                        and len(table.primary_key.columns) == 1
                    ):
                        from sqlalchemy import Integer

                        if not isinstance(column.type, Integer):
                            continue
                        sequence = target.execute(
                            text("SELECT pg_get_serial_sequence(:table,:column)"),
                            {"table": f'public."{table.name}"', "column": column.name},
                        ).scalar_one()
                        if sequence:
                            maximum = target.exec_driver_sql(
                                f'SELECT MAX("{column.name}") FROM public."{table.name}"'
                            ).scalar_one()
                            target.execute(
                                text(
                                    "SELECT setval(CAST(:seq AS regclass),:value,:used)"
                                ),
                                {
                                    "seq": sequence,
                                    "value": max(1, maximum or 0),
                                    "used": maximum is not None and maximum > 0,
                                },
                            )
            target.exec_driver_sql(
                "COMMENT ON SCHEMA memora IS 'memora-import:"
                + result["import_id"]
                + "'"
            )
            # Media remains mounted at its original path, not rewritten or decoded.
            for path in sorted(domain.parent.rglob("*")):
                if (
                    path.is_file()
                    and path.suffix not in (".sqlite3", ".sqlite3-wal", ".sqlite3-shm")
                    and path.name != "worker.lock"
                ):
                    result["audio"][str(path.relative_to(domain.parent))] = (
                        hashlib.file_digest(path.open("rb"), "sha256").hexdigest()
                    )
        proof.parent.mkdir(parents=True, exist_ok=True)
        proof.write_text(json.dumps(result, indent=2) + "\n")
        proof.chmod(0o600)
        return result
    finally:
        engine.dispose()
        for source in sources.values():
            source.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument(
        "--env-file", type=Path, default=ROOT / ".memora/docker/backend.env"
    )
    parser.add_argument("--port", type=int, default=5433)
    args = parser.parse_args()
    if not args.apply:
        raise SystemExit(
            "Import hors ligne : arrêter Memora puis utiliser --apply. Les sources SQLite seront sauvegardées et conservées."
        )
    from dotenv import dotenv_values
    from sqlalchemy.engine import make_url

    values = {k: v for k, v in dotenv_values(args.env_file).items() if v is not None}
    url = (
        make_url(values["DATABASE_URL"])
        .set(host="127.0.0.1", port=args.port)
        .render_as_string(hide_password=False)
    )
    values.update(
        DATABASE_URL=url,
        MEMORA_DATABASE_URL=url.replace("postgresql+psycopg://", "postgresql://"),
        MEMORA_DISABLE_WORKER="1",
    )
    os.environ.update(values)
    data = ROOT / ".memora/data"
    with (data / "worker.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with sqlite3.connect(
            (data / "memora.sqlite3").as_uri() + "?mode=ro", uri=True
        ) as source:
            if source.execute(
                "SELECT count(*) FROM jobs WHERE state IN ('queued','running')"
            ).fetchone()[0]:
                raise SystemExit("Traitement actif : import refusé")
            if any(
                json.loads(row[0]).get("state") in ("recording", "paused")
                for row in source.execute("SELECT data FROM meetings")
            ):
                raise SystemExit("Enregistrement actif : import refusé")
        backup = (
            ROOT
            / ".memora/backups"
            / (datetime.now(UTC).strftime("postgres-%Y%m%d-%H%M%S-") + uuid4().hex[:6])
        )
        result = migrate(
            ROOT / ".memora/accounts.sqlite3",
            data / "memora.sqlite3",
            url,
            ROOT / ".memora/docker/import-complete.json",
            backup,
        )
        print(
            f"Import vérifié : {len(result['tables'])} tables, {sum(t['rows'] for t in result['tables'].values())} lignes ; empreintes identiques. Sources et sauvegardes privées conservées."
        )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # Connection exceptions may contain passwords or private records.
        print(
            f"Import interrompu ({type(exc).__name__}). Aucune source modifiée ; vérifier la cible et les prérequis.",
            file=sys.stderr,
        )
        raise SystemExit(1) from None
