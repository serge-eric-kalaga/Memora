"""Small PostgreSQL DB-API bridge for Memora's parameterized domain queries.

The domain schema is separate from SQLAlchemy's account tables. Transactions use
one advisory lock, preserving the existing SQLite single-writer critical sections
across API and worker processes. Inference never holds a domain connection.
"""

import re
from pathlib import Path

# Stable application namespace; transaction-scoped, automatically released on
# commit, rollback or connection loss. No process-local mutex can replace this.
DOMAIN_LOCK = 546523223115143697
SCHEMA = "memora"


class Row(dict):
    """sqlite3.Row-compatible keyed and positional reads."""

    def __getitem__(self, key):
        if isinstance(key, (int, slice)):
            return tuple(self.values())[key]
        return super().__getitem__(key)

    def __iter__(self):
        # sqlite3.Row unpacks values (not names); upload aggregates rely on this.
        # keys() remains available so dict(row) and mapping expansion still work.
        return iter(self.values())


def row_factory(cursor):
    names = [column.name for column in (cursor.description or [])]
    return lambda values: Row(zip(names, values))


def sql_statement(sql, parameters=False):
    """Translate only the finite SQL dialect used by the domain store.

    Values always remain bound parameters. The scanner leaves question marks
    and identifiers inside string literals untouched.
    """
    sql = re.sub(
        r"json_extract\((\w+(?:\.\w+)?),'\$\.(\w+)'\)",
        r"(\1::jsonb->>'\2')",
        sql,
    )
    sql = re.sub(r"length\(CAST\((\w+) AS BLOB\)\)", r"octet_length(\1)", sql)
    sql = sql.replace(
        "n.rowid DESC", "(n.data::jsonb->>'created')::double precision DESC,n.id DESC"
    )
    ignore = bool(re.match(r"\s*INSERT OR IGNORE\b", sql, re.IGNORECASE))
    sql = re.sub(r"\bINSERT OR IGNORE\b", "INSERT", sql, flags=re.IGNORECASE)
    if ignore:
        sql = sql.rstrip().rstrip(";") + " ON CONFLICT DO NOTHING"
    tokens = re.split(r"('(?:[^']|'')*'|\"(?:[^\"]|\"\")*\")", sql)
    for index in range(0, len(tokens), 2):
        part = tokens[index]
        part = re.sub(r"\bwindow\b", '"window"', part, flags=re.IGNORECASE)
        part = re.sub(r"\bREAL\b", "DOUBLE PRECISION", part, flags=re.IGNORECASE)
        if parameters:
            part = part.replace("%", "%%").replace("?", "%s")
        tokens[index] = part
    if parameters:
        # Psycopg also interprets percent signs inside SQL string literals.
        for index in range(1, len(tokens), 2):
            tokens[index] = tokens[index].replace("%", "%%")
    translated = "".join(tokens)
    if (
        translated.startswith("INSERT INTO limits ")
        and "ON CONFLICT(key)" in translated
    ):
        translated = translated.replace(
            'CASE WHEN "window"=', 'CASE WHEN limits."window"='
        ).replace("THEN count+1", "THEN limits.count+1")
    return translated


class Connection:
    dialect = "postgresql"

    def __init__(self, url):
        import psycopg

        self.connection = psycopg.connect(url, row_factory=row_factory)
        self._locked = False
        try:
            self._configure()
        except BaseException:
            self.connection.close()
            raise

    def _configure(self):
        # Fixed identifiers, never derived from request input. Restrict waiting
        # rather than let a failed migration hang startup forever.
        self.connection.execute("SET lock_timeout = '30s'")
        self.connection.execute("SET statement_timeout = '60s'")
        self.connection.execute("SET search_path TO memora, public")
        self.connection.commit()

    def _lock(self):
        if not self._locked:
            self.connection.execute("SELECT pg_advisory_xact_lock(%s)", (DOMAIN_LOCK,))
            self._locked = True

    def execute(self, sql, parameters=None):
        self._lock()
        if sql.strip().upper() in ("BEGIN", "BEGIN IMMEDIATE"):
            # The transaction began when its database-wide lock was acquired.
            return self.connection.execute("SELECT 1 WHERE FALSE")
        return self.connection.execute(
            sql_statement(sql, parameters is not None), parameters
        )

    def executescript(self, script):
        # Split only statement separators outside quoted values/comments. Schema
        # migration comments themselves may contain semicolons.
        tokens = re.findall(
            r"'(?:[^']|'')*'|\"(?:[^\"]|\"\")*\"|--[^\n]*|/\*[\s\S]*?\*/|;|[^'\";/\-]+|.",
            script,
        )
        parts = []
        for token in [*tokens, ";"]:
            if token.startswith(("--", "/*")):
                parts.append(" ")
            elif token == ";":
                statement = "".join(parts).strip()
                if statement and not statement.upper().startswith("PRAGMA "):
                    self.execute(statement)
                parts = []
            else:
                parts.append(token)

    def commit(self):
        self.connection.commit()
        self._locked = False

    def rollback(self):
        self.connection.rollback()
        self._locked = False

    def close(self):
        self.connection.close()

    def initialize_schema(self, migrations: Path):
        self._lock()
        self.connection.execute("CREATE SCHEMA IF NOT EXISTS memora")
        for name in (
            "001_initial.sql",
            "002_config_history.sql",
            "003_analysis_requests.sql",
        ):
            self.executescript((migrations / name).read_text())
        self.execute("ALTER TABLE mail ADD COLUMN IF NOT EXISTS owner_uid TEXT")
        self.executescript((migrations / "004_owner_incarnation.sql").read_text())
        self.executescript((migrations / "005_account_tombstones.sql").read_text())
        for name, declaration in (
            ("phase", "TEXT NOT NULL DEFAULT 'source'"),
            ("source_version", "INTEGER"),
            ("result_report_id", "TEXT"),
        ):
            self.execute(
                f"ALTER TABLE jobs ADD COLUMN IF NOT EXISTS {name} {declaration}"
            )
        for name in ("006_job_checkpoints.sql", "007_human_review.sql"):
            self.executescript((migrations / name).read_text())

        # PostgreSQL-only transport triggers, without changing stored user data.
        # Execute directly: PL/pgSQL dollar-quoted functions are not SQLite SQL.
        self.connection.execute((migrations.parent / "realtime.sql").read_text())
