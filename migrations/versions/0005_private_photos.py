"""Aceptación por lote y adjuntos privados."""
from alembic import context, op
import sqlalchemy as sa

revision = "0005_private_photos"
down_revision = "0004_identity"
branch_labels = None
depends_on = None

def upgrade():
    # SQLite puede dejar DDL aplicado si una migración falla a mitad; tolerar la tabla vacía ya creada.
    if context.is_offline_mode() or not sa.inspect(op.get_bind()).has_table("photo_consents"):
        op.create_table("photo_consents", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False), sa.Column("accepted_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False), sa.Column("text_version", sa.String(40), nullable=False), sa.Column("accepted_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False))
    with op.batch_alter_table("attachments") as batch:
        batch.add_column(sa.Column("consent_id", sa.Integer(), nullable=True))
        batch.create_foreign_key("fk_attachments_consent", "photo_consents", ["consent_id"], ["id"], ondelete="RESTRICT")

def downgrade():
    with op.batch_alter_table("attachments") as batch:
        batch.drop_constraint("fk_attachments_consent", type_="foreignkey")
        batch.drop_column("consent_id")
    op.drop_table("photo_consents")
