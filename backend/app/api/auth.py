import logging
import re
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import User
from ..security import (
    BCRYPT_MAX_BYTES,
    create_access_token,
    get_current_user,
    hash_password,
    login_throttle,
    verify_password,
)

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])

PASSWORD_MIN_LENGTH = 8
PASSWORD_RULES = (
    f"Пароль: от {PASSWORD_MIN_LENGTH} символов и не длиннее {BCRYPT_MAX_BYTES} байт "
    "(латиница — 1 байт на символ, кириллица — 2), должен содержать букву и цифру."
)


def normalize_email(value: str) -> str:
    return value.strip().lower()


class RegisterIn(BaseModel):
    # Unknown fields such as "role" are ignored: everyone registers as a parishioner.
    username: str = Field(min_length=3, max_length=50, pattern=r"^[\w.-]+$")
    email: EmailStr = Field(max_length=255)
    password: str
    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)

    @field_validator("email")
    @classmethod
    def lower_email(cls, value: str) -> str:
        return normalize_email(value)

    @field_validator("password")
    @classmethod
    def strong_password(cls, value: str) -> str:
        if (
            len(value) < PASSWORD_MIN_LENGTH
            or len(value.encode("utf-8")) > BCRYPT_MAX_BYTES
            or not re.search(r"[^\W\d_]", value)  # a letter of any alphabet
            or not re.search(r"\d", value)
        ):
            raise ValueError(PASSWORD_RULES)
        return value


class LoginIn(BaseModel):
    email: str = Field(max_length=255)
    password: str = Field(max_length=1024)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: uuid.UUID
    username: str
    email: str
    first_name: str | None
    last_name: str | None
    role: str


class RegisterOut(BaseModel):
    user_id: uuid.UUID
    username: str
    role: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    role: str


@router.post("/register", response_model=RegisterOut, status_code=201)
def register(payload: RegisterIn, db: Session = Depends(get_db)):
    """Register a parishioner. Email and username are unique ignoring case."""
    taken = db.scalar(
        select(User.user_id).where(
            or_(User.email == payload.email, func.lower(User.username) == payload.username.lower())
        )
    )
    if taken:
        raise HTTPException(status_code=409, detail="Пользователь с таким email или именем уже существует.")

    user = User(
        username=payload.username,
        email=payload.email,
        password_hash=hash_password(payload.password),
        first_name=payload.first_name,
        last_name=payload.last_name,
        role="parishioner",
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:  # a concurrent registration with the same email/username won the race
        db.rollback()
        raise HTTPException(status_code=409, detail="Пользователь с таким email или именем уже существует.") from None
    log.info("Registered user %s", user.user_id)
    return RegisterOut(user_id=user.user_id, username=user.username, role=user.role)


@router.post("/login", response_model=TokenOut)
def login(payload: LoginIn, request: Request, db: Session = Depends(get_db)):
    """Exchange email and password for an access token. Too many failures answer 429."""
    email = normalize_email(payload.email)
    key = (email, request.client.host if request.client else "")
    wait = login_throttle.retry_after(key)
    if wait:
        log.warning("Login throttled for a user from %s", key[1])
        raise HTTPException(
            status_code=429,
            detail="Слишком много неудачных попыток входа. Попробуйте позже.",
            headers={"Retry-After": str(wait)},
        )

    user = db.scalar(select(User).where(User.email == email, User.is_deleted.is_(False)))
    if not verify_password(payload.password, user.password_hash if user else None):
        login_throttle.failed(key)
        raise HTTPException(status_code=401, detail="Неверный email или пароль.")

    login_throttle.reset(key)
    user.last_seen = datetime.now(timezone.utc)
    db.commit()
    token, expires_in = create_access_token(user.user_id)
    return TokenOut(access_token=token, expires_in=expires_in, role=user.role)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    """The profile of the token's owner (any role)."""
    return user
