"""Stable account incarnation; old JWTs must reconnect after upgrade.

Online migrations backfill random UIDs per account; offline SQL uses dialect UUID functions.
SQLite upgrade uses ADD COLUMN + UPDATE + CREATE UNIQUE INDEX, no table rebuild.
"""

from uuid import uuid4
from alembic import context, op
import sqlalchemy as sa

revision = "0007_account_uid"
down_revision = "0006_access_status"
branch_labels = None
depends_on = None
# CI may round-trip a reversible predecessor, but must never remove this boundary.
irreversible_security = True


def upgrade():
    if context.is_offline_mode():
        functions = {
            "sqlite": "lower(hex(randomblob(16)))",
            "postgresql": "replace(gen_random_uuid()::text, '-', '')",
            "mysql": "replace(UUID(), '-', '')",
        }
        dialect = op.get_context().dialect.name
        if dialect not in functions:
            raise RuntimeError(
                "Offline account UID migration unsupported for this dialect; use reviewed online migration"
            )
        op.add_column("user", sa.Column("account_uid", sa.String(32), nullable=True))
        op.execute(
            'UPDATE "user" SET account_uid='
            + functions[dialect]
            + " WHERE account_uid IS NULL OR account_uid=''"
            if dialect != "mysql"
            else "UPDATE `user` SET account_uid="
            + functions[dialect]
            + " WHERE account_uid IS NULL OR account_uid=''"
        )
        op.create_index("ix_user_account_uid", "user", ["account_uid"], unique=True)
        return
    connection = op.get_bind()
    columns = {column["name"] for column in sa.inspect(connection).get_columns("user")}
    if "account_uid" not in columns:
        # Nullable ADD preserves existing SQLite rows without batch table rebuild.
        # Application always generates a UID; unique index protects all non-null UIDs.
        op.add_column("user", sa.Column("account_uid", sa.String(32), nullable=True))
    users = sa.table("user", sa.column("id"), sa.column("account_uid"))
    for row in connection.execute(
        sa.select(users.c.id).where(
            sa.or_(users.c.account_uid.is_(None), users.c.account_uid == "")
        )
    ).fetchall():
        connection.execute(
            users.update().where(users.c.id == row.id).values(account_uid=uuid4().hex)
        )
    inspector = sa.inspect(connection)
    index_names = {index["name"] for index in inspector.get_indexes("user")}
    if "ix_user_account_uid" not in index_names:
        op.create_index("ix_user_account_uid", "user", ["account_uid"], unique=True)


def downgrade():
    # Removing account incarnation would re-enable cross-account access on ID reuse.
    raise RuntimeError(
        "Security migration cannot be downgraded; restore a reviewed backup explicitly"
    )
