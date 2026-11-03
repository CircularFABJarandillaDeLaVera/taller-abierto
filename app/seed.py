"""Carga idempotente de los ocho creadores y cinco productos de demostración."""

from decimal import Decimal

from sqlalchemy import select

from app.database import SessionLocal
from app.models import Product, User, UserRole

CREATORS = [
    ("luna_taller", "Explora formas suaves y objetos cotidianos con mirada curiosa."),
    ("norte_creativo", "Le interesa convertir ideas sencillas en piezas útiles y claras."),
    ("trazo_verde", "Combina diseño, color y materiales responsables en pequeñas series."),
    ("cobre_y_corte", "Disfruta del detalle, la precisión y las composiciones geométricas."),
    ("pixel_de_barro", "Experimenta con volumen, textura y referencias del mundo digital."),
    ("brisa_grafica", "Cuenta historias breves a través de letras, formas y color."),
    ("marco_minimo", "Busca soluciones limpias para organizar y personalizar espacios."),
    ("octava_creativa", "Está descubriendo su estilo y participa en el taller como creador/a."),
]

PRODUCTS = [
    ("luna_taller", "figura-personalizada-3d", "Figura personalizada impresa en 3D", "Una figura de pequeño formato pensada a partir de una idea o personaje elegido.", "Filamento PLA", "24.00", "illustrations/figure.svg"),
    ("norte_creativo", "llavero-personalizado-laser", "Llavero personalizado cortado con láser", "Llavero ligero con nombre, palabra o símbolo para llevar una historia contigo.", "Madera contrachapada", "8.50", "illustrations/keyring.svg"),
    ("trazo_verde", "placa-escritorio-personalizada", "Placa de escritorio personalizada", "Una placa para identificar un espacio de estudio, trabajo o proyecto personal.", "Madera y pintura al agua", "14.00", "illustrations/desk-plate.svg"),
    ("cobre_y_corte", "marcapaginas-grabado", "Marcapáginas grabado", "Marcapáginas duradero con una frase breve o un motivo gráfico grabado.", "Madera de bambú", "7.00", "illustrations/bookmark.svg"),
    ("brisa_grafica", "cartel-decorativo-personalizado", "Cartel decorativo personalizado", "Composición decorativa para una habitación, evento o rincón especial.", "Cartulina de alto gramaje", "18.00", "illustrations/poster.svg"),
]


def seed_catalog() -> tuple[int, int]:
    """Crea solo registros ausentes; no borra ni reemplaza datos existentes."""
    created_users = created_products = 0
    with SessionLocal() as session:
        users: dict[str, User] = {}
        for alias, presentation in CREATORS:
            user = session.scalar(select(User).where(User.alias == alias))
            if user is None:
                user = User(alias=alias, presentation=presentation, role=UserRole.STUDENT)
                session.add(user)
                session.flush()
                created_users += 1
            users[alias] = user
        for alias, slug, name, description, material, price, image_path in PRODUCTS:
            if session.scalar(select(Product).where(Product.slug == slug)) is None:
                session.add(Product(creator_id=users[alias].id, slug=slug, name=name, description=description, material=material, indicative_price=Decimal(price), image_path=image_path))
                created_products += 1
        session.commit()
    return created_users, created_products


if __name__ == "__main__":
    users, products = seed_catalog()
    print(f"Catálogo demo: {users} creadores nuevos, {products} productos nuevos.")

