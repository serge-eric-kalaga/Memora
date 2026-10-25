"""Descriptions et désactivation réversible des rôles et permissions."""

from alembic import context, op
import sqlalchemy as sa

revision = "0006_access_status"
down_revision = "0005_superuser"
branch_labels = None
depends_on = None


def upgrade():
    """Conserver tous les droits existants actifs lors de la migration."""
    for table in ("role", "permission"):
        columns = (
            set()
            if context.is_offline_mode()
            else {
                column["name"]
                for column in sa.inspect(op.get_bind()).get_columns(table)
            }
        )
        if "description" not in columns:
            op.add_column(
                table,
                sa.Column(
                    "description", sa.String(500), nullable=False, server_default=""
                ),
            )
        if "is_active" not in columns:
            op.add_column(
                table,
                sa.Column(
                    "is_active",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.text("1"),
                ),
            )


def downgrade():
    """Retirer les métadonnées en préservant les liens d’attribution."""
    for table in ("role", "permission"):
        with op.batch_alter_table(table) as batch:
            batch.drop_column("is_active")
            batch.drop_column("description")
