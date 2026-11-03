"""Configuración centralizada, sin secretos en el código."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Taller Abierto"
    app_env: str = "development"
    database_url: str = "sqlite:///./data/taller_abierto.db"
    attachments_dir: str = "./private_uploads"
    secret_key: str = "cambiar-por-un-secreto-local"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()

