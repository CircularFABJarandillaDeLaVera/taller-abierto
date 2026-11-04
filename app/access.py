"""Permisos de encargo independientes de las plantillas."""
from fastapi import HTTPException

from app.models import Order, User, UserRole


def require_access(order: Order | None, user: User | None) -> Order:
    if order is None or user is None:
        raise HTTPException(status_code=404, detail="Solicitud no disponible.")
    if user.role in (UserRole.TEACHER, UserRole.ADMIN):
        return order
    if user.role == UserRole.STUDENT and order.recipient_id == user.id:
        return order
    if user.role == UserRole.VISITOR and order.visitor_access_enabled and order.requester_id == user.id:
        return order
    raise HTTPException(status_code=404, detail="Solicitud no disponible.")


def require_teacher(user: User | None) -> None:
    if user is None or user.role not in (UserRole.TEACHER, UserRole.ADMIN):
        raise HTTPException(status_code=403, detail="Acción no permitida.")
