"""Textos de interfaz derivados del estado, sin alterar valores persistidos."""

from datetime import datetime

from app.models import Order, OrderStatus

STATUS_LABELS = {
    OrderStatus.RECEIVED: "Recibido",
    OrderStatus.IN_CONVERSATION: "En conversación",
    OrderStatus.ACCEPTED: "Aceptado",
    OrderStatus.COMPLETED: "Terminado",
    OrderStatus.CANCELLED: "Cancelado",
}


def status_label(status: OrderStatus) -> str:
    return STATUS_LABELS.get(status, "Estado pendiente")


def activity_date(order: Order) -> datetime:
    if hasattr(order, "_news_activity"):
        return order._news_activity
    return max((message.created_at for message in order.messages), default=order.created_at)
