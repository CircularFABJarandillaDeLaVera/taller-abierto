from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import inspect, text
from sqlalchemy.orm import sessionmaker

from app.main import app


def test_home_and_health():
    client = TestClient(app)
    assert client.get("/").status_code == 200
    assert "Tu idea." in client.get("/").text
    assert client.get("/health").json() == {"status": "ok"}


def test_migrated_schema_has_expected_tables(tmp_path: Path):
    db_url = f"sqlite:///{tmp_path / 'test.db'}"
    from app.database import make_engine
    engine = make_engine(db_url)
    from alembic.config import Config
    from alembic import command
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(config, "head")
    tables = set(inspect(engine).get_table_names())
    assert {"users", "products", "orders", "messages", "attachments", "alembic_version"} <= tables


def test_foreign_keys_and_unassigned_custom_order(tmp_path: Path):
    from app.database import make_engine
    engine = make_engine(f"sqlite:///{tmp_path / 'integrity.db'}")
    from app.database import Base
    import app.models  # noqa: F401
    Base.metadata.create_all(engine)
    with engine.connect() as connection:
        assert connection.execute(text("PRAGMA foreign_keys")).scalar() == 1
    Session = sessionmaker(engine)
    with Session() as session:
        from app.models import Order, OrderKind, OrderStatus, User, UserRole
        visitor = User(alias="visitante-demo", role=UserRole.VISITOR)
        session.add(visitor)
        session.flush()
        order = Order(kind=OrderKind.CUSTOM_FIGURE, status=OrderStatus.RECEIVED, requester_id=visitor.id, recipient_id=None, description="Figura de prueba")
        session.add(order)
        session.commit()
        assert order.recipient_id is None

