"""Acceso, paneles, conversación y asignación docente."""
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.access import require_access, require_teacher
from app.config import get_settings
from app.csrf import attach, issue, verify
from app.database import get_db
from app.identity import check_password, current_user, new_session, redeem, revoke_session
from app.models import Message, Order, OrderKind, OrderStatus, User, UserRole
from app.notifications import assignment_changed, overview, mark_shown
from app.presentation import activity_date, status_label
from app.read_cursors import issue_read_cursor, verify_read_cursor
from app.templating import templates

router = APIRouter()


def render(request, name, context=None, status_code=200, csrf=False):
    data = {"app_name": get_settings().app_name, **(context or {})}
    token = issue() if csrf else None
    if token:
        data["csrf_token"] = token
    response = templates.TemplateResponse(request=request, name=name, context=data, status_code=status_code)
    if token:
        attach(response, token)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


def actor(request: Request, db: Session) -> User | None:
    return current_user(db, request.cookies.get("ta_session"))


@router.get("/entrar", response_class=HTMLResponse)
def login_page(request: Request, db: Session = Depends(get_db)):
    return render(request, "login.html", csrf=True)


@router.post("/entrar")
def login(request: Request, alias: str = Form(""), password: str = Form(""), csrf_token: str = Form(""), db: Session = Depends(get_db)):
    verify(request, csrf_token)
    user = db.scalar(select(User).where(User.alias == alias, User.is_active.is_(True)))
    if not user or user.role not in (UserRole.STUDENT, UserRole.TEACHER) or not check_password(password, user.password_hash):
        return render(request, "login.html", {"error": "Credenciales incorrectas."}, status_code=401, csrf=True)
    revoke_session(db, request.cookies.get("ta_session"))
    response = RedirectResponse("/panel", status_code=303)
    response.set_cookie("ta_session", new_session(db, user), httponly=True, samesite="lax", secure=get_settings().app_env == "production", max_age=43200)
    response.headers["Cache-Control"] = "no-store"
    return response


@router.post("/salir")
def logout(request: Request, csrf_token: str = Form(""), db: Session = Depends(get_db)):
    verify(request, csrf_token)
    revoke_session(db, request.cookies.get("ta_session"))
    response = RedirectResponse("/", status_code=303)
    response.delete_cookie("ta_session")
    return response


@router.get("/recuperar/{token}", response_class=HTMLResponse)
def recovery_page(token: str, request: Request, db: Session = Depends(get_db)):
    if len(token) < 40:
        raise HTTPException(status_code=404)
    return render(request, "recover.html", {"recovery_token": token}, csrf=True)


@router.post("/recuperar/{token}")
def recover(token: str, request: Request, csrf_token: str = Form(""), db: Session = Depends(get_db)):
    verify(request, csrf_token)
    session_token = redeem(db, token)
    if not session_token:
        raise HTTPException(status_code=404, detail="Enlace inválido o caducado.")
    revoke_session(db, request.cookies.get("ta_session"))
    response = RedirectResponse("/panel", status_code=303)
    response.set_cookie("ta_session", session_token, httponly=True, samesite="lax", secure=get_settings().app_env == "production", max_age=43200)
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@router.get("/panel", response_class=HTMLResponse)
def panel(request: Request, db: Session = Depends(get_db)):
    user = actor(request, db)
    if user is None:
        return RedirectResponse("/entrar", status_code=303)
    orders, notices = overview(db, user)
    students = db.scalars(select(User).where(User.role == UserRole.STUDENT, User.is_active.is_(True)).order_by(User.alias)).all() if user.role == UserRole.TEACHER else []
    return render(request, "panel.html", {"user": user, "orders": orders, "notices": notices, "students": students}, csrf=True)


@router.get("/panel/novedades")
def news(request: Request, db: Session = Depends(get_db)):
    user = actor(request, db)
    if user is None:
        return JSONResponse({"detail": "Sesión no disponible."}, status_code=401, headers={"Cache-Control": "no-store"})
    orders, notices = overview(db, user)
    items = [{"order_id": order.id, "label": notices[order.id].label, "kind": notices[order.id].kind, "unread_messages": notices[order.id].unread_messages, "assignment_version": order.assignment_version, "href": f"/panel/solicitudes/{order.id}"} for order in orders if order.id in notices]
    cards = [{"order_id": order.id, "activity": activity_date(order).isoformat(), "html": templates.env.get_template("_order_card.html").render(order=order, notice=notices.get(order.id))} for order in orders]
    return JSONResponse({"count": len(items), "items": items, "cards": cards, "role": user.role.value}, headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})


@router.get("/panel/solicitudes/{order_id}", response_class=HTMLResponse)
def detail(order_id: int, request: Request, db: Session = Depends(get_db)):
    return order_page(order_id, request, db)


def order_page(order_id: int, request: Request, db: Session):
    user = actor(request, db)
    order = require_access(db.scalar(select(Order).options(selectinload(Order.messages).selectinload(Message.author), selectinload(Order.recipient), selectinload(Order.product)).where(Order.id == order_id)), user)
    students = db.scalars(select(User).where(User.role == UserRole.STUDENT, User.is_active.is_(True)).order_by(User.alias)).all() if user.role == UserRole.TEACHER else []
    shown_id = max((message.id for message in order.messages), default=0)
    read_cursor = issue_read_cursor(user.id, order.id, shown_id)
    return render(request, "order.html", {"user": user, "order": order, "shown_id": shown_id, "read_cursor": read_cursor, "students": students}, csrf=True)


@router.get("/panel/solicitudes/{order_id}/mensajes/nuevos")
def new_messages(order_id: int, request: Request, despues: int = 0, db: Session = Depends(get_db)):
    user = actor(request, db)
    order = require_access(db.get(Order, order_id), user)
    if despues < 0:
        raise HTTPException(status_code=422)
    messages = db.scalars(select(Message).options(selectinload(Message.author)).where(Message.order_id == order.id, Message.id > despues).order_by(Message.id)).all()
    items = [{"id": message.id, "body": message.body, "author": "Tú" if message.author_id == user.id else (order.requester_alias or "Visitante") if message.author.role == UserRole.VISITOR else f"@{message.author.alias}", "own": message.author_id == user.id, "date": message.created_at.strftime("%d/%m/%Y · %H:%M"), "iso_date": message.created_at.isoformat()} for message in messages]
    cursor = issue_read_cursor(user.id, order.id, messages[-1].id) if messages else None
    return JSONResponse({"messages": items, "read_cursor": cursor}, headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})


@router.post("/panel/solicitudes/{order_id}/lectura")
def read_messages(order_id: int, request: Request, read_cursor: str = Form(""), csrf_token: str = Form(""), db: Session = Depends(get_db)):
    verify(request, csrf_token)
    user = actor(request, db)
    order = require_access(db.get(Order, order_id), user)
    upto_id = verify_read_cursor(read_cursor, user.id, order.id)
    if upto_id and db.scalar(select(Message.id).where(Message.id == upto_id, Message.order_id == order.id)) is None:
        raise HTTPException(status_code=422, detail="Corte de lectura inválido.")
    mark_shown(db, order, user, upto_id or None)
    return JSONResponse({"ok": True}, headers={"Cache-Control": "no-store"})


@router.post("/panel/solicitudes/{order_id}/mensajes")
def reply(order_id: int, request: Request, body: str = Form(""), csrf_token: str = Form(""), db: Session = Depends(get_db)):
    verify(request, csrf_token)
    user = actor(request, db)
    order = require_access(db.get(Order, order_id), user)
    body = body.strip()
    if not 1 <= len(body) <= 2000:
        raise HTTPException(status_code=422, detail="El mensaje debe tener entre 1 y 2000 caracteres.")
    db.add(Message(order_id=order.id, author_id=user.id, body=body))
    if order.status == OrderStatus.RECEIVED:
        order.status = OrderStatus.IN_CONVERSATION
    db.commit()
    return RedirectResponse(f"/panel/solicitudes/{order.id}", status_code=303)


@router.post("/panel/solicitudes/{order_id}/asignar")
def assign(order_id: int, request: Request, student_id: int = Form(...), csrf_token: str = Form(""), db: Session = Depends(get_db)):
    verify(request, csrf_token)
    require_teacher(actor(request, db))
    order = db.get(Order, order_id)
    student = db.get(User, student_id)
    if not order or order.kind != OrderKind.CUSTOM_FIGURE or not student or student.role != UserRole.STUDENT or not student.is_active:
        raise HTTPException(status_code=422, detail="Asignación inválida.")
    assignment_changed(db, order, student)
    db.commit()
    return RedirectResponse(f"/panel/solicitudes/{order.id}", status_code=303)
