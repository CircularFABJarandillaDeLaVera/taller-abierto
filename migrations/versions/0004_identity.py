"""Credenciales, sesiones y recuperación sin reclamar solicitudes anteriores."""
from alembic import op
import sqlalchemy as sa

revision = "0004_identity"
down_revision = "0003_request_fields"
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("password_hash", sa.String(255), nullable=True))
    with op.batch_alter_table("orders") as batch:
        batch.add_column(sa.Column("visitor_access_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_table("login_sessions", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("token_hash", sa.String(64), nullable=False, unique=True), sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("expires_at", sa.DateTime(), nullable=False))
    op.create_table("recovery_tokens", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("token_hash", sa.String(64), nullable=False, unique=True), sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False), sa.Column("expires_at", sa.DateTime(), nullable=False), sa.Column("used_at", sa.DateTime(), nullable=True))

def downgrade():
    op.drop_table("recovery_tokens")
    op.drop_table("login_sessions")
    with op.batch_alter_table("orders") as batch:
        batch.drop_column("visitor_access_enabled")
    with op.batch_alter_table("users") as batch:
        batch.drop_column("password_hash")
