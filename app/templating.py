"""Plantillas y filtros compartidos por las rutas públicas y privadas."""

from pathlib import Path

from fastapi.templating import Jinja2Templates

from app.presentation import activity_date, status_label
from app.config import get_settings
from app.identity import current_user


def notification_context(request):
    db = getattr(request.state, "db", None)
    return {"notifications_active": bool(db and current_user(db, request.cookies.get("ta_session")))}

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"), context_processors=[notification_context])
templates.env.filters["estado"] = status_label
templates.env.filters["actividad"] = activity_date
templates.env.globals["poll_seconds"] = get_settings().poll_seconds
