"""Review legacy domain owners after Alembic 0007; dry-run by default.

Run from repository root with the reviewed auth DATABASE_URL/MEMORA_DATA_DIR.
Never infers mail ownership from an integer account ID alone.
"""

import argparse
import json
import math
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from api.configs.config import Setting
from api.memora import store
from sqlalchemy import create_engine, text


def bind_owners(connection, accounts, apply=False):
    counts = {
        "bound_meetings": 0,
        "bound_mail": 0,
        "existing_meetings": 0,
        "orphan_meetings": 0,
        "unsafe_chronology": 0,
        "unbound_mail": 0,
    }
    bindings = {}
    for row in connection.execute("SELECT id,owner,data FROM meetings").fetchall():
        mid, owner, raw = row
        meeting = json.loads(raw)
        uid = meeting.get("owner_uid")
        if uid:
            counts["existing_meetings"] += 1
        else:
            account = accounts.get(owner)
            if not account or not account.get("account_uid"):
                counts["orphan_meetings"] += 1
                continue
            created = account.get("date_creation")
            if isinstance(created, str):
                try:
                    created = datetime.fromisoformat(created)
                except ValueError:
                    created = None
            epoch = (
                created.replace(tzinfo=created.tzinfo or UTC).timestamp()
                if isinstance(created, datetime)
                else None
            )
            meeting_created = meeting.get("created")
            # SQL creation timestamps may have only second precision. Treat the
            # entire creation second as ambiguous rather than binding a recreated ID.
            if (
                epoch is None
                or not isinstance(meeting_created, (int, float))
                or not math.isfinite(meeting_created)
                or meeting_created < math.floor(epoch) + 1
            ):
                counts["unsafe_chronology"] += 1
                continue
            uid = account["account_uid"]
            counts["bound_meetings"] += 1
            if apply:
                meeting["owner_uid"] = uid
                connection.execute(
                    "UPDATE meetings SET data=? WHERE id=?", (json.dumps(meeting), mid)
                )
        bindings[mid] = uid
    reports = {
        rid: mid for rid, mid in connection.execute("SELECT id,meeting FROM reports")
    }
    for key, existing_uid in connection.execute(
        "SELECT id,owner_uid FROM mail"
    ).fetchall():
        if existing_uid:
            continue
        mid = (
            key.split(":", 2)[1]
            if key.startswith("invite:") and len(key.split(":", 2)) == 3
            else reports.get(key[7:])
            if key.startswith("report:")
            else None
        )
        uid = bindings.get(mid)
        if not uid:
            counts["unbound_mail"] += 1
            continue
        counts["bound_mail"] += 1
        if apply:
            connection.execute(
                "UPDATE mail SET owner_uid=? WHERE id=? AND owner_uid IS NULL",
                (uid, key),
            )
    return counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--dry-run", action="store_true", help="Default: inspect without writing"
    )
    group.add_argument(
        "--apply", action="store_true", help="Write reviewed safe bindings only"
    )
    args = parser.parse_args()
    path = store.ROOT / "memora.sqlite3"
    if not path.is_file():
        parser.error("Domain database absent; no database will be created")
    engine = create_engine(Setting.DATABASE_URL)
    with engine.connect() as auth:
        accounts = {
            row["id"]: dict(row)
            for row in auth.execute(
                text('SELECT id,account_uid,date_creation FROM "user"')
            ).mappings()
        }
    connection = sqlite3.connect(path.as_uri() + "?mode=rw", uri=True)
    try:
        connection.execute("BEGIN IMMEDIATE" if args.apply else "BEGIN")
        result = bind_owners(connection, accounts, args.apply)
        connection.commit() if args.apply else connection.rollback()
    except BaseException:
        connection.rollback()
        raise
    finally:
        connection.close()
        engine.dispose()
    print(
        json.dumps(
            {"mode": "apply" if args.apply else "dry-run", **result}, ensure_ascii=False
        )
    )


if __name__ == "__main__":
    main()
