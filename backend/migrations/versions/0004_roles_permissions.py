"""Rôles, permissions et attributions explicites, sans promouvoir de compte."""

from alembic import context, op
import sqlalchemy as sa

revision = "0004_roles_permissions"
down_revision = "0003_email_verification"
branch_labels = None
depends_on = None


def upgrade():
    """Créer les tables RBAC ; adopter aussi les tables d’une base neuve ORM."""
    existing = (
        set()
        if context.is_offline_mode()
        else set(sa.inspect(op.get_bind()).get_table_names())
    )
    for name in ("role", "permission"):
        if name not in existing:
            op.create_table(
                name,
                sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
                sa.Column("name", sa.String(100), nullable=False, unique=True),
                sa.Column(
                    "date_creation",
                    sa.DateTime(),
                    nullable=False,
                    server_default=sa.func.now(),
                ),
                sa.Column("date_modification", sa.DateTime(), nullable=True),
            )
    for name, left, right in (
        ("user_role", "user", "role"),
        ("role_permission", "role", "permission"),
        ("user_permission", "user", "permission"),
    ):
        if name not in existing:
            op.create_table(
                name,
                sa.Column(
                    left + "_id",
                    sa.Integer(),
                    sa.ForeignKey(left + ".id", ondelete="CASCADE"),
                    primary_key=True,
                ),
                sa.Column(
                    right + "_id",
                    sa.Integer(),
                    sa.ForeignKey(right + ".id", ondelete="CASCADE"),
                    primary_key=True,
                ),
            )


def downgrade():
    """Retirer uniquement les droits et leurs associations, sans supprimer d’utilisateur."""
    for name in (
        "user_permission",
        "role_permission",
        "user_role",
        "permission",
        "role",
    ):
        op.drop_table(name)
