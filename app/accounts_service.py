"""Altas y gestión de accesos del taller, independientes de las plantillas."""

import re
import secrets

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.identity import check_password, hash_password
from app.models import LoginSession, User, UserRole


class AccountError(Exception):
    def __init__(self, message: str, status_code: int = 422):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def allowed_new_roles(actor: User | None) -> tuple[UserRole, ...]:
    if actor is None or not actor.is_active:
        return ()
    if actor.role == UserRole.ADMIN:
        return (UserRole.TEACHER, UserRole.STUDENT)
    if actor.role == UserRole.TEACHER:
        return (UserRole.STUDENT,)
    return ()


def require_manager(actor: User | None) -> tuple[UserRole, ...]:
    roles = allowed_new_roles(actor)
    if not roles:
        raise AccountError("Acción no permitida.", 403)
    return roles


def managed_accounts(db: Session, actor: User) -> list[User]:
    roles = require_manager(actor)
    return db.scalars(select(User).where(User.role.in_(roles)).order_by(User.role, User.alias)).all()


def unlinked_artisans(db: Session, actor: User) -> list[User]:
    require_manager(actor)
    return db.scalars(select(User).where(User.role == UserRole.STUDENT, User.password_hash.is_(None), User.is_active.is_(True)).order_by(User.alias)).all()


def _target(db: Session, actor: User, user_id: int) -> User:
    roles = require_manager(actor)
    target = db.get(User, user_id)
    if target is None:
        raise AccountError("Cuenta no encontrada.", 404)
    if target.role not in roles:
        raise AccountError("No puedes gestionar esa cuenta.", 403)
    return target


def _temporary_password() -> str:
    return secrets.token_urlsafe(24)


def _revoke_sessions(db: Session, user_id: int) -> None:
    db.execute(delete(LoginSession).where(LoginSession.user_id == user_id))


def create_account(db: Session, actor: User, *, role_name: str, mode: str, alias: str = "", existing_user_id: int | None = None) -> tuple[User, str]:
    roles = require_manager(actor)
    try:
        role = UserRole(role_name)
    except ValueError:
        raise AccountError("Rol no permitido.", 403) from None
    if role not in roles:
        raise AccountError("Rol no permitido.", 403)

    if mode == "existing":
        if role != UserRole.STUDENT or existing_user_id is None:
            raise AccountError("Selecciona un perfil de artesano disponible.")
        user = db.get(User, existing_user_id)
        if user is None or user.role != UserRole.STUDENT or not user.is_active:
            raise AccountError("Perfil de artesano no disponible.", 404)
        if user.password_hash:
            raise AccountError("Ese alias ya tiene acceso. Usa el restablecimiento.", 409)
    elif mode == "new":
        alias = alias.strip().lower()
        if not re.fullmatch(r"[a-z][a-z0-9_]{2,79}", alias) or alias.startswith("visitante_"):
            raise AccountError("El alias debe tener 3–80 caracteres: letras minúsculas, números o guion bajo; debe empezar por una letra.")
        if db.scalar(select(User.id).where(func.lower(User.alias) == alias)) is not None:
            raise AccountError("Ese alias ya existe. Vincula su perfil o elige otro alias.", 409)
        user = User(alias=alias, role=role)
        db.add(user)
    else:
        raise AccountError("Modo de alta no válido.")

    password = _temporary_password()
    user.password_hash = hash_password(password)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise AccountError("Ese alias ya existe. Elige otro alias.", 409) from None
    return user, password


def reset_access(db: Session, actor: User, user_id: int) -> tuple[User, str]:
    user = _target(db, actor, user_id)
    password = _temporary_password()
    user.password_hash = hash_password(password)
    _revoke_sessions(db, user.id)
    db.commit()
    return user, password


def set_active(db: Session, actor: User, user_id: int, active: bool) -> User:
    user = _target(db, actor, user_id)
    user.is_active = active
    if not active:
        _revoke_sessions(db, user.id)
    db.commit()
    return user


def change_own_password(db: Session, actor: User, current_password: str, new_password: str, confirmation: str) -> None:
    if actor.role not in (UserRole.ADMIN, UserRole.TEACHER, UserRole.STUDENT) or not actor.is_active:
        raise AccountError("Acción no permitida.", 403)
    if not check_password(current_password, actor.password_hash):
        raise AccountError("La contraseña actual no es correcta.")
    if new_password != confirmation:
        raise AccountError("Las contraseñas nuevas no coinciden.")
    try:
        actor.password_hash = hash_password(new_password)
    except ValueError:
        raise AccountError("La contraseña nueva debe tener entre 12 y 1024 caracteres.") from None
    _revoke_sessions(db, actor.id)
    db.commit()
