"""Provisionamiento interactivo de credenciales individuales de demo."""
import argparse
from getpass import getpass

from sqlalchemy import select

from app.database import SessionLocal
from app.identity import hash_password
from app.models import LoginSession, User, UserRole


def main():
    parser = argparse.ArgumentParser(description="Crear o renovar credenciales de creador o docente")
    parser.add_argument("alias", help="Alias existente de creador o alias nuevo del docente")
    parser.add_argument("--role", choices=("student", "teacher"), required=True)
    args = parser.parse_args()
    role = UserRole(args.role)
    first = getpass("Contraseña (mínimo 12 caracteres): ")
    second = getpass("Repetir contraseña: ")
    if first != second:
        parser.error("Las contraseñas no coinciden.")
    encoded = hash_password(first)
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.alias == args.alias))
        if user and user.role != role:
            parser.error("El alias pertenece a otro rol.")
        if not user and role == UserRole.STUDENT:
            parser.error("El creador debe existir en el catálogo antes de provisionarlo.")
        if not user:
            user = User(alias=args.alias, role=role)
            db.add(user)
        user.password_hash = encoded
        db.flush()
        for active_session in db.scalars(select(LoginSession).where(LoginSession.user_id == user.id)).all():
            db.delete(active_session)
        db.commit()
    print("Credencial provisionada. No se muestra la contraseña.")


if __name__ == "__main__":
    main()
