import re
from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

import app.seed as seed_module
from app.database import Base, get_db, make_engine
from app.identity import fingerprint, hash_password, now
from app.main import app
from app.models import LoginSession, Message, Order, RecoveryToken, User, UserRole


def test_three_roles_and_recovery(tmp_path, monkeypatch):
    path = tmp_path / "roles.db"
    engine = make_engine(f"sqlite:///{path}")
    Base.metadata.create_all(engine)
    Sessions = sessionmaker(engine)
    monkeypatch.setattr(seed_module, "SessionLocal", Sessions)
    seed_module.seed_catalog()
    with Sessions() as db:
        db.add(User(alias="docente_demo", role=UserRole.TEACHER, password_hash=hash_password("Clave docente 123")))
        for alias in ("luna_taller", "norte_creativo"):
            db.scalar(select(User).where(User.alias == alias)).password_hash = hash_password("Clave alumno 123")
        db.commit()

    def override_db():
        with Sessions() as db:
            yield db

    app.dependency_overrides[get_db] = override_db

    def csrf(client, path):
        page = client.get(path)
        assert page.status_code == 200
        return re.search(r'name="csrf_token" value="([^"]+)"', page.text).group(1)

    visitor = TestClient(app, follow_redirects=False)
    outsider = TestClient(app, follow_redirects=False)
    creator = TestClient(app, follow_redirects=False)
    other_creator = TestClient(app, follow_redirects=False)
    teacher = TestClient(app, follow_redirects=False)
    try:
        # Solicitudes anteriores conservadas, sin derecho de recuperación por alias.
        with Sessions() as db:
            legacy = User(alias="visitante_anterior", role=UserRole.VISITOR)
            db.add(legacy)
            db.flush()
            old = Order(kind="CUSTOM_FIGURE", status="RECEIVED", requester_id=legacy.id, requester_alias="MismoAlias", description="Solicitud anterior", visitor_access_enabled=False)
            db.add(old)
            db.commit()
            old_id = old.id

        token = csrf(visitor, "/productos/figura-personalizada-3d")
        result = visitor.post("/productos/figura-personalizada-3d/consulta", data={"alias": "MismoAlias", "message": "Una consulta detallada", "csrf_token": token})
        assert result.status_code == 303
        confirmation = visitor.get("/solicitud-recibida")
        recovery = re.search(r'/recuperar/([A-Za-z0-9_-]+)', confirmation.text).group(1)
        assert "/recuperar/" not in visitor.get("/solicitud-recibida").text
        with Sessions() as db:
            newest = db.scalars(select(Order).order_by(Order.id.desc())).first()
            product_id = newest.id
            assert newest.requester_id != db.get(Order, old_id).requester_id
        assert visitor.get(f"/panel/solicitudes/{old_id}").status_code == 404
        assert outsider.get(f"/panel/solicitudes/{product_id}").status_code == 404

        def login(client, alias, password):
            return client.post("/entrar", data={"alias": alias, "password": password, "csrf_token": csrf(client, "/entrar")})

        assert login(creator, "luna_taller", "incorrecta").status_code == 401
        assert login(creator, "luna_taller", "Clave alumno 123").status_code == 303
        assert login(other_creator, "norte_creativo", "Clave alumno 123").status_code == 303
        assert login(teacher, "docente_demo", "Clave docente 123").status_code == 303
        assert f'/panel/solicitudes/{product_id}"' in creator.get("/panel").text
        assert f'/panel/solicitudes/{product_id}"' not in other_creator.get("/panel").text
        assert other_creator.get(f"/panel/solicitudes/{product_id}").status_code == 404
        assert other_creator.post(f"/panel/solicitudes/{product_id}/mensajes", data={"body": "Mensaje ajeno", "csrf_token": csrf(other_creator, "/panel")}).status_code == 404
        assert creator.post(f"/panel/solicitudes/{product_id}/mensajes", data={"body": "Sin token"}).status_code == 403
        assert creator.post(f"/panel/solicitudes/{product_id}/mensajes", data={"body": "Respuesta <script>alert(1)</script>", "csrf_token": csrf(creator, f"/panel/solicitudes/{product_id}")}).status_code == 303
        detail = visitor.get(f"/panel/solicitudes/{product_id}")
        assert "&lt;script&gt;" in detail.text and "<script>" not in detail.text

        token = csrf(visitor, "/figura-personalizada")
        assert visitor.post("/figura-personalizada", data={"alias": "MismoAlias", "description": "Figura de ejemplo ficticia", "csrf_token": token}).status_code == 303
        with Sessions() as db:
            custom_id = db.scalars(select(Order.id).order_by(Order.id.desc())).first()
            assert db.get(Order, custom_id).recipient_id is None
            student_id = db.scalar(select(User.id).where(User.alias == "norte_creativo"))
        assert creator.post(f"/panel/solicitudes/{custom_id}/asignar", data={"student_id": student_id, "csrf_token": csrf(creator, "/panel")}).status_code == 403
        assert teacher.post(f"/panel/solicitudes/{custom_id}/asignar", data={"student_id": student_id, "csrf_token": csrf(teacher, "/panel")}).status_code == 303
        assert other_creator.get(f"/panel/solicitudes/{custom_id}").status_code == 200
        assert creator.get(f"/panel/solicitudes/{custom_id}").status_code == 404
        with Sessions() as db:
            first_student_id = db.scalar(select(User.id).where(User.alias == "luna_taller"))
        assert teacher.post(f"/panel/solicitudes/{custom_id}/asignar", data={"student_id": first_student_id, "csrf_token": csrf(teacher, "/panel")}).status_code == 303
        assert other_creator.get(f"/panel/solicitudes/{custom_id}").status_code == 404
        assert creator.get(f"/panel/solicitudes/{custom_id}").status_code == 200
        with Sessions() as db:
            assert db.get(Order, custom_id).recipient_id == first_student_id
            assert len(db.scalars(select(Message).where(Message.order_id == product_id)).all()) == 2
        reopened = make_engine(f"sqlite:///{path}")
        with sessionmaker(reopened)() as db:
            assert db.get(Order, custom_id).recipient_id == first_student_id
            assert len(db.scalars(select(Message).where(Message.order_id == product_id)).all()) == 2
        assert visitor.post("/salir", data={"csrf_token": csrf(visitor, "/panel")}).status_code == 303
        assert visitor.get(f"/panel/solicitudes/{product_id}").status_code == 404
        assert visitor.get(f"/recuperar/{recovery}").status_code == 200
        assert visitor.post(f"/recuperar/{recovery}", data={"csrf_token": csrf(visitor, f"/recuperar/{recovery}")}).status_code == 303
        assert visitor.get(f"/panel/solicitudes/{product_id}").status_code == 200
        assert outsider.post(f"/recuperar/{recovery}", data={"csrf_token": csrf(outsider, f"/recuperar/{recovery}")}).status_code == 404
        assert teacher.post("/salir", data={"csrf_token": csrf(teacher, "/panel")}).status_code == 303
        assert teacher.get("/panel").status_code == 303
        assert outsider.post("/recuperar/" + "x" * 43, data={"csrf_token": csrf(outsider, "/entrar")}).status_code == 404
        with Sessions() as db:
            record = db.scalar(select(LoginSession).where(LoginSession.token_hash == fingerprint(creator.cookies.get("ta_session"))))
            record.expires_at = now() - timedelta(seconds=1)
            db.commit()
        assert creator.get("/panel").status_code == 303
        with Sessions() as db:
            db.scalar(select(RecoveryToken).where(RecoveryToken.token_hash == fingerprint(recovery))).expires_at = now() - timedelta(seconds=1)
            db.commit()
        assert outsider.post(f"/recuperar/{recovery}", data={"csrf_token": csrf(outsider, f"/recuperar/{recovery}")}).status_code == 404
    finally:
        app.dependency_overrides.clear()
