"""Esquema inicial de usuarios, catálogo, encargos, mensajes y adjuntos."""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    user_role = sa.Enum("VISITOR", "STUDENT", "TEACHER", name="userrole")
    order_kind = sa.Enum("PRODUCT_INQUIRY", "CUSTOM_FIGURE", name="orderkind")
    order_status = sa.Enum("RECEIVED", "IN_CONVERSATION", "ACCEPTED", "COMPLETED", "CANCELLED", name="orderstatus")
    attachment_source = sa.Enum("REQUESTER", "RECIPIENT", "STAFF", name="attachmentsource")
    op.create_table("users", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("alias", sa.String(80), nullable=False), sa.Column("role", user_role, nullable=False), sa.Column("is_active", sa.Boolean(), nullable=False), sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False), sa.UniqueConstraint("alias"))
    op.create_table("products", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("creator_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False), sa.Column("name", sa.String(160), nullable=False), sa.Column("description", sa.Text(), nullable=False))
    op.create_table("orders", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("kind", order_kind, nullable=False), sa.Column("status", order_status, nullable=False), sa.Column("requester_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False), sa.Column("recipient_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT")), sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id", ondelete="RESTRICT")), sa.Column("description", sa.Text(), nullable=False), sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False))
    op.create_table("messages", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False), sa.Column("author_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False), sa.Column("body", sa.Text(), nullable=False), sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False))
    op.create_table("attachments", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False), sa.Column("uploaded_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False), sa.Column("source", attachment_source, nullable=False), sa.Column("stored_name", sa.String(255), nullable=False), sa.Column("original_name", sa.String(255), nullable=False), sa.Column("mime_type", sa.String(100), nullable=False), sa.Column("size_bytes", sa.Integer(), nullable=False), sa.UniqueConstraint("stored_name"))

def downgrade():
    op.drop_table("attachments"); op.drop_table("messages"); op.drop_table("orders"); op.drop_table("products"); op.drop_table("users")

