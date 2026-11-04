"""Importación revisable de productos públicos desde CSV, sin crear cuentas."""

import argparse
import csv
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Product, User, UserRole


FIELDS = ("slug", "artisan_alias", "name", "description", "material", "indicative_price", "image_path")
STATIC_PRODUCTS = Path(__file__).resolve().parent / "static" / "products"
SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
IMAGE = re.compile(r"products/[a-zA-Z0-9][a-zA-Z0-9._/-]*\.(?:jpg|jpeg|png|webp)\Z", re.IGNORECASE)


@dataclass(frozen=True)
class Item:
    line: int
    slug: str
    artisan_alias: str
    name: str
    description: str
    material: str
    price: Decimal
    image_path: str


class ImportErrorDetails(ValueError):
    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("\n".join(errors))


def _image_ok(image_path: str) -> bool:
    if not IMAGE.fullmatch(image_path) or ".." in Path(image_path).parts:
        return False
    path = (STATIC_PRODUCTS.parent / image_path).resolve()
    if not path.is_relative_to(STATIC_PRODUCTS.resolve()) or not path.is_file():
        return False
    if path.stat().st_size > 10 * 1024 * 1024:
        return False
    with path.open("rb") as file:
        head = file.read(16)
    suffix = path.suffix.lower()
    return (suffix in (".jpg", ".jpeg") and head.startswith(b"\xff\xd8\xff")) or (suffix == ".png" and head.startswith(b"\x89PNG\r\n\x1a\n")) or (suffix == ".webp" and head[:4] == b"RIFF" and head[8:12] == b"WEBP")


def read_items(csv_path: Path) -> list[Item]:
    errors: list[str] = []
    items: list[Item] = []
    seen: set[str] = set()
    with csv_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file, strict=True)
        if reader.fieldnames != list(FIELDS):
            raise ImportErrorDetails(["Cabecera CSV incorrecta; usa exactamente las columnas de la plantilla y en ese orden."])
        for line, row in enumerate(reader, start=2):
            if None in row or any(value is None for value in row.values()):
                errors.append(f"Fila {line}: número de columnas incorrecto.")
                continue
            values = {key: value.strip() for key, value in row.items()}
            slug, alias, name, description, material, price_text, image_path = (values[key] for key in FIELDS)
            if not SLUG.fullmatch(slug) or len(slug) > 180:
                errors.append(f"Fila {line}: slug inválido (minúsculas, números y guiones; máximo 180).")
            if slug in seen:
                errors.append(f"Fila {line}: slug repetido en el CSV: {slug}.")
            seen.add(slug)
            if not alias or len(alias) > 80:
                errors.append(f"Fila {line}: alias de artesano vacío o demasiado largo.")
            for label, value, limit in (("name", name, 160), ("description", description, 5000), ("material", material, 160)):
                if not value or len(value) > limit:
                    errors.append(f"Fila {line}: {label} vacío o demasiado largo (máximo {limit}).")
            try:
                if not re.fullmatch(r"[0-9]+(?:\.[0-9]{1,2})?", price_text):
                    raise InvalidOperation
                price = Decimal(price_text)
                if not price.is_finite() or price <= 0 or price.as_tuple().exponent < -2 or price > Decimal("99999999.99"):
                    raise InvalidOperation
            except (InvalidOperation, ValueError):
                errors.append(f"Fila {line}: precio inválido; usa un importe positivo con punto y hasta dos decimales.")
                price = Decimal("0")
            if len(image_path) > 255 or not _image_ok(image_path):
                errors.append(f"Fila {line}: imagen no válida o ausente en app/static/products/.")
            items.append(Item(line, slug, alias, name, description, material, price, image_path))
    if not items:
        errors.append("El CSV no contiene productos.")
    if errors:
        raise ImportErrorDetails(errors)
    return items


def import_items(db: Session, items: list[Item], *, apply: bool = False) -> tuple[int, int]:
    """Valida el lote completo; crea solo slugs ausentes y nunca cambia los existentes."""
    aliases = {item.artisan_alias for item in items}
    slugs = {item.slug for item in items}
    users = {user.alias: user for user in db.scalars(select(User).where(User.alias.in_(aliases)))}
    existing = {product.slug: product for product in db.scalars(select(Product).where(Product.slug.in_(slugs)))}
    errors: list[str] = []
    pending: list[tuple[Item, User]] = []
    skipped = 0
    for item in items:
        artisan = users.get(item.artisan_alias)
        if artisan is None or artisan.role != UserRole.STUDENT or not artisan.is_active:
            errors.append(f"Fila {item.line}: @{item.artisan_alias} no es un perfil de artesano activo existente.")
            continue
        product = existing.get(item.slug)
        if product is not None:
            if (product.creator_id, product.name, product.description, product.material, product.indicative_price, product.image_path) != (artisan.id, item.name, item.description, item.material, item.price, item.image_path):
                errors.append(f"Fila {item.line}: el slug {item.slug} ya existe con datos distintos; revisa el conflicto manualmente.")
            else:
                skipped += 1
        else:
            pending.append((item, artisan))
    if errors:
        raise ImportErrorDetails(errors)
    if apply:
        for item, artisan in pending:
            db.add(Product(creator_id=artisan.id, slug=item.slug, name=item.name, description=item.description, material=item.material, indicative_price=item.price, image_path=item.image_path))
        db.commit()
    return len(pending), skipped


def main() -> None:
    parser = argparse.ArgumentParser(description="Validar o importar productos públicos del aula")
    parser.add_argument("csv_file", type=Path)
    parser.add_argument("--apply", action="store_true", help="Guardar tras validar el lote completo")
    args = parser.parse_args()
    try:
        items = read_items(args.csv_file)
        with SessionLocal() as db:
            created, skipped = import_items(db, items, apply=args.apply)
    except (ImportErrorDetails, OSError, csv.Error) as error:
        parser.exit(1, f"Importación cancelada:\n{error}\n")
    print(f"{'Importados' if args.apply else 'Listos para importar'}: {created}; ya idénticos: {skipped}.")


if __name__ == "__main__":
    main()
