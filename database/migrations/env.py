"""
CONDUIT — Alembic Migration Environment
Connects Alembic to SQLAlchemy models and database
"""

import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# ── PATH SETUP ────────────────────────────────────────────────────────────────
# Add project root to sys.path so we can import database.models
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)
))))

# ── LOAD ENV VARS ─────────────────────────────────────────────────────────────
from dotenv import load_dotenv
load_dotenv()

# ── IMPORT MODELS ─────────────────────────────────────────────────────────────
# This must come AFTER sys.path is set
# All models must be imported here for autogenerate to detect them
from database.models import (
    Base,
    Vehicle,
    Inventory,
    LaborOperation,
    Customer,
    Supplier,
    RepairOrder,
    Quote,
    PurchaseOrder,
    AgentAuditLog,
)

# ── ALEMBIC CONFIG ────────────────────────────────────────────────────────────
config = context.config

# Override sqlalchemy.url with DATABASE_URL from .env if present
# This means you never need to hardcode credentials in alembic.ini
database_url = os.getenv("DATABASE_URL")
if database_url:
    config.set_main_option("sqlalchemy.url", database_url)

# Setup logging from alembic.ini config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata — Alembic uses this for autogenerate
target_metadata = Base.metadata


# ── MIGRATION RUNNERS ─────────────────────────────────────────────────────────

def run_migrations_offline() -> None:
    """
    Run migrations in offline mode (generates SQL without DB connection)
    Useful for generating migration scripts to review before applying
    Usage: alembic upgrade head --sql
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Run migrations in online mode (connects to DB and applies directly)
    This is the standard mode used by: alembic upgrade head
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # Compare server defaults for more accurate autogenerate
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


# ── ENTRY POINT ───────────────────────────────────────────────────────────────
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
