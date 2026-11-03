"""Token CSRF de doble envío, firmado y limitado al navegador local."""
import hashlib
import hmac
import secrets

from fastapi import HTTPException, Request
from fastapi.responses import Response

from app.config import get_settings


def issue() -> str:
    nonce = secrets.token_urlsafe(24)
    signature = hmac.new(get_settings().secret_key.encode(), nonce.encode(), hashlib.sha256).hexdigest()
    token = nonce + "." + signature
    return token


def attach(response: Response, token: str) -> None:
    response.set_cookie("ta_csrf", token, httponly=True, samesite="strict", secure=get_settings().app_env == "production", max_age=3600)
    response.headers["Cache-Control"] = "no-store"


def verify(request: Request, submitted: str) -> None:
    cookie = request.cookies.get("ta_csrf", "")
    try:
        nonce, signature = cookie.split(".", 1)
        expected = hmac.new(get_settings().secret_key.encode(), nonce.encode(), hashlib.sha256).hexdigest()
        valid = len(nonce) >= 20 and hmac.compare_digest(signature, expected)
    except ValueError:
        valid = False
    if not valid or not hmac.compare_digest(cookie, submitted):
        raise HTTPException(status_code=403, detail="Formulario caducado o no válido.")
