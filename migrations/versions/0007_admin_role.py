"""Permite una cuenta administradora elegida explícitamente."""

from alembic import op

revision = "0007_admin_role"
down_revision = "0006_order_reads"
branch_labels = None
depends_on = None


def upgrade():
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'ADMIN'")


def downgrade():
    raise RuntimeError("La revisión ADMIN no admite downgrade automático sin revisar las cuentas.")
