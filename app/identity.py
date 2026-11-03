"""Identidad local: PBKDF2 estándar, sesiones revocables y enlaces de un solo uso."""
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import LoginSession, Order, RecoveryToken, User, UserRole

SESSION_HOURS = 12
RECOVERY_HOURS = 48
ITERATIONS = 600_000


def now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def fingerprint(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def hash_password(password: str) -> str:
    if not 12 <= len(password) <= 1024:
        raise ValueError("La contraseña debe tener entre 12 y 1024 caracteres.")
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS)
    return f"pbkdf2_sha256${ITERATIONS}${salt.hex()}${digest.hex()}"


def check_password(password: str, encoded: str | None) -> bool:
    if not encoded or len(password) > 1024:
        return False
    try:
        algorithm, count, salt, digest = encoded.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(count))
        return hmac.compare_digest(candidate, bytes.fromhex(digest))
    except (ValueError, TypeError):
        return False


def new_session(db: Session, user: User) -> str:
    token = secrets.token_urlsafe(32)
    db.add(LoginSession(token_hash=fingerprint(token), user_id=user.id, expires_at=now() + timedelta(hours=SESSION_HOURS)))
    db.commit()
    return token


def current_user(db: Session, token: str | None) -> User | None:
    if not token:
        return None
    record = db.scalar(select(LoginSession).where(LoginSession.token_hash == fingerprint(token), LoginSession.expires_at > now()))
    return record.user if record and record.user.is_active else None


def revoke_session(db: Session, token: str | None) -> None:
    if token:
        record = db.scalar(select(LoginSession).where(LoginSession.token_hash == fingerprint(token)))
        if record:
            db.delete(record)
            db.commit()


def new_recovery(db: Session, order: Order) -> str:
    token = secrets.token_urlsafe(32)
    db.add(RecoveryToken(token_hash=fingerprint(token), order_id=order.id, expires_at=now() + timedelta(hours=RECOVERY_HOURS)))
    db.commit()
    return token


def redeem(db: Session, token: str) -> str | None:
    record = db.scalar(select(RecoveryToken).where(RecoveryToken.token_hash == fingerprint(token), RecoveryToken.expires_at > now(), RecoveryToken.used_at.is_(None)))
    if not record or not record.order.visitor_access_enabled:
        return None
    record.used_at = now()
    user = db.get(User, record.order.requester_id)
    if not user or user.role != UserRole.VISITOR:
        return None
    session_token = secrets.token_urlsafe(32)
    db.add(LoginSession(token_hash=fingerprint(session_token), user_id=user.id, expires_at=now() + timedelta(hours=SESSION_HOURS)))
    db.commit()
    return session_token
