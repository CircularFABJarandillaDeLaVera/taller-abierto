"""Comprobante firmado del corte de mensajes entregado por el servidor."""

import hashlib
import hmac
import time

from fastapi import HTTPException

from app.config import get_settings

MAX_AGE_SECONDS = 12 * 60 * 60
DOMAIN = b"taller-abierto-lectura-v1:"


def _signature(payload: str) -> str:
    key = get_settings().secret_key.encode()
    return hmac.new(key, DOMAIN + payload.encode(), hashlib.sha256).hexdigest()


def issue_read_cursor(user_id: int, order_id: int, message_id: int) -> str:
    payload = f"{user_id}.{order_id}.{message_id}.{int(time.time())}"
    return f"{payload}.{_signature(payload)}"


def verify_read_cursor(token: str, user_id: int, order_id: int) -> int:
    try:
        if len(token) > 180:
            raise ValueError
        user, order, message, issued, signature = token.split(".")
        values = (int(user), int(order), int(message), int(issued))
        payload = ".".join((user, order, message, issued))
        age = int(time.time()) - values[3]
        valid = (
            values[0] == user_id and values[1] == order_id and values[2] >= 0
            and 0 <= age <= MAX_AGE_SECONDS and hmac.compare_digest(signature, _signature(payload))
        )
    except (ValueError, TypeError):
        valid = False
    if not valid:
        raise HTTPException(status_code=422, detail="Corte de lectura inválido o caducado.")
    return values[2]
