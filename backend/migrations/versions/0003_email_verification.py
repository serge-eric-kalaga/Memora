"""Confirmation optionnelle des adresses, sans bloquer les comptes existants."""

from alembic import context, op
import sqlalchemy as sa

revision = "0003_email_verification"
down_revision = "0002_password_recovery"
branch_labels = None
depends_on = None


def upgrade():
    """Ajouter les champs ; adopter également une base neuve créée par l’ORM."""
    columns = (
        set()
        if context.is_offline_mode()
        else {c["name"] for c in sa.inspect(op.get_bind()).get_columns("user")}
    )
    for column in [
        sa.Column(
            "email_verification_required",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("email_verified_at", sa.DateTime(), nullable=True),
        sa.Column("email_verification_digest", sa.String(64), nullable=True),
        sa.Column("email_verification_expires_at", sa.DateTime(), nullable=True),
    ]:
        if column.name not in columns:
            op.add_column("user", column)
    if context.is_offline_mode() or not any(
        i["name"] == "ix_user_email_verification_digest"
        for i in sa.inspect(op.get_bind()).get_indexes("user")
    ):
        op.create_index(
            "ix_user_email_verification_digest", "user", ["email_verification_digest"]
        )


def downgrade():
    """Retirer uniquement les données de confirmation."""
    op.drop_index("ix_user_email_verification_digest", table_name="user")
    with op.batch_alter_table("user") as batch:
        batch.drop_column("email_verification_expires_at")
        batch.drop_column("email_verification_digest")
        batch.drop_column("email_verified_at")
        batch.drop_column("email_verification_required")
