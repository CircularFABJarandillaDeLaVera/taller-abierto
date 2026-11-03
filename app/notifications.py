"""Novedades por persona y conversación, independientes del estado del encargo."""

from dataclasses import dataclass

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session, selectinload

from app.models import Message, Order, OrderKind, OrderRead, User, UserRole
from app.presentation import activity_date


@dataclass(frozen=True)
class Notice:
    order_id: int
    label: str
    unread_messages: int
    kind: str


def visible_orders(db: Session, user: User) -> list[Order]:
    query = select(Order).options(selectinload(Order.recipient), selectinload(Order.product))
    if user.role == UserRole.STUDENT:
        query = query.where(Order.recipient_id == user.id)
    elif user.role == UserRole.VISITOR:
        query = query.where(Order.requester_id == user.id, Order.visitor_access_enabled.is_(True))
    return db.scalars(query).all()


def notice_for(order: Order, user: User, read: OrderRead | None) -> Notice | None:
    if user.role == UserRole.STUDENT and order.recipient_id == user.id and (
        read is None or read.seen_assignment_version < order.assignment_version
    ):
        return Notice(order.id, "Nueva para ti", 0, "assignment")
    if user.role == UserRole.TEACHER and order.kind == OrderKind.CUSTOM_FIGURE and order.recipient_id is None and read is None:
        return Notice(order.id, "Nueva sin asignar", 0, "unassigned")
    cutoff = read.last_read_message_id if read and read.last_read_message_id else 0
    count = getattr(order, "_news_unread", None)
    if count is None:
        count = sum(message.id > cutoff and message.author_id != user.id for message in order.messages)
    if count:
        return Notice(order.id, f"{count} mensaje{'s' if count != 1 else ''} nuevo{'s' if count != 1 else ''}", count, "messages")
    return None


def overview(db: Session, user: User) -> tuple[list[Order], dict[int, Notice]]:
    orders = visible_orders(db, user)
    if not orders:
        return [], {}
    ids = [order.id for order in orders]
    reads = {row.order_id: row for row in db.scalars(select(OrderRead).where(OrderRead.user_id == user.id, OrderRead.order_id.in_(ids)))}
    activities = {row[0]: row[1] for row in db.execute(select(Message.order_id, func.max(Message.created_at)).where(Message.order_id.in_(ids)).group_by(Message.order_id))}
    counts = {row[0]: row[1] for row in db.execute(
        select(Message.order_id, func.count(Message.id))
        .outerjoin(OrderRead, and_(OrderRead.order_id == Message.order_id, OrderRead.user_id == user.id))
        .where(Message.order_id.in_(ids), Message.author_id != user.id, Message.id > func.coalesce(OrderRead.last_read_message_id, 0))
        .group_by(Message.order_id)
    )}
    for order in orders:
        order._news_unread = counts.get(order.id, 0)
        order._news_activity = max(order.created_at, activities.get(order.id) or order.created_at)
    notices = {order.id: notice for order in orders if (notice := notice_for(order, user, reads.get(order.id))) is not None}
    orders.sort(key=lambda order: (order.id in notices, activity_date(order), order.id), reverse=True)
    return orders, notices


def mark_shown(db: Session, order: Order, user: User, shown_message_id: int | None) -> None:
    """Guarda solo el último mensaje que la respuesta ha incluido, nunca el máximo futuro."""
    read = db.scalar(select(OrderRead).where(OrderRead.order_id == order.id, OrderRead.user_id == user.id))
    if read is None:
        read = OrderRead(order_id=order.id, user_id=user.id)
        db.add(read)
    if shown_message_id is not None and (read.last_read_message_id is None or shown_message_id > read.last_read_message_id):
        read.last_read_message_id = shown_message_id
    if user.role == UserRole.STUDENT and order.recipient_id == user.id:
        read.seen_assignment_version = order.assignment_version
    db.commit()


def assignment_changed(db: Session, order: Order, recipient: User) -> None:
    """El historial previo es contexto, no una ráfaga de mensajes nuevos."""
    if order.recipient_id == recipient.id:
        return
    order.recipient_id = recipient.id
    order.assignment_version += 1
    read = db.scalar(select(OrderRead).where(OrderRead.order_id == order.id, OrderRead.user_id == recipient.id))
    if read is None:
        read = OrderRead(order_id=order.id, user_id=recipient.id)
        db.add(read)
    read.last_read_message_id = max((m.id for m in order.messages), default=None)
    # La versión observada permanece anterior hasta que el creador abra el detalle.
