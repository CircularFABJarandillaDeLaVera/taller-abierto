"""Comprobaciones locales de configuración y DDL PostgreSQL, sin conexión externa."""

import pytest
from io import StringIO
from alembic import command
from alembic.config import Config
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from app.config import Settings, sqlalchemy_url, validate_for_production
from app.database import Base
import app.models  # noqa: F401


def test_postgres_url_and_production_guards():
    example = "postgresql://usuario:clave@ejemplo.invalid/demo?sslmode=require"
    assert sqlalchemy_url(example).startswith("postgresql+psycopg://")
    assert sqlalchemy_url(example.replace("postgresql://", "postgres://")).startswith("postgresql+psycopg://")
    assert sqlalchemy_url("sqlite:///prueba.db") == "sqlite:///prueba.db"
    with pytest.raises(RuntimeError):
        validate_for_production(Settings(app_env="production", database_url="sqlite:///prueba.db", secret_key="x" * 40))
    with pytest.raises(RuntimeError):
        validate_for_production(Settings(app_env="production", database_url=example, secret_key="cambiar-por-un-secreto-local"))
    with pytest.raises(RuntimeError):
        validate_for_production(Settings(app_env="production", database_url=example.replace("sslmode=require", "sslmode=disable"), secret_key="x" * 40))
    validate_for_production(Settings(app_env="production", database_url=example, secret_key="x" * 40))


def test_all_models_compile_for_postgres():
    dialect = postgresql.dialect()
    for table in Base.metadata.sorted_tables:
        sql = str(CreateTable(table).compile(dialect=dialect))
        assert "CREATE TABLE" in sql


def test_alembic_generates_postgres_sql_offline():
    output = StringIO()
    config = Config("alembic.ini", output_buffer=output)
    config.set_main_option("sqlalchemy.url", "postgresql+psycopg://usuario:clave@ejemplo.invalid/demo?sslmode=require")
    command.upgrade(config, "head", sql=True)
    script = output.getvalue()
    assert "CREATE TABLE order_reads" in script
    assert "photo_consents" in script
    assert "0006_order_reads" in script
