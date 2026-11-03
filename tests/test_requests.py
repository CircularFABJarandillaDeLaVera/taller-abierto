import re

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db, make_engine
from app.main import app
from app.models import Message, Order, OrderKind, OrderStatus, Product, User
import app.seed as seed_module


def test_request_flows(tmp_path, monkeypatch):
    db_file = tmp_path / "requests.db"
    engine = make_engine(f"sqlite:///{db_file}")
    Base.metadata.create_all(engine)
    Sessions = sessionmaker(engine)
    monkeypatch.setattr(seed_module, "SessionLocal", Sessions)
    seed_module.seed_catalog()

    def override_db():
        with Sessions() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app, follow_redirects=False)

    def token(path):
        response = client.get(path)
        assert response.status_code == 200
        return re.search(r'name="csrf_token" value="([^"]+)"', response.text).group(1)

    try:
        path = "/productos/figura-personalizada-3d"
        csrf = token(path)
        assert client.post(path + "/consulta", data={"alias": "X", "message": "corto", "csrf_token": csrf}).status_code == 422
        assert client.post(path + "/consulta", data={"alias": "Ana", "message": "Texto suficiente", "csrf_token": "falso"}).status_code == 403
        csrf = token(path)
        result = client.post(path + "/consulta", data={"alias": "<script>alert(1)</script>", "message": "Una consulta de ejemplo", "offer": "12,50", "recipient_id": "99999", "csrf_token": csrf})
        assert result.status_code == 303
        assert result.headers["location"] == "/solicitud-recibida"
        page = client.get(result.headers["location"])
        assert page.status_code == 200 and "<script>" not in page.text
        assert client.get(result.headers["location"]).status_code == 200

        csrf = token("/figura-personalizada")
        assert client.post("/figura-personalizada", data={"alias": "A", "description": "corto", "csrf_token": csrf}).status_code == 422
        csrf = token("/figura-personalizada")
        assert client.post("/figura-personalizada", data={"alias": "Luz", "description": "Figura con tonos verdes", "csrf_token": csrf}).status_code == 303
        with Sessions() as session:
            orders = session.scalars(select(Order).order_by(Order.id)).all()
            assert len(orders) == 2
            product = session.scalar(select(Product).where(Product.slug == "figura-personalizada-3d"))
            assert orders[0].recipient_id == product.creator_id
            assert orders[0].offer_cents == 1250
            assert orders[0].requester_alias == "<script>alert(1)</script>"
            assert orders[1].kind == OrderKind.CUSTOM_FIGURE and orders[1].recipient_id is None
            assert all(o.status == OrderStatus.RECEIVED for o in orders)
            assert session.scalar(select(func.count()).select_from(Message)) == 2
            assert session.scalar(select(func.count()).select_from(User)) == 9
        reopened = make_engine(f"sqlite:///{db_file}")
        with sessionmaker(reopened)() as session:
            assert session.scalar(select(func.count()).select_from(Order)) == 2
    finally:
        app.dependency_overrides.clear()
