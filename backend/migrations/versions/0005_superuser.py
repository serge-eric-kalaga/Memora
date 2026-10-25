"""Statut de super administrateur, sans promouvoir de compte existant."""

from alembic import context, op
import sqlalchemy as sa

revision = "0005_superuser"
down_revision = "0004_roles_permissions"
branch_labels = None
depends_on = None


def upgrade():
    """Ajouter le statut désactivé par défaut et adopter une base ORM neuve."""
    columns = (
        set()
        if context.is_offline_mode()
        else {c["name"] for c in sa.inspect(op.get_bind()).get_columns("user")}
    )
    if "is_superuser" not in columns:
        op.add_column(
            "user",
            sa.Column(
                "is_superuser",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("0"),
            ),
        )


def downgrade():
    """Retirer le statut sans supprimer les utilisateurs."""
    with op.batch_alter_table("user") as batch:
        batch.drop_column("is_superuser")
