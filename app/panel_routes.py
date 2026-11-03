"""Acceso, paneles, conversación y asignación docente."""
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.access import require_access, require_teacher
from app.config import get_settings
from app.csrf import attach, issue, verify
from app.database import get_db
from app.identity import check_password, current_user, new_session, redeem, revoke_session
from app.models import Attachment, Message, Order, OrderKind, OrderStatus, User, UserRole
from app.photos import PhotoError, prepare, save_batch, clean_written, storage_root, RIGHTS_TEXT, PERSON_TEXT, MINOR_TEXT, USE_TEXT
import secrets
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
def login_page(request: Request):
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
def recovery_page(token: str, request: Request):
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
    query = select(Order).options(selectinload(Order.messages), selectinload(Order.recipient), selectinload(Order.product)).order_by(Order.created_at.desc(), Order.id.desc())
    if user.role == UserRole.STUDENT:
        query = query.where(Order.recipient_id == user.id)
    elif user.role == UserRole.VISITOR:
        query = query.where(Order.requester_id == user.id, Order.visitor_access_enabled.is_(True))
    orders = db.scalars(query).all()
    students = db.scalars(select(User).where(User.role == UserRole.STUDENT, User.is_active.is_(True)).order_by(User.alias)).all() if user.role == UserRole.TEACHER else []
    return render(request, "panel.html", {"user": user, "orders": orders, "students": students}, csrf=True)


@router.get("/panel/solicitudes/{order_id}", response_class=HTMLResponse)
def detail(order_id: int, request: Request, db: Session = Depends(get_db)):
    return order_page(order_id, request, db)


def order_page(order_id: int, request: Request, db: Session, photo_error: str | None = None, photo_error_field: str | None = None, rights_checked: bool = False, person_checked: bool = False):
    user = actor(request, db)
    order = require_access(db.scalar(select(Order).options(selectinload(Order.messages).selectinload(Message.author), selectinload(Order.recipient), selectinload(Order.product), selectinload(Order.attachments)).where(Order.id == order_id)), user)
    students = db.scalars(select(User).where(User.role == UserRole.STUDENT, User.is_active.is_(True)).order_by(User.alias)).all() if user.role == UserRole.TEACHER else []
    return render(request, "order.html", {"user": user, "order": order, "students": students, "rights_text": RIGHTS_TEXT, "person_text": PERSON_TEXT, "minor_text": MINOR_TEXT, "use_text": USE_TEXT, "photo_error": photo_error, "photo_error_field": photo_error_field, "rights_checked": rights_checked, "person_checked": person_checked}, status_code=422 if photo_error else 200, csrf=True)


@router.post("/panel/solicitudes/{order_id}/fotos")
async def upload_photos(order_id: int, request: Request, csrf_token: str = Form(""), rights_confirmed: str = Form(""), person_confirmed: str = Form(""), photos: list[UploadFile] = File(default=[]), db: Session = Depends(get_db)):
    verify(request, csrf_token)
    user = actor(request, db)
    order = require_access(db.get(Order, order_id), user)
    if order.kind != OrderKind.CUSTOM_FIGURE:
        raise HTTPException(status_code=404)
    if user.role != UserRole.VISITOR or order.requester_id != user.id or not order.visitor_access_enabled:
        raise HTTPException(status_code=403, detail="Solo el solicitante puede añadir fotografías.")
    written = []
    try:
        prepared = await prepare(photos, rights_confirmed, person_confirmed)
        if not prepared:
            raise PhotoError("Selecciona al menos una fotografía.")
        save_batch(db, order, user, prepared, written)
        db.commit()
    except PhotoError as exc:
        db.rollback()
        clean_written(written)
        return order_page(order_id, request, db, str(exc), exc.field, rights_confirmed == "on", person_confirmed == "on")
    except Exception:
        db.rollback()
        clean_written(written)
        raise
    return RedirectResponse(f"/panel/solicitudes/{order_id}", status_code=303)


@router.get("/panel/solicitudes/{order_id}/fotos/{photo_id}")
def view_photo(order_id: int, photo_id: int, request: Request, db: Session = Depends(get_db)):
    require_access(db.get(Order, order_id), actor(request, db))
    photo = db.get(Attachment, photo_id)
    if not photo or photo.order_id != order_id:
        raise HTTPException(status_code=404)
    root = storage_root()
    path = root / photo.stored_name
    if path.parent != root or not path.is_file():
        raise HTTPException(status_code=404)
    return FileResponse(path, media_type=photo.mime_type, headers={"Cache-Control": "no-store", "Pragma": "no-cache", "Referrer-Policy": "no-referrer", "X-Content-Type-Options": "nosniff"})


@router.post("/panel/solicitudes/{order_id}/fotos/{photo_id}/eliminar")
def delete_photo(order_id: int, photo_id: int, request: Request, csrf_token: str = Form(""), db: Session = Depends(get_db)):
    verify(request, csrf_token)
    user = actor(request, db)
    order = require_access(db.get(Order, order_id), user)
    if user.role != UserRole.TEACHER and not (user.role == UserRole.VISITOR and order.requester_id == user.id and order.visitor_access_enabled):
        raise HTTPException(status_code=403)
    photo = db.get(Attachment, photo_id)
    if not photo or photo.order_id != order.id:
        raise HTTPException(status_code=404)
    root = storage_root()
    source = root / photo.stored_name
    if source.parent != root or not source.is_file():
        raise HTTPException(status_code=409, detail="No se encuentra el archivo; el registro se conserva para revisión.")
    staged = root / (secrets.token_hex(24) + ".deleting")
    try:
        source.rename(staged)
        db.delete(photo)
        db.commit()
    except OSError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="No se pudo retirar el archivo; el registro se conserva.") from exc
    except Exception:
        db.rollback()
        staged.rename(source)
        raise
    try:
        staged.unlink()
    except OSError:
        # Queda en cuarentena privada para limpieza administrativa; el registro activo ya no existe.
        pass
    return RedirectResponse(f"/panel/solicitudes/{order_id}", status_code=303)


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
    order.recipient_id = student.id
    db.commit()
    return RedirectResponse(f"/panel/solicitudes/{order.id}", status_code=303)
