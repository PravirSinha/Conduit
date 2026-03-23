"""
CONDUIT — Database Connection
==============================
Single source of truth for all database connections.
Every file in the project that needs PostgreSQL
imports from here — never creates its own connection.

Usage:
    from database.connection import get_db, engine

    # In FastAPI routes (dependency injection)
    def my_route(db: Session = Depends(get_db)):
        results = db.query(Vehicle).all()

    # In agents (direct session)
    with get_session() as db:
        part = db.query(Inventory).filter_by(
            part_number="BRK-PAD-HON-F-01"
        ).first()

    # In scripts (one-off queries)
    db = next(get_db())
    count = db.query(RepairOrder).count()
    db.close()
"""

import os
import sys
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from dotenv import load_dotenv

load_dotenv()

# ── ENGINE CONFIGURATION ──────────────────────────────────────────────────────

DATABASE_URL = os.getenv("DATABASE_URL")

# ── LAZY ENGINE ───────────────────────────────────────────────────────────────
# Engine is created on FIRST USE, not at import time.
# A missing or wrong DATABASE_URL won't crash FastAPI on startup —
# it only fails when a request actually touches the database.

_engine        = None
_SessionLocal  = None


def _get_engine():
    global _engine, _SessionLocal
    if _engine is not None:
        return _engine

    url = os.getenv("DATABASE_URL") or DATABASE_URL
    if not url:
        raise ValueError(
            "DATABASE_URL not set. "
            "Check the DATABASE_URL GitHub Actions secret and EC2 .env file.\n"
            "Expected: postgresql://user:pass@host:5432/conduit?sslmode=require"
        )

    _engine = create_engine(
        url,
        poolclass=QueuePool,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
        pool_recycle=3600,
        echo=os.getenv("ENVIRONMENT") == "development" and
             os.getenv("LOG_LEVEL") == "DEBUG",
    )
    _SessionLocal = sessionmaker(
        bind=_engine,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
    )
    return _engine


# ── SESSION FACTORY ───────────────────────────────────────────────────────────

class _LazySessionLocal:
    """Proxy that creates the session factory on first use."""
    def __call__(self, *a, **kw):
        _get_engine()
        return _SessionLocal(*a, **kw)

SessionLocal = _LazySessionLocal()


class _LazyEngine:
    """Proxy that creates the engine on first use."""
    def __getattr__(self, name):
        return getattr(_get_engine(), name)
    def connect(self, *a, **kw):
        return _get_engine().connect(*a, **kw)
    def begin(self, *a, **kw):
        return _get_engine().begin(*a, **kw)
    def dispose(self, *a, **kw):
        return _get_engine().dispose(*a, **kw)

engine = _LazyEngine()


# ── SESSION PROVIDERS ─────────────────────────────────────────────────────────

def get_db():
    """
    FastAPI dependency injection style session provider.

    Usage in FastAPI routes:
        from fastapi import Depends
        from database.connection import get_db

        @router.get("/repair-orders")
        def get_ros(db: Session = Depends(get_db)):
            return db.query(RepairOrder).all()

    Automatically closes session after request completes.
    Use this in all FastAPI route handlers.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_session():
    """
    Context manager style session for use in agents and scripts.

    Usage:
        from database.connection import get_session

        with get_session() as db:
            part = db.query(Inventory).filter_by(
                part_number="BRK-PAD-HON-F-01"
            ).first()
            part.qty_on_hand -= 1
            db.commit()
        # session automatically closed here

    Use this in:
        - Agent functions
        - Background tasks
        - Data generation scripts
        - Seed scripts
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ── HEALTH CHECK ──────────────────────────────────────────────────────────────

def check_db_connection() -> bool:
    """
    Tests database connectivity.
    Called on application startup to fail fast if DB is unreachable.

    Returns True if connected, raises exception if not.
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        raise ConnectionError(
            f"Cannot connect to PostgreSQL: {e}\n"
            f"DATABASE_URL: {DATABASE_URL}\n"
            f"Is PostgreSQL running? Try: docker-compose up -d postgres"
        )


def get_table_counts() -> dict:
    """
    Returns row counts for all CONDUIT tables.
    Useful for startup logging and health checks.
    """
    tables = [
        "vehicles",
        "inventory",
        "labor_operations",
        "customers",
        "suppliers",
        "repair_orders",
        "quotes",
        "purchase_orders",
        "agent_audit_log",
    ]

    counts = {}
    with engine.connect() as conn:
        for table in tables:
            try:
                result = conn.execute(
                    text(f"SELECT COUNT(*) FROM {table}")
                )
                counts[table] = result.scalar()
            except Exception:
                counts[table] = "error"

    return counts


# ── STARTUP VERIFICATION ──────────────────────────────────────────────────────

if __name__ == "__main__":
    """
    Run directly to verify database connection and table counts:
        python database/connection.py
    """
    GREEN  = "\033[92m"
    RED    = "\033[91m"
    CYAN   = "\033[96m"
    BOLD   = "\033[1m"
    RESET  = "\033[0m"

    print(f"\n{BOLD}CONDUIT — Database Connection Check{RESET}\n")
    print(f"  Connecting to: {DATABASE_URL}\n")

    try:
        check_db_connection()
        print(f"  {GREEN}✓ PostgreSQL connection successful{RESET}\n")

        counts = get_table_counts()
        print(f"  {BOLD}Table counts:{RESET}")
        for table, count in counts.items():
            status = GREEN if isinstance(count, int) and count > 0 else RED
            print(f"  {CYAN}→{RESET} {table:<20} {status}{count}{RESET}")

    except ConnectionError as e:
        print(f"  {RED}✗ Connection failed:{RESET}\n  {e}")
        sys.exit(1)