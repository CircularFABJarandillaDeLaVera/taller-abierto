"""Lectura individual e inicialización del historial sin avisos retroactivos."""

from alembic import op
import sqlalchemy as sa

revision = "0006_order_reads"
down_revision = "0005_private_photos"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("orders") as batch:
        batch.add_column(sa.Column("assignment_version", sa.Integer(), nullable=False, server_default="0"))
    op.create_table(
        "order_reads",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("last_read_message_id", sa.Integer(), sa.ForeignKey("messages.id", ondelete="SET NULL")),
        sa.Column("seen_assignment_version", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("order_id", "user_id", name="uq_order_reads_person"),
    )
    # Es un corte técnico inicial, no una fecha histórica de lectura.
    # Docente: todos; creador: encargos asignados; visitante: solo accesos recuperables.
    op.execute(sa.text("""
        INSERT INTO order_reads (order_id, user_id, last_read_message_id, seen_assignment_version)
        SELECT o.id, u.id, (SELECT MAX(m.id) FROM messages m WHERE m.order_id = o.id), 0
        FROM orders o JOIN users u ON u.role = 'TEACHER'
    """))
    op.execute(sa.text("""
        INSERT INTO order_reads (order_id, user_id, last_read_message_id, seen_assignment_version)
        SELECT o.id, o.recipient_id, (SELECT MAX(m.id) FROM messages m WHERE m.order_id = o.id), 0
        FROM orders o WHERE o.recipient_id IS NOT NULL
    """))
    op.execute(sa.text("""
        INSERT INTO order_reads (order_id, user_id, last_read_message_id, seen_assignment_version)
        SELECT o.id, o.requester_id, (SELECT MAX(m.id) FROM messages m WHERE m.order_id = o.id), 0
        FROM orders o WHERE o.visitor_access_enabled = TRUE
    """))


def downgrade():
    op.drop_table("order_reads")
    with op.batch_alter_table("orders") as batch:
        batch.drop_column("assignment_version")
