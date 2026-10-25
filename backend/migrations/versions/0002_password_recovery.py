"""Adresse privée, révocation des sessions et récupération de mot de passe."""

from alembic import context, op
import sqlalchemy as sa

revision = "0002_password_recovery"
down_revision = "0001_last_login_at"
branch_labels = None
depends_on = None


def upgrade():
    """Ajouter les champs sans modifier les mots de passe ni les comptes existants."""
    columns = (
        {}
        if context.is_offline_mode()
        else {c["name"]: c for c in sa.inspect(op.get_bind()).get_columns("user")}
    )
    additions = [
        sa.Column("email", sa.String(254), nullable=True),
        sa.Column("auth_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("password_reset_digest", sa.String(64), nullable=True),
        sa.Column("password_reset_expires_at", sa.DateTime(), nullable=True),
    ]
    for column in additions:
        if column.name not in columns:
            op.add_column("user", column)
    if "email" not in columns:
        op.create_index("ix_user_email", "user", ["email"], unique=True)
    if context.is_offline_mode() or not sa.inspect(op.get_bind()).has_table(
        "recovery_rate_limit"
    ):
        op.create_table(
            "recovery_rate_limit",
            sa.Column("key", sa.String(64), primary_key=True),
            sa.Column("window_start", sa.DateTime(), nullable=False),
            sa.Column("attempts", sa.Integer(), nullable=False),
            sa.Column(
                "date_creation",
                sa.DateTime(),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column("date_modification", sa.DateTime(), nullable=True),
        )
    if context.is_offline_mode() or not any(
        index["name"] == "ix_user_password_reset_digest"
        for index in sa.inspect(op.get_bind()).get_indexes("user")
    ):
        op.create_index(
            "ix_user_password_reset_digest", "user", ["password_reset_digest"]
        )
    if context.is_offline_mode() or not any(
        index["name"] == "ix_recovery_rate_limit_window_start"
        for index in sa.inspect(op.get_bind()).get_indexes("recovery_rate_limit")
    ):
        op.create_index(
            "ix_recovery_rate_limit_window_start",
            "recovery_rate_limit",
            ["window_start"],
        )


def downgrade():
    """Retirer les données de récupération ; les comptes et mots de passe sont conservés."""
    op.drop_table("recovery_rate_limit")
    op.drop_index("ix_user_password_reset_digest", table_name="user")
    op.drop_index("ix_user_email", table_name="user")
    with op.batch_alter_table("user") as batch:
        batch.drop_column("password_reset_expires_at")
        batch.drop_column("password_reset_digest")
        batch.drop_column("auth_version")
        batch.drop_column("email")
