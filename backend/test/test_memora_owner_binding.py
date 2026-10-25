"""Legacy incarnation binding only when chronology and a meeting prove ownership."""

from datetime import datetime, UTC
import importlib.util
import json
from pathlib import Path
import sqlite3


def test_owner_binding_dry_run_and_safe_apply():
    path = Path(__file__).resolve().parents[2] / "scripts/memora-bind-owners.py"
    spec = importlib.util.spec_from_file_location("memora_bind_owners", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    connection = sqlite3.connect(":memory:")
    connection.executescript(
        "CREATE TABLE meetings(id TEXT,owner INTEGER,data TEXT); CREATE TABLE reports(id TEXT,meeting TEXT); CREATE TABLE mail(id TEXT,owner_uid TEXT);"
    )
    accounts = {
        1: {
            "account_uid": "safe-incarnation",
            "date_creation": datetime.fromtimestamp(100, UTC),
        },
        2: {
            "account_uid": "recreated-incarnation",
            "date_creation": datetime.fromtimestamp(500, UTC),
        },
    }
    for mid, owner, created in [
        ("safe", 1, 200),
        ("older", 2, 300),
        ("ambiguous", 1, 100.5),
        ("orphan", 9, 400),
    ]:
        connection.execute(
            "INSERT INTO meetings VALUES(?,?,?)",
            (mid, owner, json.dumps({"created": created})),
        )
    connection.execute("INSERT INTO reports VALUES(?,?)", ("report-safe", "safe"))
    for key in [
        "invite:safe:hash",
        "report:report-safe",
        "invite:older:hash",
        "arbitrary-owner-id-1",
    ]:
        connection.execute("INSERT INTO mail VALUES(?,NULL)", (key,))
    before = connection.execute("SELECT data FROM meetings ORDER BY id").fetchall()
    expected = {
        "bound_meetings": 1,
        "bound_mail": 2,
        "existing_meetings": 0,
        "orphan_meetings": 1,
        "unsafe_chronology": 2,
        "unbound_mail": 2,
    }
    assert module.bind_owners(connection, accounts, False) == expected
    assert (
        connection.execute("SELECT data FROM meetings ORDER BY id").fetchall() == before
    )
    assert (
        connection.execute(
            "SELECT count(*) FROM mail WHERE owner_uid IS NOT NULL"
        ).fetchone()[0]
        == 0
    )
    assert module.bind_owners(connection, accounts, True) == expected
    bindings = {
        mid: json.loads(raw).get("owner_uid")
        for mid, raw in connection.execute("SELECT id,data FROM meetings")
    }
    assert bindings == {
        "safe": "safe-incarnation",
        "older": None,
        "ambiguous": None,
        "orphan": None,
    }
    mails = dict(connection.execute("SELECT id,owner_uid FROM mail"))
    assert mails == {
        "invite:safe:hash": "safe-incarnation",
        "report:report-safe": "safe-incarnation",
        "invite:older:hash": None,
        "arbitrary-owner-id-1": None,
    }
    repeated = module.bind_owners(connection, accounts, True)
    assert (
        repeated["bound_meetings"] == 0
        and repeated["existing_meetings"] == 1
        and repeated["bound_mail"] == 0
    )
    connection.close()
