"""La nueva opción ADMIN no modifica las cuentas docentes existentes."""

import os

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.engine import make_url

from app.config import sqlalchemy_url
from app.database import make_engine


def _check_upgrade(url):
    engine = make_engine(url)
    try:
        assert not inspect(engine).get_table_names(), "La base de regresión debe estar vacía"
        config = Config("alembic.ini")
        config.set_main_option("sqlalchemy.url", sqlalchemy_url(url).replace("%", "%%"))
        command.upgrade(config, "0006_order_reads")
        with engine.begin() as connection:
            connection.execute(text("INSERT INTO users (alias, role, is_active) VALUES ('responsable_previo', 'TEACHER', TRUE)"))
        command.upgrade(config, "head")
        with engine.begin() as connection:
            assert connection.execute(text("SELECT role FROM users WHERE alias='responsable_previo'")).scalar() == "TEACHER"
            connection.execute(text("INSERT INTO users (alias, role, is_active) VALUES ('admin_ficticio', 'ADMIN', TRUE)"))
            assert connection.execute(text("SELECT role FROM users WHERE alias='admin_ficticio'")).scalar() == "ADMIN"
    finally:
        engine.dispose()


def test_admin_upgrade_on_isolated_sqlite(tmp_path):
    _check_upgrade(f"sqlite:///{tmp_path / 'admin.db'}")


def test_admin_upgrade_on_isolated_postgres():
    url = os.environ.get("TEST_ADMIN_POSTGRES_URL")
    if not url:
        pytest.skip("Requiere una base PostgreSQL de regresión aislada")
    if not make_url(sqlalchemy_url(url)).database.startswith("regression_"):
        pytest.fail("TEST_ADMIN_POSTGRES_URL debe apuntar a una base regression_ dedicada")
    _check_upgrade(url)
