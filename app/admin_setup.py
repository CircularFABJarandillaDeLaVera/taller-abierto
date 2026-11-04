"""Habilitación presencial y explícita de una única cuenta administradora."""

import argparse

from sqlalchemy import delete, select

from app.database import SessionLocal
from app.models import LoginSession, User, UserRole


def main() -> None:
    parser = argparse.ArgumentParser(description="Promover una cuenta responsable identificada a administradora")
    parser.add_argument("alias", help="Alias exacto de una cuenta responsable existente")
    args = parser.parse_args()

    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.alias == args.alias))
        if user is None or user.role != UserRole.TEACHER or not user.is_active or not user.password_hash:
            parser.error("El alias debe ser una cuenta responsable activa con contraseña.")
        if db.scalar(select(User.id).where(User.role == UserRole.ADMIN)) is not None:
            parser.error("Ya existe una cuenta administradora; no se ha cambiado ningún acceso.")
        expected = f"HABILITAR ADMIN {user.alias} #{user.id}"
        print(f"Cuenta encontrada: ID {user.id}, alias {user.alias}, rol responsable de tienda.")
        if input(f"Escribe exactamente «{expected}» para continuar: ") != expected:
            parser.error("Confirmación incorrecta; no se ha cambiado ningún acceso.")
        user.role = UserRole.ADMIN
        db.execute(delete(LoginSession).where(LoginSession.user_id == user.id))
        db.commit()
        print("Cuenta administradora habilitada. La contraseña se conserva; vuelve a iniciar sesión.")


if __name__ == "__main__":
    main()
