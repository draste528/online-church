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


DEFAULT_CORS_ORIGINS = ["http://localhost:3000"]


def cors_origins() -> tuple[list[str], str]:
    """Allowed browser origins: CORS_ORIGINS="http://a,http://b", the local frontend by default.

    The auth endpoints use a cookie, so CORS runs with credentials, and browsers refuse credentials
    with "*": a wildcard is rejected here (the backend does not start) instead of silently breaking login.
    """
    raw = os.getenv("CORS_ORIGINS", "").strip()
    if not raw:
        return list(DEFAULT_CORS_ORIGINS), "default"
    origins = [o.strip().rstrip("/") for o in raw.split(",") if o.strip()]
    if "*" in origins:
        raise RuntimeError(
            'CORS_ORIGINS="*" cannot be used: login sends a cookie and browsers forbid "*" with credentials. '
            "List the frontend addresses instead, e.g. CORS_ORIGINS=http://localhost:3000"
        )
    return origins or list(DEFAULT_CORS_ORIGINS), "env CORS_ORIGINS"


CHAT_PROVIDERS = {"openrouter": "OPENROUTER_API_KEY", "hive": "HIVE_API_KEY"}  # provider -> env var with its key


def chat_provider() -> str:
    """CHAT_PROVIDER: 'openrouter' (default) or 'hive'. An unknown value falls back to the default."""
    value = os.getenv("CHAT_PROVIDER", "").strip().lower()
    return value if value in CHAT_PROVIDERS else "openrouter"


def chat_mode() -> str:
    """'ai' when the key of the selected chat provider is configured, 'demo' otherwise."""
    return "ai" if os.getenv(CHAT_PROVIDERS[chat_provider()], "").strip() else "demo"


def seed_on_startup() -> bool:
    """SEED_ON_STARTUP (default true): fill an empty `items` table with the demo catalogue."""
    return os.getenv("SEED_ON_STARTUP", "true").strip().lower() not in {"0", "false", "no", "off"}


JWT_SECRET_MIN_LENGTH = 32


def jwt_secret() -> str:
    """JWT_SECRET signs the access tokens. There is deliberately no default: the repository is public,
    so a default secret would let anyone forge a token for any account. Raises when it is missing or short."""
    value = os.getenv("JWT_SECRET", "").strip()
    if len(value) < JWT_SECRET_MIN_LENGTH:
        raise RuntimeError(
            f"JWT_SECRET is not set or shorter than {JWT_SECRET_MIN_LENGTH} characters. "
            'Generate one: python -c "import secrets; print(secrets.token_urlsafe(48))"'
        )
    return value


def jwt_expire_minutes() -> int:
    """JWT_EXPIRE_MINUTES: lifetime of an access token, 60 by default (1..1440)."""
    try:
        value = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))
    except ValueError:
        return 60
    return min(max(value, 1), 24 * 60)


def refresh_expire_days() -> int:
    """REFRESH_EXPIRE_DAYS: lifetime of a refresh token (the HttpOnly cookie), 30 days by default (1..365)."""
    try:
        value = int(os.getenv("REFRESH_EXPIRE_DAYS", "30"))
    except ValueError:
        return 30
    return min(max(value, 1), 365)


def cookie_secure() -> bool:
    """COOKIE_SECURE (default true): send the refresh cookie over HTTPS only.

    Browsers treat http://localhost as secure, so the default also works for local development;
    set it to false only when the frontend is opened over plain http on another host name."""
    return os.getenv("COOKIE_SECURE", "true").strip().lower() not in {"0", "false", "no", "off"}
