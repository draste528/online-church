"""Database access: one lazily created SQLAlchemy engine and a FastAPI session dependency.

Tests replace `get_db` through `app.dependency_overrides`, so they never need PostgreSQL.
"""
from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine, event, func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, Session
from sqlalchemy.pool import StaticPool

from .config import database_url, seed_on_startup
from .data import ITEMS


class Base(DeclarativeBase):
    pass


def driver_url(url: str) -> str:
    """Pin the psycopg2 driver for plain postgresql:// URLs (SQLAlchemy 2.1 would default to psycopg 3)."""
    parsed = make_url(url)
    if parsed.drivername in ("postgresql", "postgres"):
        parsed = parsed.set(drivername="postgresql+psycopg2")
    return parsed.render_as_string(hide_password=False)


def _sqlite_setup(dbapi_connection, _record) -> None:
    # SQLite's built-in lower() is ASCII-only; the Cyrillic shop search needs a Unicode-aware one.
    dbapi_connection.create_function("lower", 1, lambda value: value.lower() if isinstance(value, str) else value)
    dbapi_connection.execute("PRAGMA foreign_keys=ON")


def make_engine(url: str) -> Engine:
    """Engine for PostgreSQL (production) or SQLite (local runs and tests)."""
    url = driver_url(url)
    if not url.startswith("sqlite"):
        return create_engine(url, pool_pre_ping=True)
    kwargs: dict = {"connect_args": {"check_same_thread": False}}
    if url in ("sqlite://", "sqlite:///:memory:"):
        kwargs["poolclass"] = StaticPool  # one shared in-memory database
    engine = create_engine(url, **kwargs)
    event.listen(engine, "connect", _sqlite_setup)
    return engine


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    return make_engine(database_url()[0])


def get_db() -> Iterator[Session]:
    """FastAPI dependency: one session per request."""
    with Session(get_engine(), expire_on_commit=False) as session:
        yield session


def safe_database_url() -> str:
    """The configured URL with the password hidden, for logs."""
    url, _ = database_url()
    return make_url(url).render_as_string(hide_password=True)


def seed_items(engine: Engine) -> int:
    """Load the demo catalogue into an empty `items` table. Returns the number of inserted rows."""
    from .models import Item

    with Session(engine) as session:
        if session.scalar(select(func.count()).select_from(Item)):
            return 0
        session.add_all(Item(**{key: value for key, value in row.items() if key != "item_id"}) for row in ITEMS)
        session.commit()
        return len(ITEMS)


def init_db(engine: Engine | None = None, seed: bool | None = None) -> tuple[bool, str]:
    """Check the connection, create missing tables and seed the demo catalogue.

    Returns (available, detail); never raises. `seed` defaults to the SEED_ON_STARTUP setting.
    """
    # Imported here so the models register themselves on Base before create_all.
    from . import models  # noqa: F401

    try:
        engine = engine or get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        Base.metadata.create_all(engine)
        if seed_on_startup() if seed is None else seed:
            seed_items(engine)
    except Exception as exc:
        return False, f"{type(exc).__name__}: {str(exc).splitlines()[0] if str(exc) else ''}"
    return True, "ok"
