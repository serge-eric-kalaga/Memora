"""Ajouter l’horodatage de la dernière connexion réussie."""
from alembic import op, context
import sqlalchemy as sa

revision = "0001_last_login_at"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    """Ajouter le champ aux bases existantes ; accepter un schéma neuf créé par l’ORM."""
    if not context.is_offline_mode():
        columns = {column["name"]: column for column in sa.inspect(op.get_bind()).get_columns("user")}
        if "last_login_at" in columns:
            column = columns["last_login_at"]
            if not isinstance(column["type"], sa.DateTime) or not column["nullable"]:
                raise RuntimeError("La colonne last_login_at existante ne correspond pas au schéma attendu")
            return
    op.add_column("user", sa.Column("last_login_at", sa.DateTime(), nullable=True))


def downgrade():
    """Retirer l’horodatage sans supprimer les comptes utilisateur."""
    with op.batch_alter_table("user") as batch:
        batch.drop_column("last_login_at")
