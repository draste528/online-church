"""Runtime configuration of the backend, read from environment variables.

The backend does not load a .env file itself: docker compose passes variables to the container
and for a local run you export them in the shell (see .env.example).
"""
import os
from pathlib import Path

APP_VERSION = "1.1.0"
SERVICE_NAME = "online-church-backend"

# Used when DATABASE_URL is not set (a local run without docker): a throw-away SQLite file.
DEFAULT_SQLITE_PATH = Path(__file__).resolve().parents[1] / "church_dev.db"


def database_url() -> tuple[str, str]:
    """Return (url, source) where source says whether the value came from the environment or the default."""
    value = os.getenv("DATABASE_URL", "").strip()
    if value:
        return value, "env DATABASE_URL"
    return f"sqlite:///{DEFAULT_SQLITE_PATH}", "default (local SQLite file, DATABASE_URL is not set)"


def cors_origins() -> tuple[list[str], str]:
    """Allowed browser origins: CORS_ORIGINS="http://a,http://b", "*" (everything) by default."""
    raw = os.getenv("CORS_ORIGINS", "").strip()
    if not raw:
        return ["*"], "default"
    return [o.strip() for o in raw.split(",") if o.strip()], "env CORS_ORIGINS"


def chat_mode() -> str:
    """'ai' when an OpenRouter key is configured, 'demo' otherwise."""
    return "ai" if os.getenv("OPENROUTER_API_KEY", "").strip() else "demo"
