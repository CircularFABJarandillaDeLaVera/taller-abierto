"""La retirada HTTP preserva datos y archivos históricos privados."""

import re

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db, make_engine
from app.identity import new_session
from app.main import app
from app.models import Attachment, Message, Order, OrderKind, OrderStatus, PhotoConsent, User, UserRole


def test_historical_photo_inaccessible(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'historico.db'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine)
    private = tmp_path / "private"
    private.mkdir()
    file = private / "historico.png"
    file.write_bytes(b"archivo historico ficticio")
    with sessions() as db:
        visitor = User(alias="visita_foto", role=UserRole.VISITOR)
        teacher = User(alias="docente_foto", role=UserRole.TEACHER)
        student = User(alias="creador_foto", role=UserRole.STUDENT)
        db.add_all([visitor, teacher, student])
        db.flush()
        order = Order(kind=OrderKind.CUSTOM_FIGURE, status=OrderStatus.RECEIVED, requester_id=visitor.id, recipient_id=student.id, requester_alias="Visita", description="Figura de ejemplo", visitor_access_enabled=True)
        db.add(order)
        db.flush()
        db.add(Message(order_id=order.id, author_id=visitor.id, body="Mensaje histórico"))
        consent = PhotoConsent(order_id=order.id, accepted_by_id=visitor.id, text_version="fotografias-v1-2026-11")
        db.add(consent)
        db.flush()
        photo = Attachment(order_id=order.id, uploaded_by_id=visitor.id, source="REQUESTER", stored_name=file.name, original_name="ejemplo.png", mime_type="image/png", size_bytes=file.stat().st_size, consent_id=consent.id)
        db.add(photo)
        db.commit()
        order_id, photo_id = order.id, photo.id
        credentials = [new_session(db, user) for user in (visitor, teacher, student)]

    def override_db():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    try:
        for credential in [None, *credentials]:
            client = TestClient(app, follow_redirects=False)
            if credential:
                client.cookies.set("ta_session", credential)
            base = f"/panel/solicitudes/{order_id}/fotos"
            assert client.post(base, files={"photos": ("nuevo.png", b"foto", "image/png")}).status_code == 404
            assert client.get(f"{base}/{photo_id}").status_code == 404
            assert client.post(f"{base}/{photo_id}/eliminar").status_code == 404
            if credential:
                detail = client.get(f"/panel/solicitudes/{order_id}")
                assert detail.status_code == 200
                assert 'type="file"' not in detail.text
                assert f"/fotos/{photo_id}" not in detail.text
        with sessions() as db:
            assert db.get(Attachment, photo_id) is not None
            assert db.scalar(select(PhotoConsent).where(PhotoConsent.order_id == order_id)) is not None
        assert file.read_bytes() == b"archivo historico ficticio"
    finally:
        app.dependency_overrides.clear()


def test_custom_request_without_photos_and_multipart_rejected(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'solicitudes.db'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine)

    def override_db():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app, follow_redirects=False)
        page = client.get("/figura-personalizada")
        assert page.status_code == 200
        assert 'name="alias"' in page.text and 'name="description"' in page.text
        assert 'type="file"' not in page.text and 'type="checkbox"' not in page.text
        assert "Antes de enviar fotografías al creador" in page.text
        csrf = re.search(r'name="csrf_token" value="([^"]+)"', page.text).group(1)
        data = {"alias": "Visitante ficticio", "description": "Una figura con chaqueta verde", "csrf_token": csrf}
        assert client.post("/figura-personalizada", data=data, files={"photos": ("foto.png", b"falso", "image/png")}).status_code == 415
        with sessions() as db:
            assert db.scalar(select(Order.id)) is None
        assert client.post("/figura-personalizada", data=data).status_code == 303
        with sessions() as db:
            order = db.scalar(select(Order))
            assert order.recipient_id is None and order.kind == OrderKind.CUSTOM_FIGURE
            assert db.scalar(select(Message).where(Message.order_id == order.id)).body == data["description"]
            assert db.scalar(select(Attachment.id)) is None
    finally:
        app.dependency_overrides.clear()
