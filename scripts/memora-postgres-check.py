"""Check that Docker is using the PostgreSQL database validated by the importer."""

import json
from pathlib import Path

import psycopg
from dotenv import dotenv_values
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]


def main():
    folder = ROOT / ".memora/docker"
    proof = json.loads((folder / "import-complete.json").read_text())
    compose = dotenv_values(folder / "compose.env")
    values = dotenv_values(folder / "backend.env")
    url = make_url(values["DATABASE_URL"]).set(
        drivername="postgresql",
        host="127.0.0.1",
        port=int(compose.get("MEMORA_POSTGRES_PORT", "5433")),
    )
    if url.database != "memora" or proof.get("target") != "memora":
        raise ValueError("Unexpected database")
    expected = "memora-import:" + proof["import_id"]
    with psycopg.connect(
        url.render_as_string(hide_password=False), connect_timeout=5
    ) as c:
        row = c.execute(
            "SELECT obj_description('memora'::regnamespace,'pg_namespace'),to_regclass('public.user'),to_regclass('memora.meetings')"
        ).fetchone()
        if row[0] != expected or not row[1] or not row[2]:
            raise ValueError("Import identity mismatch")
    print("PostgreSQL : base importée et schémas vérifiés.")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit(
            "PostgreSQL non validé : vérifier le volume et l’import ; aucun démarrage applicatif effectué."
        ) from None
