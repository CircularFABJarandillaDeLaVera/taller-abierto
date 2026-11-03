"""Pruebas de privacidad y archivos en SQLite/almacenamiento temporales."""
import io
import re
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

import app.seed as seed_module
from app.database import Base, get_db, make_engine
from app.identity import hash_password
from app.main import app
from app.models import Attachment, Order, PhotoConsent, User, UserRole
from app.photos import PreparedPhoto


@pytest.fixture
def setup(tmp_path, monkeypatch):
    engine = make_engine(f"sqlite:///{tmp_path / 'photos.db'}")
    Base.metadata.create_all(engine)
    Sessions = sessionmaker(engine)
    monkeypatch.setattr(seed_module, "SessionLocal", Sessions)
    seed_module.seed_catalog()
    monkeypatch.setattr("app.photos.get_settings", lambda: SimpleNamespace(attachments_dir=str(tmp_path / "private")))
    with Sessions() as db:
        db.add(User(alias="docente_fotos", role=UserRole.TEACHER, password_hash=hash_password("Clave docente fotos")))
        for alias in ("luna_taller", "norte_creativo"):
            db.scalar(select(User).where(User.alias == alias)).password_hash = hash_password("Clave creador fotos")
        db.commit()

    def override_db():
        with Sessions() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    yield Sessions, tmp_path / "private"
    app.dependency_overrides.clear()


def token(client, path):
    response = client.get(path)
    assert response.status_code == 200
    return re.search(r'name="csrf_token" value="([^"]+)"', response.text).group(1)


def login(client, alias, password):
    return client.post("/entrar", data={"alias": alias, "password": password, "csrf_token": token(client, "/entrar")})


def test_private_storage_consent_reassignment_and_delete(setup, monkeypatch):
    Sessions, root = setup
    # El decodificador real se prueba aparte cuando Pillow está instalado.
    async def prepared(files, rights, person):
        if rights != "on" or person != "on":
            from app.photos import PhotoError
            raise PhotoError("Faltan confirmaciones.")
        return [PreparedPhoto("ejemplo.png", "image/png", b"imagen-normalizada") for _ in files if _.filename]
    monkeypatch.setattr("app.routes.prepare", prepared)
    monkeypatch.setattr("app.panel_routes.prepare", prepared)
    visitor = TestClient(app, follow_redirects=False)
    outsider = TestClient(app, follow_redirects=False)
    creator = TestClient(app, follow_redirects=False)
    second = TestClient(app, follow_redirects=False)
    teacher = TestClient(app, follow_redirects=False)
    form = "/figura-personalizada"
    data = {"alias": "Demo", "description": "Figura de ejemplo", "rights_confirmed": "on", "person_confirmed": "on"}
    files = {"photos": ("ejemplo.png", b"entrada", "image/png")}
    assert visitor.post(form, data={**data, "csrf_token": token(visitor, form)}, files=files).status_code == 303
    with Sessions() as db:
        order = db.scalars(select(Order).order_by(Order.id.desc())).first()
        order_id = order.id
        photo = db.scalar(select(Attachment).where(Attachment.order_id == order_id))
        photo_id = photo.id
        assert photo.consent.accepted_by_id == order.requester_id
        assert photo.consent.text_version
        assert photo.consent.accepted_at
        assert (root / photo.stored_name).read_bytes() == b"imagen-normalizada"
        assert db.scalar(select(func.count()).select_from(PhotoConsent)) == 1
        first_id = db.scalar(select(User.id).where(User.alias == "luna_taller"))
        second_id = db.scalar(select(User.id).where(User.alias == "norte_creativo"))
    url = f"/panel/solicitudes/{order_id}/fotos/{photo_id}"
    assert visitor.get(url).status_code == 200
    assert visitor.get(url).headers["cache-control"] == "no-store"
    assert outsider.get(url).status_code == 404
    upload = f"/panel/solicitudes/{order_id}/fotos"
    upload_data = {"rights_confirmed": "on", "person_confirmed": "on"}
    assert visitor.post(upload, data={**upload_data, "person_confirmed": "", "csrf_token": token(visitor, f"/panel/solicitudes/{order_id}")}, files=files).status_code == 422
    assert visitor.post(upload, data={**upload_data, "csrf_token": token(visitor, f"/panel/solicitudes/{order_id}")}, files=[("photos", ("a.png", b"a", "image/png")), ("photos", ("b.png", b"b", "image/png"))]).status_code == 303
    assert visitor.post(upload, data={**upload_data, "csrf_token": token(visitor, f"/panel/solicitudes/{order_id}")}, files=files).status_code == 422
    assert visitor.post(upload, data={**upload_data, "csrf_token": token(visitor, f"/panel/solicitudes/{order_id}")}, files=files, headers={"content-length": str(16 * 1024 * 1024 + 1)}).status_code == 413
    with Sessions() as db:
        assert db.scalar(select(func.count()).select_from(Attachment).where(Attachment.order_id == order_id)) == 3
        assert db.scalar(select(func.count()).select_from(PhotoConsent)) == 2
    assert len(list(root.glob("*.png"))) == 3
    assert login(creator, "luna_taller", "Clave creador fotos").status_code == 303
    assert login(second, "norte_creativo", "Clave creador fotos").status_code == 303
    assert login(teacher, "docente_fotos", "Clave docente fotos").status_code == 303
    assert teacher.get(url).status_code == 200
    assign = f"/panel/solicitudes/{order_id}/asignar"
    assert teacher.post(assign, data={"student_id": first_id, "csrf_token": token(teacher, f"/panel/solicitudes/{order_id}")}).status_code == 303
    assert creator.get(url).status_code == 200
    assert teacher.post(assign, data={"student_id": second_id, "csrf_token": token(teacher, f"/panel/solicitudes/{order_id}")}).status_code == 303
    assert creator.get(url).status_code == 404
    assert second.get(url).status_code == 200
    delete = url + "/eliminar"
    assert second.post(delete, data={"csrf_token": token(second, f"/panel/solicitudes/{order_id}")}).status_code == 403
    assert visitor.post(delete, data={}).status_code == 403
    assert visitor.post(delete, data={"csrf_token": token(visitor, f"/panel/solicitudes/{order_id}")}).status_code == 303
    assert visitor.get(url).status_code == 404
    assert len(list(root.glob("*.png"))) == 2
    with Sessions() as db:
        assert db.get(Attachment, photo_id) is None
        assert db.scalar(select(func.count()).select_from(PhotoConsent)) == 2


def test_real_decoding_and_limits(setup):
    Image = pytest.importorskip("PIL.Image")
    Sessions, root = setup
    client = TestClient(app, follow_redirects=False)
    def picture(fmt="PNG", size=(30, 30)):
        stream = io.BytesIO()
        Image.new("RGB", size, "green").save(stream, format=fmt)
        return stream.getvalue()
    path = "/figura-personalizada"
    data = {"alias": "Demo", "description": "Figura de ejemplo", "rights_confirmed": "on", "person_confirmed": "on"}
    def submit(content, filename="imagen.png", overrides=None):
        return client.post(path, data={**data, **(overrides or {}), "csrf_token": token(client, path)}, files={"photos": (filename, content, "image/png")})
    for overrides in ({"rights_confirmed": ""}, {"person_confirmed": ""}):
        assert submit(picture(), overrides=overrides).status_code == 422
    assert submit(b"no es una imagen").status_code == 422
    assert submit(picture("GIF"), "imagen.gif").status_code == 422
    assert submit(picture(size=(6001, 1))).status_code == 422
    assert submit(b"x" * (5 * 1024 * 1024 + 1)).status_code == 422
    assert submit(picture()).status_code == 303
    with Sessions() as db:
        assert db.scalar(select(func.count()).select_from(Order)) == 1
        assert db.scalar(select(func.count()).select_from(Attachment)) == 1
    assert len(list(root.glob("*.png"))) == 1
