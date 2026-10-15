"""One lazily created SQLAlchemy engine shared by the API routes (tests replace it with SQLite)."""
from functools import lru_cache

from sqlalchemy import Engine, create_engine

from analytics.src.config import settings


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    return create_engine(settings.database_url, pool_pre_ping=True)
