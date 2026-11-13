"""Passwords (bcrypt), access tokens (JWT, HS256), login throttling and role checks for routes.

Usage in a router:

    @router.patch("/{order_id}")
    def update(..., user: User = Depends(require_roles("priest", "admin"))): ...

The token carries only the user id. The role and the "deleted" flag are read from the database on
every request, so a role change or a deletion takes effect immediately, not when the token expires.
"""

import hashlib
import re
import secrets
import threading
import time
import uuid
from collections import deque
from datetime import datetime, timedelta, timezone
from functools import lru_cache

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import delete
from sqlalchemy.orm import Session

from .config import cookie_secure, jwt_expire_minutes, jwt_secret, refresh_expire_days
from .db import get_db
from .models import RefreshToken, User

ALGORITHM = "HS256"
BCRYPT_MAX_BYTES = 72  # bcrypt only looks at the first 72 bytes (bcrypt>=4.1 refuses longer input)
PASSWORD_MIN_LENGTH = 10
PASSWORD_RULES = (
    f"Пароль: от {PASSWORD_MIN_LENGTH} символов и не длиннее {BCRYPT_MAX_BYTES} байт "
    "(латиница — 1 байт на символ, кириллица — 2), должен содержать букву и цифру."
)
PASSWORD_IDENTITY_RULE = "Пароль не должен совпадать с email или именем пользователя."


# --- passwords ---------------------------------------------------------------------------------------


def password_problem(password: str, *identities: str | None) -> str | None:
    """The reason a new password is refused, or None. `identities` are the email and username."""
    if (
        len(password) < PASSWORD_MIN_LENGTH
        or len(password.encode("utf-8")) > BCRYPT_MAX_BYTES
        or not re.search(r"[^\W\d_]", password)  # a letter of any alphabet
        or not re.search(r"\d", password)
    ):
        return PASSWORD_RULES
    if any(value and value.strip().lower() == password.lower() for value in identities):
        return PASSWORD_IDENTITY_RULE
    return None


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


# --- refresh tokens (HttpOnly cookie) ----------------------------------------------------------------

REFRESH_COOKIE = "refresh_token"
REFRESH_COOKIE_PATH = "/api/v1/auth"  # the browser sends it only to the auth endpoints


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def issue_refresh_token(db: Session, response: Response, user_id: uuid.UUID) -> None:
    """Start a session: store the token's hash and put the token itself in the cookie. Caller commits."""
    token = secrets.token_urlsafe(32)
    lifetime = timedelta(days=refresh_expire_days())
    now = datetime.now(timezone.utc)
    # Housekeeping: the user's expired sessions are dropped here instead of by a scheduled job.
    db.execute(delete(RefreshToken).where(RefreshToken.user_id == user_id, RefreshToken.expires_at <= now))
    db.add(RefreshToken(token_hash=_digest(token), user_id=user_id, expires_at=now + lifetime))
    response.set_cookie(
        REFRESH_COOKIE,
        token,
        max_age=int(lifetime.total_seconds()),
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        samesite="strict",
        secure=cookie_secure(),
    )


def clear_refresh_cookie(response: Response) -> None:
    """Max-Age=0 with the same attributes, so the browser drops the cookie."""
    response.delete_cookie(
        REFRESH_COOKIE, path=REFRESH_COOKIE_PATH, httponly=True, samesite="strict", secure=cookie_secure()
    )


def user_for_refresh_token(db: Session, token: str | None) -> User | None:
    """The live user behind a valid, unexpired refresh token; None otherwise."""
    if not token:
        return None
    row = db.get(RefreshToken, _digest(token))
    if row is None:
        return None
    expires_at = row.expires_at if row.expires_at.tzinfo else row.expires_at.replace(tzinfo=timezone.utc)  # SQLite
    if expires_at <= datetime.now(timezone.utc):
        db.delete(row)
        db.commit()
        return None
    user = db.get(User, row.user_id)
    return None if user is None or user.is_deleted else user


def revoke_refresh_token(db: Session, token: str | None) -> None:
    """Delete one session (logout). Caller commits."""
    if token:
        db.execute(delete(RefreshToken).where(RefreshToken.token_hash == _digest(token)))


def revoke_user_sessions(db: Session, user_id: uuid.UUID) -> None:
    """Delete every session of the user (password change). Caller commits."""
    db.execute(delete(RefreshToken).where(RefreshToken.user_id == user_id))


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
