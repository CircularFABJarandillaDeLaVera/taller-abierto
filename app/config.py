"""Configuración centralizada, sin secretos en el código."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError


class Settings(BaseSettings):
    app_name: str = "Taller Abierto"
    app_env: str = "development"
    database_url: str = "sqlite:///./data/taller_abierto.db"
    attachments_dir: str = "./private_uploads"
    secret_key: str = "cambiar-por-un-secreto-local"
    poll_seconds: int = Field(default=10, ge=5, le=120)

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

def sqlalchemy_url(database_url: str) -> str:
    """Usa Psycopg 3 con las URL PostgreSQL que entrega el proveedor."""
    if database_url.startswith("postgresql://"):
        return "postgresql+psycopg://" + database_url[len("postgresql://"):]
    if database_url.startswith("postgres://"):
        return "postgresql+psycopg://" + database_url[len("postgres://"):]
    return database_url


def validate_for_production(settings: Settings) -> None:
    """Rechaza despliegues inseguros con errores que no imprimen secretos."""
    if settings.app_env != "production":
        return
    try:
        url = make_url(sqlalchemy_url(settings.database_url))
    except ArgumentError:
        raise RuntimeError("DATABASE_URL de producción no es válida.") from None
    if url.drivername != "postgresql+psycopg" or url.query.get("sslmode") not in ("require", "verify-ca", "verify-full"):
        raise RuntimeError("Producción requiere PostgreSQL con conexión TLS.")
    if settings.secret_key == "cambiar-por-un-secreto-local" or len(settings.secret_key) < 32:
        raise RuntimeError("Producción requiere SECRET_KEY privada de al menos 32 caracteres.")


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    validate_for_production(settings)
    return settings

