"""Formularios de gestión de cuentas; las reglas están en accounts_service."""

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.accounts_service import (
    AccountError, change_own_password, create_account,
    managed_accounts, require_manager, reset_access, set_active, unlinked_artisans,
)
from app.csrf import verify
from app.database import get_db
from app.models import UserRole
from app.panel_routes import actor, render


router = APIRouter()


def _accounts_page(request: Request, db: Session, *, error: str | None = None, status_code: int = 200):
    user = actor(request, db)
    try:
        roles = require_manager(user)
    except AccountError as problem:
        raise HTTPException(problem.status_code, problem.message) from None
    return render(request, "accounts.html", {
        "user": user, "roles": roles, "accounts": managed_accounts(db, user),
        "unlinked": unlinked_artisans(db, user), "error": error,
    }, status_code=status_code, csrf=True)


@router.get("/panel/cuentas")
def accounts_page(request: Request, db: Session = Depends(get_db)):
    return _accounts_page(request, db)


@router.post("/panel/cuentas/alta")
def account_create(request: Request, role: str = Form(""), mode: str = Form(""), alias: str = Form(""), existing_user_id: int | None = Form(None), csrf_token: str = Form(""), db: Session = Depends(get_db)):
    verify(request, csrf_token)
    user = actor(request, db)
    try:
        target, password = create_account(db, user, role_name=role, mode=mode, alias=alias, existing_user_id=existing_user_id)
    except AccountError as problem:
        if problem.status_code == 403:
            raise HTTPException(403, problem.message) from None
        return _accounts_page(request, db, error=problem.message, status_code=problem.status_code)
    return render(request, "credential.html", {"target": target, "password": password, "action": "creado"})


@router.post("/panel/cuentas/{user_id}/restablecer")
def account_reset(user_id: int, request: Request, csrf_token: str = Form(""), db: Session = Depends(get_db)):
    verify(request, csrf_token)
    try:
        target, password = reset_access(db, actor(request, db), user_id)
    except AccountError as problem:
        raise HTTPException(problem.status_code, problem.message) from None
    return render(request, "credential.html", {"target": target, "password": password, "action": "restablecido"})


@router.post("/panel/cuentas/{user_id}/estado")
def account_status(user_id: int, request: Request, active: str = Form(""), csrf_token: str = Form(""), db: Session = Depends(get_db)):
    verify(request, csrf_token)
    if active not in ("0", "1"):
        raise HTTPException(422, "Estado no válido.")
    try:
        set_active(db, actor(request, db), user_id, active == "1")
    except AccountError as problem:
        raise HTTPException(problem.status_code, problem.message) from None
    return RedirectResponse("/panel/cuentas", status_code=303)


@router.get("/panel/clave")
def password_page(request: Request, db: Session = Depends(get_db)):
    user = actor(request, db)
    if user is None or user.role not in (UserRole.ADMIN, UserRole.TEACHER, UserRole.STUDENT):
        raise HTTPException(403, "Acción no permitida.")
    return render(request, "password_change.html", csrf=True)


@router.post("/panel/clave")
def password_update(request: Request, current_password: str = Form(""), new_password: str = Form(""), confirmation: str = Form(""), csrf_token: str = Form(""), db: Session = Depends(get_db)):
    verify(request, csrf_token)
    user = actor(request, db)
    if user is None:
        raise HTTPException(403, "Acción no permitida.")
    try:
        change_own_password(db, user, current_password, new_password, confirmation)
    except AccountError as problem:
        if problem.status_code == 403:
            raise HTTPException(403, problem.message) from None
        return render(request, "password_change.html", {"error": problem.message}, status_code=problem.status_code, csrf=True)
    response = render(request, "password_change.html", {"success": True})
    response.delete_cookie("ta_session")
    return response
