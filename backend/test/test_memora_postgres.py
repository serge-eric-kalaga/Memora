"""Synthetic dialect contracts; live PostgreSQL exercised by isolated migration QA."""

from api.memora.postgres import Connection, Row, sql_statement


def test_row_supports_mapping_and_positions():
    row = Row(id="synthetic-id", created=123.456)
    assert row["id"] == row[0] == "synthetic-id"
    assert row[-1] == row["created"] == 123.456
    assert dict(row) == {"id": "synthetic-id", "created": 123.456}
    assert tuple(row) == ("synthetic-id", 123.456)
    assert list(row.keys()) == ["id", "created"]
    assert row[:] == ("synthetic-id", 123.456)
    assert {**row} == dict(row)


def test_bound_values_are_not_interpolated():
    sql = sql_statement(
        "SELECT data FROM meetings WHERE id=? AND data LIKE '100%'", True
    )
    assert sql == "SELECT data FROM meetings WHERE id=%s AND data LIKE '100%%'"
    assert sql_statement("SELECT '?' AS literal,?", True) == "SELECT '?' AS literal,%s"


def test_domain_dialect_translations():
    assert sql_statement("INSERT OR IGNORE INTO config VALUES(1,?)", True) == (
        "INSERT INTO config VALUES(1,%s) ON CONFLICT DO NOTHING"
    )
    assert sql_statement(
        "SELECT json_extract(m.data,'$.owner_uid') FROM meetings m"
    ) == ("SELECT (m.data::jsonb->>'owner_uid') FROM meetings m")
    assert sql_statement("SELECT length(CAST(data AS BLOB)) FROM transcripts") == (
        "SELECT octet_length(data) FROM transcripts"
    )
    assert sql_statement("SELECT n.* FROM notifications n ORDER BY n.rowid DESC") == (
        "SELECT n.* FROM notifications n ORDER BY "
        "(n.data::jsonb->>'created')::double precision DESC,n.id DESC"
    )
    assert sql_statement("CREATE TABLE limits(window INTEGER, created REAL)") == (
        'CREATE TABLE limits("window" INTEGER, created DOUBLE PRECISION)'
    )


def test_dialect_does_not_rewrite_strings():
    assert sql_statement("SELECT 'window REAL ?' AS value") == (
        "SELECT 'window REAL ?' AS value"
    )


def test_quoted_identifiers_remain_valid_for_imports():
    assert sql_statement(
        'INSERT INTO limits("key","window","count") VALUES(?,?,?)', True
    ) == ('INSERT INTO limits("key","window","count") VALUES(%s,%s,%s)')


def test_migrations_ignore_separators_inside_comments_and_literals():
    connection = Connection.__new__(Connection)
    statements = []
    connection.execute = statements.append
    connection.executescript(
        "-- source: original; report: committed source_version\n"
        "PRAGMA journal_mode=WAL; CREATE TABLE test(data TEXT);"
        "/* another ; separator */ INSERT INTO test VALUES('value;--literal');"
    )
    assert statements == [
        "CREATE TABLE test(data TEXT)",
        "INSERT INTO test VALUES('value;--literal')",
    ]


def test_rate_limit_upsert_qualifies_existing_values():
    sql = sql_statement(
        "INSERT INTO limits VALUES(?,?,1) ON CONFLICT(key) DO UPDATE SET count=CASE WHEN window=? THEN count+1 ELSE 1 END,window=?",
        True,
    )
    assert 'WHEN limits."window"=%s THEN limits.count+1' in sql
