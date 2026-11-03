"""Campos de presentación y catálogo de la microfase 1."""
from alembic import op
import sqlalchemy as sa

revision = "0002_catalog_fields"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade():
    # La migración mantiene compatibilidad con bases que ya ejecutaron 0001.
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("presentation", sa.Text(), nullable=True))
    with op.batch_alter_table("products") as batch:
        batch.add_column(sa.Column("slug", sa.String(180), nullable=False))
        batch.add_column(sa.Column("material", sa.String(160), nullable=False))
        batch.add_column(sa.Column("indicative_price", sa.Numeric(10, 2), nullable=False))
        batch.add_column(sa.Column("image_path", sa.String(255), nullable=False))
        batch.create_unique_constraint("uq_products_slug", ["slug"])


def downgrade():
    with op.batch_alter_table("products") as batch:
        batch.drop_constraint("uq_products_slug", type_="unique")
        batch.drop_column("image_path")
        batch.drop_column("indicative_price")
        batch.drop_column("material")
        batch.drop_column("slug")
    with op.batch_alter_table("users") as batch:
        batch.drop_column("presentation")

