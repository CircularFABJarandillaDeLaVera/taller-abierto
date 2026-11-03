from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base, make_engine
from app.main import app
from app.models import Product, User, UserRole
from app.routes import get_db
from app.seed import seed_catalog


def test_seed_is_reproducible_and_preserves_other_data(tmp_path, monkeypatch):
    engine = make_engine(f"sqlite:///{tmp_path / 'catalog.db'}")
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(engine, autoflush=False)
    monkeypatch.setattr("app.seed.SessionLocal", TestingSession)
    with TestingSession() as session:
        session.add(User(alias="persona-ajena", role=UserRole.VISITOR))
        session.commit()

    assert seed_catalog() == (8, 5)
    assert seed_catalog() == (0, 0)
    with TestingSession() as session:
        assert session.scalar(select(func.count()).select_from(User)) == 9
        assert session.scalar(select(func.count()).select_from(Product)) == 5
        assert session.scalar(select(func.count()).select_from(Product).where(Product.creator_id.is_not(None))) == 5


def test_catalog_detail_404_and_local_navigation(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'web.db'}")
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(engine, autoflush=False)
    import app.seed as seed_module
    old_session = seed_module.SessionLocal
    seed_module.SessionLocal = TestingSession
    try:
        seed_module.seed_catalog()

        def override_db() -> Generator[Session, None, None]:
            with TestingSession() as session:
                yield session

        app.dependency_overrides[get_db] = override_db
        client = TestClient(app)
        assert client.get("/").status_code == 200
        assert client.get("/catalogo").status_code == 200
        assert client.get("/catalogo").text.count("/productos/") >= 5
        assert client.get("/productos/figura-personalizada-3d").status_code == 200
        assert "Filamento PLA" in client.get("/productos/figura-personalizada-3d").text
        assert client.get("/productos/no-existe").status_code == 404
        assert client.get("/creadores").text.count("class=\"creator-card card\"") == 8
    finally:
        app.dependency_overrides.clear()
        seed_module.SessionLocal = old_session

