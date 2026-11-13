"""Passwords (bcrypt), access tokens (JWT, HS256), login throttling and role checks for routes.

Usage in a router:

    @router.patch("/{order_id}")
    def update(..., user: User = Depends(require_roles("priest", "admin"))): ...

The token carries only the user id. The role and the "deleted" flag are read from the database on
every request, so a role change or a deletion takes effect immediately, not when the token expires.
"""

import threading
import time
import uuid
from collections import deque
from datetime import datetime, timedelta, timezone
from functools import lru_cache

import bcrypt
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .config import jwt_expire_minutes, jwt_secret
from .db import get_db
from .models import User

ALGORITHM = "HS256"
BCRYPT_MAX_BYTES = 72  # bcrypt only looks at the first 72 bytes (bcrypt>=4.1 refuses longer input)


# --- passwords ---------------------------------------------------------------------------------------


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


@lru_cache(maxsize=1)
def _dummy_hash() -> str:
    return hash_password("timing-equaliser")


def verify_password(password: str, password_hash: str | None) -> bool:
    """Constant-ish time: an unknown user (password_hash=None) still costs one bcrypt check."""
    data = password.encode("utf-8")
    if len(data) > BCRYPT_MAX_BYTES:
        data = b""  # such a password can never have been registered; still spend the bcrypt time
        password_hash = None
    ok = bcrypt.checkpw(data, (password_hash or _dummy_hash()).encode("ascii"))
    return ok and password_hash is not None


# --- tokens ------------------------------------------------------------------------------------------


def create_access_token(user_id: uuid.UUID) -> tuple[str, int]:
    """Return (token, lifetime in seconds)."""
    lifetime = timedelta(minutes=jwt_expire_minutes())
    now = datetime.now(timezone.utc)
    payload = {"sub": str(user_id), "iat": now, "exp": now + lifetime}
    return jwt.encode(payload, jwt_secret(), algorithm=ALGORITHM), int(lifetime.total_seconds())


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(status_code=401, detail=detail, headers={"WWW-Authenticate": "Bearer"})


def decode_access_token(token: str) -> uuid.UUID:
    """Return the user id from a valid token; raise 401 otherwise. Only HS256 is accepted (no alg=none)."""
    try:
        payload = jwt.decode(token, jwt_secret(), algorithms=[ALGORITHM], options={"require": ["exp", "iat", "sub"]})
        return uuid.UUID(payload["sub"])
    except jwt.ExpiredSignatureError:
        raise _unauthorized("Срок действия токена истёк. Войдите снова.") from None
    except (jwt.PyJWTError, ValueError, TypeError):
        raise _unauthorized("Недействительный токен.") from None


# --- route protection --------------------------------------------------------------------------------

_bearer = HTTPBearer(auto_error=False)  # we answer 401 ourselves (FastAPI versions differ: 401 vs 403)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer), db: Session = Depends(get_db)
) -> User:
    if credentials is None:
        raise _unauthorized("Требуется авторизация.")
    user = db.get(User, decode_access_token(credentials.credentials))
    if user is None or user.is_deleted:
        raise _unauthorized("Пользователь не найден.")
    return user


def require_roles(*roles: str):
    """Dependency that lets through only users with one of the given roles (403 otherwise)."""

    def check(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="Недостаточно прав.")
        return user

    return check


# --- brute-force protection ----------------------------------------------------------------------------


class LoginThrottle:
    """Counts failed logins per (email, client IP) in a sliding window, in memory of this process.

    After `max_failures` failures the pair is blocked until the oldest failure leaves the window,
    even for the right password. Keying by the pair (not by email alone) means an attacker cannot
    lock a real user out from another address.
    """

    def __init__(self, max_failures: int = 5, window_seconds: int = 15 * 60):
        self.max_failures = max_failures
        self.window = window_seconds
        self._failures: dict[tuple[str, str], deque[float]] = {}
        self._lock = threading.Lock()

    def _recent(self, key: tuple[str, str], now: float) -> deque[float]:
        times = self._failures.get(key, deque())
        while times and times[0] <= now - self.window:
            times.popleft()
        return times

    def retry_after(self, key: tuple[str, str]) -> int:
        """Seconds until the next attempt is allowed; 0 when it is allowed now."""
        now = time.monotonic()
        with self._lock:
            times = self._recent(key, now)
            if len(times) < self.max_failures:
                return 0
            return max(1, int(times[0] + self.window - now) + 1)

    def failed(self, key: tuple[str, str]) -> None:
        now = time.monotonic()
        with self._lock:
            if len(self._failures) > 10_000:  # drop stale keys so random emails cannot grow memory forever
                for stale in [k for k in self._failures if not self._recent(k, now)]:
                    del self._failures[stale]
            times = self._recent(key, now)
            times.append(now)
            self._failures[key] = times

    def reset(self, key: tuple[str, str]) -> None:
        with self._lock:
            self._failures.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._failures.clear()


login_throttle = LoginThrottle()
