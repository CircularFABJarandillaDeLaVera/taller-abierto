"""Altas y permisos con personas ficticias y una base SQLite aislada."""

import re
import sys
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from app.accounts_service import AccountError, allowed_new_roles, create_account
import app.admin_setup as admin_setup
from app.database import Base, get_db, make_engine
from app.identity import check_password, fingerprint, hash_password, new_session
from app.main import app
from app.models import LoginSession, Message, Order, OrderKind, OrderStatus, Product, User, UserRole


@pytest.fixture
def accounts(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'cuentas.db'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    with sessions() as db:
        admin = User(alias="administracion", role=UserRole.ADMIN, password_hash=hash_password("Clave admin ficticia"))
        manager = User(alias="responsable", role=UserRole.TEACHER, password_hash=hash_password("Clave responsable ficticia"))
        artisan = User(alias="artesano", role=UserRole.STUDENT, password_hash=hash_password("Clave artesano ficticia"))
        unlinked = User(alias="perfil_previo", role=UserRole.STUDENT, presentation="Perfil existente")
        visitor = User(alias="visitante_ficticio", role=UserRole.VISITOR)
        db.add_all([admin, manager, artisan, unlinked, visitor])
        db.flush()
        product = Product(creator_id=unlinked.id, slug="pieza-existente", name="Pieza", description="Ejemplo", material="PLA", indicative_price=Decimal("10.00"), image_path="illustrations/figure.svg")
        db.add(product)
        db.flush()
        order = Order(kind=OrderKind.CUSTOM_FIGURE, status=OrderStatus.RECEIVED, requester_id=visitor.id, recipient_id=unlinked.id, requester_alias="Cliente", description="Encargo ficticio", visitor_access_enabled=True)
        db.add(order)
        db.flush()
        db.add(Message(order_id=order.id, author_id=visitor.id, body="Mensaje conservado"))
        db.commit()
        ids = {person.alias: person.id for person in (admin, manager, artisan, unlinked, visitor)}
        tokens = {person.alias: new_session(db, person) for person in (admin, manager, artisan, visitor)}
        order_id = order.id

    def override_db():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    try:
        yield sessions, ids, tokens, order_id
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def _client(token):
    client = TestClient(app, follow_redirects=False)
    client.cookies.set("ta_session", token)
    return client


def _csrf(client, path="/panel"):
    page = client.get(path)
    assert page.status_code == 200
    return re.search(r'name="csrf_token" value="([^"]+)"', page.text).group(1)


def test_account_service_role_matrix_and_duplicate(accounts):
    sessions, ids, _, _ = accounts
    with sessions() as db:
        actors = {name: db.get(User, ids[name]) for name in ("administracion", "responsable", "artesano", "visitante_ficticio")}
        assert allowed_new_roles(actors["administracion"]) == (UserRole.TEACHER, UserRole.STUDENT)
        assert allowed_new_roles(actors["responsable"]) == (UserRole.STUDENT,)
        assert allowed_new_roles(actors["artesano"]) == ()
        assert allowed_new_roles(actors["visitante_ficticio"]) == ()
        for actor, forbidden in ((actors["administracion"], "admin"), (actors["responsable"], "teacher"), (actors["responsable"], "admin"), (actors["artesano"], "student"), (actors["visitante_ficticio"], "student")):
            with pytest.raises(AccountError) as error:
                create_account(db, actor, role_name=forbidden, mode="new", alias="nuevo_perfil")
            assert error.value.status_code == 403
        with pytest.raises(AccountError) as error:
            create_account(db, actors["responsable"], role_name="student", mode="new", alias="PERFIL_PREVIO")
        assert error.value.status_code == 409
        assert db.scalar(select(func.count()).select_from(User).where(User.alias == "nuevo_perfil")) == 0


def test_account_forms_link_create_reset_and_permissions(accounts):
    sessions, ids, tokens, order_id = accounts
    admin = _client(tokens["administracion"])
    manager = _client(tokens["responsable"])
    artisan = _client(tokens["artesano"])
    visitor = _client(tokens["visitante_ficticio"])

    admin_page = admin.get("/panel/cuentas")
    manager_page = manager.get("/panel/cuentas")
    assert admin_page.status_code == manager_page.status_code == 200
    assert 'value="teacher"' in admin_page.text and 'value="teacher"' not in manager_page.text
    assert artisan.get("/panel/cuentas").status_code == 403
    assert visitor.get("/panel/cuentas").status_code == 403

    for client, role in ((manager, "teacher"), (manager, "admin"), (artisan, "student"), (visitor, "student"), (admin, "admin")):
        response = client.post("/panel/cuentas/alta", data={"role": role, "mode": "new", "alias": "rol_forzado", "csrf_token": _csrf(client)})
        assert response.status_code == 403

    linked = manager.post("/panel/cuentas/alta", data={"role": "student", "mode": "existing", "existing_user_id": ids["perfil_previo"], "csrf_token": _csrf(manager, "/panel/cuentas")})
    assert linked.status_code == 200 and "No volverá a mostrarse" in linked.text
    temporary = re.search(r"<code>([^<]+)</code>", linked.text).group(1)
    with sessions() as db:
        person = db.get(User, ids["perfil_previo"])
        assert check_password(temporary, person.password_hash)
        assert person.password_hash != temporary
        assert db.scalar(select(Product.creator_id).where(Product.slug == "pieza-existente")) == person.id
        assert db.get(Order, order_id).recipient_id == person.id
        assert db.scalar(select(Message.body).where(Message.order_id == order_id)) == "Mensaje conservado"
        assert db.scalar(select(func.count()).select_from(User).where(User.alias == "perfil_previo")) == 1
    assert temporary not in manager.get("/panel/cuentas").text

    duplicate = manager.post("/panel/cuentas/alta", data={"role": "student", "mode": "new", "alias": "perfil_previo", "csrf_token": _csrf(manager, "/panel/cuentas")})
    assert duplicate.status_code == 409 and "Ese alias ya existe" in duplicate.text
    created = admin.post("/panel/cuentas/alta", data={"role": "teacher", "mode": "new", "alias": "responsable_dos", "csrf_token": _csrf(admin, "/panel/cuentas")})
    assert created.status_code == 200
    artisan_created = manager.post("/panel/cuentas/alta", data={"role": "student", "mode": "new", "alias": "artesana_nueva", "csrf_token": _csrf(manager, "/panel/cuentas")})
    assert artisan_created.status_code == 200
    admin_artisan = admin.post("/panel/cuentas/alta", data={"role": "student", "mode": "new", "alias": "artesano_admin", "csrf_token": _csrf(admin, "/panel/cuentas")})
    assert admin_artisan.status_code == 200
    with sessions() as db:
        second = db.scalar(select(User).where(User.alias == "responsable_dos"))
        assert second.role == UserRole.TEACHER and second.password_hash
        assert db.scalar(select(User.role).where(User.alias == "artesana_nueva")) == UserRole.STUDENT
        assert db.scalar(select(User.role).where(User.alias == "artesano_admin")) == UserRole.STUDENT
        second_id = second.id
    assert manager.post(f"/panel/cuentas/{second_id}/restablecer", data={"csrf_token": _csrf(manager, "/panel/cuentas")}).status_code == 403
    assert admin.post(f"/panel/cuentas/{ids['administracion']}/restablecer", data={"csrf_token": _csrf(admin, "/panel/cuentas")}).status_code == 403

    old_session = tokens["artesano"]
    reset = manager.post(f"/panel/cuentas/{ids['artesano']}/restablecer", data={"csrf_token": _csrf(manager, "/panel/cuentas")})
    assert reset.status_code == 200
    with sessions() as db:
        assert db.scalar(select(LoginSession).where(LoginSession.token_hash == fingerprint(old_session))) is None
    assert artisan.get("/panel").status_code == 303

    disabled = manager.post(f"/panel/cuentas/{ids['perfil_previo']}/estado", data={"active": "0", "csrf_token": _csrf(manager, "/panel/cuentas")})
    assert disabled.status_code == 303
    with sessions() as db:
        assert not db.get(User, ids["perfil_previo"]).is_active
    assert manager.post(f"/panel/cuentas/{second_id}/estado", data={"active": "0", "csrf_token": _csrf(manager, "/panel/cuentas")}).status_code == 403


def test_change_own_password_revokes_sessions(accounts):
    sessions, ids, tokens, _ = accounts
    artisan = _client(tokens["artesano"])
    bad = artisan.post("/panel/clave", data={"current_password": "incorrecta", "new_password": "Nueva clave ficticia", "confirmation": "Nueva clave ficticia", "csrf_token": _csrf(artisan, "/panel/clave")})
    assert bad.status_code == 422
    changed = artisan.post("/panel/clave", data={"current_password": "Clave artesano ficticia", "new_password": "Nueva clave ficticia", "confirmation": "Nueva clave ficticia", "csrf_token": _csrf(artisan, "/panel/clave")})
    assert changed.status_code == 200 and "cerraron tus sesiones" in changed.text
    with sessions() as db:
        assert check_password("Nueva clave ficticia", db.get(User, ids["artesano"]).password_hash)
    assert artisan.get("/panel").status_code == 303


def test_admin_setup_requires_named_existing_responsible(tmp_path, monkeypatch):
    engine = make_engine(f"sqlite:///{tmp_path / 'habilitacion.db'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine)
    with sessions() as db:
        person = User(alias="mi_cuenta", role=UserRole.TEACHER, password_hash=hash_password("Clave ficticia suficiente"))
        db.add(person)
        db.commit()
        user_id = person.id
        old_session = new_session(db, person)
    monkeypatch.setattr(admin_setup, "SessionLocal", sessions)
    monkeypatch.setattr(sys, "argv", ["admin_setup", "mi_cuenta"])
    monkeypatch.setattr("builtins.input", lambda _: "confirmación incorrecta")
    with pytest.raises(SystemExit):
        admin_setup.main()
    with sessions() as db:
        assert db.get(User, user_id).role == UserRole.TEACHER
    monkeypatch.setattr("builtins.input", lambda _: f"HABILITAR ADMIN mi_cuenta #{user_id}")
    admin_setup.main()
    with sessions() as db:
        assert db.get(User, user_id).role == UserRole.ADMIN
        assert db.get(User, user_id).password_hash is not None
        assert db.scalar(select(LoginSession).where(LoginSession.token_hash == fingerprint(old_session))) is None
    engine.dispose()
