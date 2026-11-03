"""Lectura individual y avisos con bases efímeras, sin tocar encargos de trabajo."""

import re

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db, make_engine
from app.identity import new_recovery, new_session
from app.main import app
from app.models import Message, Order, OrderKind, OrderRead, OrderStatus, User, UserRole


def test_personal_reading_assignment_and_recovery(tmp_path):
    path = tmp_path / "novedades.db"
    engine = make_engine(f"sqlite:///{path}")
    Base.metadata.create_all(engine)
    Sessions = sessionmaker(engine, expire_on_commit=False)
    with Sessions() as db:
        visitor = User(alias="visitante_novedades", role=UserRole.VISITOR)
        first = User(alias="creador_uno", role=UserRole.STUDENT)
        second = User(alias="creador_dos", role=UserRole.STUDENT)
        teacher = User(alias="docente_novedades", role=UserRole.TEACHER)
        db.add_all([visitor, first, second, teacher])
        db.flush()
        order = Order(kind=OrderKind.CUSTOM_FIGURE, status=OrderStatus.RECEIVED, requester_id=visitor.id, requester_alias="Alias de prueba", description="Figura ficticia", visitor_access_enabled=True)
        db.add(order)
        db.flush()
        db.add(Message(order_id=order.id, author_id=visitor.id, body="Mensaje inicial ficticio"))
        db.commit()
        order_id = order.id
        users = {"visitor": visitor, "first": first, "second": second, "teacher": teacher}
        sessions = {key: new_session(db, user) for key, user in users.items()}

    def override_db():
        with Sessions() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    clients = {key: TestClient(app, follow_redirects=False) for key in users}
    for key, client in clients.items():
        client.cookies.set("ta_session", sessions[key])

    def news(key):
        result = clients[key].get("/panel/novedades")
        assert result.status_code == 200 and result.headers["cache-control"] == "no-store"
        return result.json()

    def token(key, url="/panel"):
        html = clients[key].get(url).text
        return re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)

    def cursor(key):
        html = clients[key].get(f"/panel/solicitudes/{order_id}").text
        return re.search(r'data-read-cursor="([^"]+)"', html).group(1)

    def read(key, read_cursor=None):
        html = clients[key].get(f"/panel/solicitudes/{order_id}").text
        csrf = re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)
        return clients[key].post(f"/panel/solicitudes/{order_id}/lectura", data={"csrf_token": csrf, "read_cursor": read_cursor or re.search(r'data-read-cursor="([^"]+)"', html).group(1)})

    try:
        assert news("teacher")["items"][0]["label"] == "Nueva sin asignar"
        assert news("visitor")["count"] == 0
        assert order_id in [card["order_id"] for card in news("visitor")["cards"]]  # Visible sin aviso.
        assert news("first")["count"] == 0
        assert order_id not in [card["order_id"] for card in news("first")["cards"]]
        assert clients["teacher"].get(f"/panel/solicitudes/{order_id}").status_code == 200
        assert news("teacher")["count"] == 1  # Consultar y abrir HTML no muta lectura.
        assert clients["teacher"].post(f"/panel/solicitudes/{order_id}/lectura", data={"read_cursor": cursor("teacher")}).status_code == 403
        assert read("teacher").status_code == 200
        assert news("teacher")["count"] == 0
        assert order_id in [card["order_id"] for card in news("teacher")["cards"]]
        assert clients["first"].get(f"/panel/solicitudes/{order_id}").status_code == 404
        assert clients["first"].get(f"/panel/solicitudes/{order_id}/mensajes/nuevos").status_code == 404
        with Sessions() as db:
            first_id = users["first"].id
            second_id = users["second"].id
        assign_url = f"/panel/solicitudes/{order_id}/asignar"
        assert clients["first"].post(assign_url, data={"student_id": first_id, "csrf_token": token("first")}).status_code == 403
        assert clients["teacher"].post(assign_url, data={"student_id": first_id}).status_code == 403
        assert clients["teacher"].post(assign_url, data={"student_id": first_id, "csrf_token": token("teacher")}).status_code == 303
        assert news("first")["items"][0]["label"] == "Nueva para ti"
        assert order_id in [card["order_id"] for card in news("first")["cards"]]
        assert news("first")["items"][0]["unread_messages"] == 0
        assert news("teacher")["count"] == 0
        assert read("first").status_code == 200
        assert news("first")["count"] == 0
        assert order_id in [card["order_id"] for card in news("first")["cards"]]
        reply = f"/panel/solicitudes/{order_id}/mensajes"
        assert clients["first"].post(reply, data={"body": "Respuesta nueva", "csrf_token": token("first")}).status_code == 303
        assert news("first")["count"] == 0
        assert news("visitor")["items"][0]["label"] == "1 mensaje nuevo"
        assert news("teacher")["items"][0]["label"] == "1 mensaje nuevo"
        snapshot = clients["visitor"].get(f"/panel/solicitudes/{order_id}")
        cutoff = int(re.search(r'data-shown-id="(\d+)"', snapshot.text).group(1))
        read_cursor = re.search(r'data-read-cursor="([^"]+)"', snapshot.text).group(1)
        assert cutoff == 2 and news("visitor")["count"] == 1
        with Sessions() as db:
            db.add(Message(order_id=order_id, author_id=first_id, body="Llegó después del HTML"))
            db.commit()
        assert read("visitor", read_cursor).status_code == 200
        assert news("visitor")["items"][0]["label"] == "1 mensaje nuevo"
        assert read("visitor", read_cursor[:-1] + ("a" if read_cursor[-1] != "a" else "b")).status_code == 422
        assert clients["visitor"].post(f"/panel/solicitudes/{order_id}/lectura", data={"read_cursor": read_cursor}).status_code == 403
        assert read("visitor", read_cursor).status_code == 200  # Reintento idempotente.
        assert news("visitor")["count"] == 1
        newer = clients["visitor"].get(f"/panel/solicitudes/{order_id}/mensajes/nuevos?despues={cutoff}").json()
        assert len(newer["messages"]) == 1
        assert read("visitor", newer["read_cursor"]).status_code == 200
        assert news("visitor")["count"] == 0
        assert news("teacher")["items"][0]["label"] == "2 mensajes nuevos"
        assert clients["teacher"].post(assign_url, data={"student_id": second_id, "csrf_token": token("teacher")}).status_code == 303
        assert news("first")["count"] == 0
        assert order_id not in [card["order_id"] for card in news("first")["cards"]]
        assert clients["first"].get(f"/panel/solicitudes/{order_id}").status_code == 404
        assert clients["first"].post(f"/panel/solicitudes/{order_id}/lectura", data={"read_cursor": read_cursor, "csrf_token": token("first")}).status_code == 404
        assert clients["second"].get(f"/panel/solicitudes/{order_id}").status_code == 200
        assert news("second")["items"][0]["label"] == "Nueva para ti"
        assert read("second").status_code == 200
        assert news("second")["count"] == 0
        assert clients["second"].post(reply, data={"body": "Mensaje de segundo creador", "csrf_token": token("second")}).status_code == 303
        assert news("visitor")["count"] == 1
        assert read("visitor").status_code == 200
        assert news("visitor")["count"] == 0
        with Sessions() as db:
            recovery = new_recovery(db, db.get(Order, order_id))
        assert clients["visitor"].post("/salir", data={"csrf_token": token("visitor")}).status_code == 303
        assert clients["visitor"].get("/panel/novedades").status_code == 401
        recover_url = f"/recuperar/{recovery}"
        assert clients["visitor"].post(recover_url, data={"csrf_token": token("visitor", recover_url)}).status_code == 303
        assert news("visitor")["count"] == 0
        with Sessions() as db:
            assert db.get(Order, order_id).status == OrderStatus.IN_CONVERSATION
            assert db.scalar(select(OrderRead).where(OrderRead.order_id == order_id, OrderRead.user_id == users["visitor"].id)).last_read_message_id == 4
        reopened = make_engine(f"sqlite:///{path}")
        with sessionmaker(reopened)() as db:
            assert db.get(Order, order_id).recipient_id == second_id
            assert db.scalar(select(OrderRead).where(OrderRead.order_id == order_id, OrderRead.user_id == users["visitor"].id)).last_read_message_id == 4
    finally:
        app.dependency_overrides.clear()


def test_migration_initializes_history_without_changing_it(tmp_path):
    path = tmp_path / "historial.db"
    url = f"sqlite:///{path}"
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "0005_private_photos")
    engine = make_engine(url)
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO users (id, alias, role, is_active) VALUES (1,'visitante','VISITOR',1),(2,'creador','STUDENT',1),(3,'docente','TEACHER',1)"))
        connection.execute(text("INSERT INTO orders (id,kind,status,requester_id,recipient_id,description,requester_alias,visitor_access_enabled) VALUES (1,'CUSTOM_FIGURE','RECEIVED',1,2,'Descripción intacta','Prueba',1)"))
        connection.execute(text("INSERT INTO messages (id,order_id,author_id,body) VALUES (1,1,1,'Mensaje intacto')"))
        connection.execute(text("INSERT INTO photo_consents (id,order_id,accepted_by_id,text_version) VALUES (1,1,1,'fotografias-v1-2026-11')"))
        connection.execute(text("INSERT INTO attachments (id,order_id,uploaded_by_id,source,stored_name,original_name,mime_type,size_bytes,consent_id) VALUES (1,1,1,'REQUESTER','nombre-interno.png','foto.png','image/png',3,1)"))
    command.upgrade(cfg, "head")
    with engine.connect() as connection:
        assert connection.execute(text("SELECT body FROM messages WHERE id=1")).scalar() == "Mensaje intacto"
        assert connection.execute(text("SELECT description FROM orders WHERE id=1")).scalar() == "Descripción intacta"
        assert connection.execute(text("SELECT COUNT(*) FROM attachments WHERE consent_id=1")).scalar() == 1
        assert connection.execute(text("SELECT COUNT(*) FROM photo_consents")).scalar() == 1
        assert connection.execute(text("SELECT COUNT(*) FROM order_reads WHERE order_id=1 AND last_read_message_id=1")).scalar() == 3
        assert connection.execute(text("SELECT assignment_version FROM orders WHERE id=1")).scalar() == 0
    with sessionmaker(engine)() as db:
        for user_id in (1, 2, 3):
            from app.notifications import overview
            assert overview(db, db.get(User, user_id))[1] == {}
