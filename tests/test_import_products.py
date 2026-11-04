"""Importación de productos con CSV, imágenes y base ficticios aislados."""

import csv
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from app.database import Base, make_engine
from app.import_products import FIELDS, ImportErrorDetails, import_items, read_items
from app.models import Order, OrderKind, OrderStatus, Product, User, UserRole


def _csv(path, rows):
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(FIELDS)
        writer.writerows(rows)


def test_product_import_validates_then_applies_idempotently(tmp_path, monkeypatch):
    static = tmp_path / "static" / "products"
    static.mkdir(parents=True)
    (static / "foto.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"imagen ficticia")
    monkeypatch.setattr("app.import_products.STATIC_PRODUCTS", static)
    csv_path = tmp_path / "productos.csv"
    row = ("pieza-nueva", "artesana", "Pieza nueva", "Descripción pública", "PLA", "12.50", "products/foto.png")
    _csv(csv_path, [row])
    engine = make_engine(f"sqlite:///{tmp_path / 'productos.db'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    with sessions() as db:
        artisan = User(alias="artesana", role=UserRole.STUDENT)
        visitor = User(alias="visitante", role=UserRole.VISITOR)
        db.add_all([artisan, visitor])
        db.flush()
        prior = Product(creator_id=artisan.id, slug="pieza-anterior", name="Anterior", description="Conservar", material="PLA", indicative_price=Decimal("8.00"), image_path="illustrations/figure.svg")
        db.add(prior)
        db.flush()
        order = Order(kind=OrderKind.PRODUCT_INQUIRY, status=OrderStatus.RECEIVED, requester_id=visitor.id, recipient_id=artisan.id, product_id=prior.id, description="Consulta previa")
        db.add(order)
        db.commit()
        prior_id, order_id, artisan_id = prior.id, order.id, artisan.id
    items = read_items(csv_path)
    with sessions() as db:
        assert import_items(db, items) == (1, 0)
        assert db.scalar(select(func.count()).select_from(Product)) == 1
        assert import_items(db, items, apply=True) == (1, 0)
        assert db.scalar(select(Product.creator_id).where(Product.slug == "pieza-nueva")) == artisan_id
        assert db.get(Product, prior_id).name == "Anterior"
        assert db.get(Order, order_id).product_id == prior_id
        assert import_items(db, items, apply=True) == (0, 1)
        assert db.scalar(select(func.count()).select_from(Product)) == 2
    engine.dispose()


def test_product_import_rejects_whole_batch_on_bad_alias_or_conflict(tmp_path, monkeypatch):
    static = tmp_path / "static" / "products"
    static.mkdir(parents=True)
    (static / "foto.jpg").write_bytes(b"\xff\xd8\xffimagen ficticia")
    monkeypatch.setattr("app.import_products.STATIC_PRODUCTS", static)
    csv_path = tmp_path / "productos.csv"
    engine = make_engine(f"sqlite:///{tmp_path / 'productos.db'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine)
    with sessions() as db:
        db.add_all([User(alias="artesana", role=UserRole.STUDENT), User(alias="responsable", role=UserRole.TEACHER)])
        db.commit()
    valid = ("pieza-valida", "artesana", "Pieza", "Descripción", "PLA", "10.00", "products/foto.jpg")
    invalid = ("pieza-invalida", "responsable", "Otra", "Descripción", "PLA", "11.00", "products/foto.jpg")
    _csv(csv_path, [valid, invalid])
    with sessions() as db:
        with pytest.raises(ImportErrorDetails, match="no es un perfil de artesano"):
            import_items(db, read_items(csv_path), apply=True)
        assert db.scalar(select(func.count()).select_from(Product)) == 0
    _csv(csv_path, [valid, valid])
    with pytest.raises(ImportErrorDetails, match="slug repetido"):
        read_items(csv_path)
    _csv(csv_path, [valid])
    with sessions() as db:
        assert import_items(db, read_items(csv_path), apply=True) == (1, 0)
    _csv(csv_path, [("pieza-valida", "artesana", "Título cambiado", "Descripción", "PLA", "10.00", "products/foto.jpg")])
    with sessions() as db:
        with pytest.raises(ImportErrorDetails, match="datos distintos"):
            import_items(db, read_items(csv_path), apply=True)
        assert db.scalar(select(Product.name).where(Product.slug == "pieza-valida")) == "Pieza"
    engine.dispose()


def test_product_import_rejects_missing_or_unsafe_image(tmp_path, monkeypatch):
    static = tmp_path / "static" / "products"
    static.mkdir(parents=True)
    monkeypatch.setattr("app.import_products.STATIC_PRODUCTS", static)
    csv_path = tmp_path / "productos.csv"
    base = ("pieza", "artesana", "Pieza", "Descripción", "PLA", "10.00")
    for path in ("products/ausente.jpg", "products/../privada.jpg", "../private_uploads/foto.jpg"):
        _csv(csv_path, [(*base, path)])
        with pytest.raises(ImportErrorDetails, match="imagen no válida"):
            read_items(csv_path)
