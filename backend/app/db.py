"""Database access: one lazily created SQLAlchemy engine and a FastAPI session dependency.

Tests replace `get_db` through `app.dependency_overrides`, so they never need PostgreSQL.
"""
from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, Session

from .config import database_url

class Base(DeclarativeBase):
    pass


def driver_url(url: str) -> str:
    """Pin the psycopg2 driver for plain postgresql:// URLs (SQLAlchemy 2.1 would default to psycopg 3)."""
    parsed = make_url(url)
    if parsed.drivername in ("postgresql", "postgres"):
        parsed = parsed.set(drivername="postgresql+psycopg2")
    return parsed.render_as_string(hide_password=False)


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    url = driver_url(database_url()[0])
    kwargs = {"connect_args": {"check_same_thread": False}} if url.startswith("sqlite") else {"pool_pre_ping": True}
    return create_engine(url, **kwargs)


def get_db() -> Iterator[Session]:
    """FastAPI dependency: one session per request."""
    with Session(get_engine(), expire_on_commit=False) as session:
        yield session


def safe_database_url() -> str:
    """The configured URL with the password hidden, for logs."""
    url, _ = database_url()
    return make_url(url).render_as_string(hide_password=True)


def init_db() -> tuple[bool, str]:
    """Check the connection and create missing tables. Returns (available, detail); never raises."""
    # Imported here so the models register themselves on Base before create_all.
    from . import models  # noqa: F401

    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        Base.metadata.create_all(engine)
    except Exception as exc:
        return False, f"{type(exc).__name__}: {str(exc).splitlines()[0] if str(exc) else ''}"
    return True, "ok"
