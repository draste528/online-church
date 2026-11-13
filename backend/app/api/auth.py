import logging
import re
import uuid
from datetime import date, datetime, timezone
from typing import Annotated, Literal
from urllib.parse import urlsplit

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from pydantic import BaseModel, BeforeValidator, ConfigDict, EmailStr, Field, ValidationInfo, field_validator
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import User
from ..security import (
    REFRESH_COOKIE,
    clear_refresh_cookie,
    create_access_token,
    get_current_user,
    hash_password,
    issue_refresh_token,
    login_throttle,
    password_problem,
    revoke_refresh_token,
    revoke_user_sessions,
    user_for_refresh_token,
    verify_password,
)

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])

MIN_AGE = 14  # birth_year is accepted from 1900 to (current year - MIN_AGE)


def normalize_email(value: str) -> str:
    return value.strip().lower()


def _blank_to_none(value):
    """Forms send "" for an untouched field: store it as NULL, not as an empty string."""
    if isinstance(value, str):
        return value.strip() or None
    return value


Blank = BeforeValidator(_blank_to_none)
Name = Annotated[Annotated[str, Field(max_length=100)] | None, Blank]
City = Annotated[Annotated[str, Field(max_length=80)] | None, Blank]
Utm = Annotated[Annotated[str, Field(max_length=100)] | None, Blank]
Language = Annotated[Literal["ru", "en", "be"] | None, Blank]

RefreshCookie = Annotated[str | None, Cookie(alias=REFRESH_COOKIE)]


def domain_of(value: str) -> str | None:
    """'https://Www.Example.com:443/path?q=1' -> 'www.example.com'. Anything that is not a host name -> None:
    a broken referrer is analytics noise and must not block a registration."""
    try:
        host = urlsplit(value if "//" in value else "//" + value).hostname
    except ValueError:
        return None
    if not host or len(host) > 255 or not re.fullmatch(r"[a-z0-9.-]+", host):
        return None
    return host


class ProfileFields(BaseModel):
    """Fields a user fills in at registration and may change later in the cabinet (PATCH /me)."""

    first_name: Name = None
    last_name: Name = None
    city: City = None
    birth_year: int | None = None
    preferred_language: Language = None

    @field_validator("birth_year")
    @classmethod
    def plausible_birth_year(cls, value: int | None) -> int | None:
        latest = date.today().year - MIN_AGE
        if value is not None and not 1900 <= value <= latest:
            raise ValueError(f"Год рождения: от 1900 до {latest}.")
        return value


class RegisterIn(ProfileFields):
    # Unknown fields such as "role" are ignored: everyone registers as a parishioner.
    username: str = Field(min_length=3, max_length=50, pattern=r"^[\w.-]+$")
    email: EmailStr = Field(max_length=255)
    password: str  # declared after username and email: its validator compares against them
    analytics_consent: bool = False
    acquisition_source: Annotated[Literal["friends", "search", "social", "parish", "other"] | None, Blank] = None
    utm_source: Utm = None
    utm_medium: Utm = None
    utm_campaign: Utm = None
    referrer_domain: Annotated[Annotated[str, Field(max_length=2048)] | None, Blank] = None
    device_type: Annotated[Literal["mobile", "tablet", "desktop"] | None, Blank] = None

    @field_validator("email")
    @classmethod
    def lower_email(cls, value: str) -> str:
        return normalize_email(value)

    @field_validator("password")
    @classmethod
    def strong_password(cls, value: str, info: ValidationInfo) -> str:
        problem = password_problem(value, info.data.get("email"), info.data.get("username"))
        if problem:
            raise ValueError(problem)
        return value

    @field_validator("referrer_domain")
    @classmethod
    def keep_domain_only(cls, value: str | None) -> str | None:
        return domain_of(value) if value else None


class ProfileIn(ProfileFields):
    """PATCH /me. Other fields (role, email, username, ...) are ignored. A missing field stays unchanged."""

    analytics_consent: bool | None = None


class LoginIn(BaseModel):
    email: str = Field(max_length=255)
    password: str = Field(max_length=1024)


class ChangePasswordIn(BaseModel):
    current_password: str = Field(max_length=1024)
    new_password: str = Field(max_length=1024)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: uuid.UUID
    username: str
    email: str
    first_name: str | None
    last_name: str | None
    role: str
    analytics_consent: bool
    birth_year: int | None
    city: str | None
    preferred_language: str | None


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    role: str


def field_error(field: str, message: str) -> HTTPException:
    """A 422 shaped like a validation error, so the frontend shows it under the field."""
    return HTTPException(status_code=422, detail=[{"loc": ["body", field], "msg": message, "type": "value_error"}])


def drop_demographics_without_consent(user: User) -> None:
    """Birth year and city are kept only with analytics consent (ck_users_demographics_consent)."""
    if not user.analytics_consent:
        user.birth_year = None
        user.city = None


def token_reply(user: User) -> TokenOut:
    token, expires_in = create_access_token(user.user_id)
    return TokenOut(access_token=token, expires_in=expires_in, role=user.role)


def throttle_key(email: str, request: Request) -> tuple[str, str]:
    return email, request.client.host if request.client else ""


def check_throttle(key: tuple[str, str]) -> None:
    wait = login_throttle.retry_after(key)
    if wait:
        log.warning("Password attempts throttled for a user from %s", key[1])
        raise HTTPException(
            status_code=429,
            detail="Слишком много неудачных попыток входа. Попробуйте позже.",
            headers={"Retry-After": str(wait)},
        )


@router.post("/register", response_model=UserOut, status_code=201)
def register(payload: RegisterIn, db: Session = Depends(get_db)):
    """Register a parishioner. Email and username are unique ignoring case. Answers with the /me profile."""
    taken = db.scalar(
        select(User.user_id).where(
            or_(User.email == payload.email, func.lower(User.username) == payload.username.lower())
        )
    )
    if taken:
        raise HTTPException(status_code=409, detail="Пользователь с таким email или именем уже существует.")

    user = User(
        **payload.model_dump(exclude={"password"}),
        password_hash=hash_password(payload.password),
        role="parishioner",
    )
    drop_demographics_without_consent(user)
    db.add(user)
    try:
        db.commit()
    except IntegrityError:  # a concurrent registration with the same email/username won the race
        db.rollback()
        raise HTTPException(status_code=409, detail="Пользователь с таким email или именем уже существует.") from None
    log.info("Registered user %s", user.user_id)
    return user


@router.post("/login", response_model=TokenOut)
def login(payload: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    """Exchange email and password for an access token; the refresh token goes to an HttpOnly cookie.
    Too many failures answer 429."""
    email = normalize_email(payload.email)
    key = throttle_key(email, request)
    check_throttle(key)

    user = db.scalar(select(User).where(User.email == email, User.is_deleted.is_(False)))
    if not verify_password(payload.password, user.password_hash if user else None):
        login_throttle.failed(key)
        raise HTTPException(status_code=401, detail="Неверный email или пароль.")

    login_throttle.reset(key)
    user.last_seen = datetime.now(timezone.utc)
    issue_refresh_token(db, response, user.user_id)
    db.commit()
    return token_reply(user)


@router.post("/refresh", response_model=TokenOut)
def refresh(refresh_token: RefreshCookie = None, db: Session = Depends(get_db)):
    """A new access token for the refresh cookie (after F5 or when the access token expired)."""
    user = user_for_refresh_token(db, refresh_token)
    if user is None:
        raise HTTPException(status_code=401, detail="Сессия истекла. Войдите снова.")
    user.last_seen = datetime.now(timezone.utc)
    db.commit()
    return token_reply(user)


@router.post("/logout", status_code=204)
def logout(response: Response, refresh_token: RefreshCookie = None, db: Session = Depends(get_db)):
    """Revoke the session behind the cookie and delete the cookie. Works without an access token."""
    revoke_refresh_token(db, refresh_token)
    db.commit()
    clear_refresh_cookie(response)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    """The profile of the token's owner (any role)."""
    return user


@router.patch("/me", response_model=UserOut)
def update_me(payload: ProfileIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Change name, city, birth year, language or analytics consent. Withdrawn consent erases birth year and city."""
    changes = payload.model_dump(exclude_unset=True)
    if changes.get("analytics_consent") is None:
        changes.pop("analytics_consent", None)
    for field, value in changes.items():
        setattr(user, field, value)
    drop_demographics_without_consent(user)
    db.commit()
    return user


@router.post("/change-password", status_code=204)
def change_password(
    payload: ChangePasswordIn,
    request: Request,
    response: Response,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Set a new password. Every session (refresh cookie) is revoked; this browser gets a fresh cookie."""
    key = throttle_key(user.email, request)  # shares the login counter: guessing here is guessing a login
    check_throttle(key)
    if not verify_password(payload.current_password, user.password_hash):
        login_throttle.failed(key)
        raise field_error("current_password", "Неверный текущий пароль.")
    problem = password_problem(payload.new_password, user.email, user.username)
    if problem:
        raise field_error("new_password", problem)

    user.password_hash = hash_password(payload.new_password)
    revoke_user_sessions(db, user.user_id)
    issue_refresh_token(db, response, user.user_id)
    db.commit()
    log.info("User %s changed the password; other sessions revoked", user.user_id)
