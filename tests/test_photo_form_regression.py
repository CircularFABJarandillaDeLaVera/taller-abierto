"""El formulario visible solo ofrece alias y descripción, sin fotos ni casillas."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db, make_engine
from app.main import app


def test_custom_form_asks_only_for_idea_and_alias(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'formulario.db'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine)
    def override_db():
        with sessions() as db:
            yield db
    app.dependency_overrides[get_db] = override_db
    try:
        page = TestClient(app).get("/figura-personalizada")
    finally:
        app.dependency_overrides.clear()
    assert page.status_code == 200
    assert 'action="/figura-personalizada"' in page.text
    assert 'name="alias"' in page.text
    assert 'name="description"' in page.text
    for removed in ('name="photos"', 'name="rights_confirmed"', 'name="person_confirmed"'):
        assert removed not in page.text
    assert "Cuando tengas una persona artesana asignada" in page.text
