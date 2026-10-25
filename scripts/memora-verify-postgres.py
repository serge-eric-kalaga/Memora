"""Run PostgreSQL contracts/import on two new synthetic DBs, then remove only those DBs."""

import os
from pathlib import Path
import secrets
import subprocess
import sys

import psycopg
from psycopg import sql
from dotenv import dotenv_values
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]


def main():
    private = ROOT / ".memora/docker"
    env = dotenv_values(private / "backend.env")
    compose = dotenv_values(private / "compose.env")
    base = make_url(env["DATABASE_URL"]).set(
        drivername="postgresql",
        host="127.0.0.1",
        port=int(compose.get("MEMORA_POSTGRES_PORT", "5433")),
    )
    names = []
    child_env = dict(os.environ)
    with psycopg.connect(
        base.render_as_string(hide_password=False), autocommit=True
    ) as admin:
        try:
            for key in ("MEMORA_TEST_POSTGRES_URL", "MEMORA_TEST_IMPORT_URL"):
                name = "memora_test_" + secrets.token_hex(8)
                admin.execute(
                    sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name))
                )
                names.append(name)
                child_env[key] = base.set(database=name).render_as_string(
                    hide_password=False
                )
            result = subprocess.run(
                [
                    str(ROOT / "backend/.venv/bin/python"),
                    str(ROOT / "scripts/memora-test.py"),
                    "test/test_memora_postgres_live.py",
                    "test/test_memora_postgres_import.py",
                    "-q",
                ],
                env=child_env,
                cwd=ROOT,
                check=False,
            )
            return result.returncode
        finally:
            for name in names:
                admin.execute(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()",
                    (name,),
                )
                admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(
            "PostgreSQL synthetic verification failed:",
            type(exc).__name__,
            file=sys.stderr,
        )
        raise SystemExit(1) from None
