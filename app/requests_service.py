"""Validación y creación atómica de solicitudes locales ficticias."""
import re
import secrets
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import Message, Order, OrderKind, OrderStatus, Product, User, UserRole, RecoveryToken
from app.identity import fingerprint, now, RECOVERY_HOURS
from datetime import timedelta
from app.photos import PreparedPhoto, save_batch, clean_written


class InvalidRequest(ValueError):
    pass


def validate(alias: str, message: str, offer: str = "") -> tuple[str, str, int | None]:
    alias, message, offer = alias.strip(), message.strip(), offer.strip()
    if not 2 <= len(alias) <= 80 or any(ord(c) < 32 for c in alias):
        raise InvalidRequest("El alias debe tener entre 2 y 80 caracteres.")
    if not 10 <= len(message) <= 2000:
        raise InvalidRequest("La descripción o mensaje debe tener entre 10 y 2000 caracteres.")
    if offer and not re.fullmatch(r"[0-9]{1,7}(?:[.,][0-9]{1,2})?", offer):
        raise InvalidRequest("Indica un importe positivo con hasta dos decimales.")
    cents = int(Decimal(offer.replace(",", ".")) * 100) if offer else None
    if cents is not None and cents <= 0:
        raise InvalidRequest("El importe debe ser mayor que cero.")
    return alias, message, cents


def create_request(db: Session, *, alias: str, message: str, kind: OrderKind, product: Product | None = None, offer: str = "", visitor: User | None = None, photos: list[PreparedPhoto] | None = None) -> tuple[Order, str]:
    alias, message, cents = validate(alias, message, offer)
    if kind == OrderKind.PRODUCT_INQUIRY and product is None:
        raise InvalidRequest("El producto no existe.")
    if kind == OrderKind.CUSTOM_FIGURE and (product is not None or cents is not None):
        raise InvalidRequest("Esta solicitud no admite producto ni oferta.")
    written = []
    try:
        # Identificador interno aleatorio por solicitud: el alias escrito no concede acceso.
        if visitor is None or visitor.role != UserRole.VISITOR:
            visitor = User(alias="visitante_" + secrets.token_hex(16), role=UserRole.VISITOR)
            db.add(visitor)
            db.flush()
        order = Order(kind=kind, status=OrderStatus.RECEIVED, requester_id=visitor.id,
                      requester_alias=alias, recipient_id=product.creator_id if product else None,
                      product_id=product.id if product else None, description=message, offer_cents=cents, visitor_access_enabled=True)
        db.add(order)
        db.flush()
        db.add(Message(order_id=order.id, author_id=visitor.id, body=message))
        recovery = secrets.token_urlsafe(32)
        db.add(RecoveryToken(token_hash=fingerprint(recovery), order_id=order.id, expires_at=now() + timedelta(hours=RECOVERY_HOURS)))
        save_batch(db, order, visitor, photos or [], written)
        db.commit()
        return order, recovery
    except Exception:
        db.rollback()
        clean_written(written)
        raise
