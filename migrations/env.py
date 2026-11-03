from logging.config import fileConfig
from alembic import context
from sqlalchemy import engine_from_config, pool
from app.database import Base
from app.config import get_settings, sqlalchemy_url
import app.models  # noqa: F401

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)
target_metadata = Base.metadata
configured_url = config.get_main_option("sqlalchemy.url")
# Las llamadas de prueba que pasan una URL explícita conservan su base temporal.
if configured_url == "sqlite:///./data/taller_abierto.db":
    configured_url = get_settings().database_url
config.set_main_option("sqlalchemy.url", sqlalchemy_url(configured_url).replace("%", "%%"))

def run_migrations_offline():
    context.configure(url=config.get_main_option("sqlalchemy.url"), target_metadata=target_metadata, literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction(): context.run_migrations()

def run_migrations_online():
    connectable = engine_from_config(config.get_section(config.config_ini_section), prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction(): context.run_migrations()

if context.is_offline_mode(): run_migrations_offline()
else: run_migrations_online()

