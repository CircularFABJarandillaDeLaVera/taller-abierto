"""Alias visible e importe exacto para solicitudes."""
from alembic import op
import sqlalchemy as sa

revision = "0003_request_fields"
down_revision = "0002_catalog_fields"
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table("orders") as batch:
        batch.add_column(sa.Column("requester_alias", sa.String(80), nullable=True))
        batch.add_column(sa.Column("offer_cents", sa.Integer(), nullable=True))
        batch.create_check_constraint("ck_orders_offer_positive", "offer_cents IS NULL OR offer_cents > 0")

def downgrade():
    with op.batch_alter_table("orders") as batch:
        batch.drop_constraint("ck_orders_offer_positive", type_="check")
        batch.drop_column("offer_cents")
        batch.drop_column("requester_alias")
