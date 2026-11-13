import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.config import jwt_secret
from backend.app.db import get_db, init_db, make_engine
from backend.app.main import app
from backend.app.models import User
from backend.app.security import login_throttle

client = TestClient(app)

REGISTER = "/api/v1/auth/register"
LOGIN = "/api/v1/auth/login"
ME = "/api/v1/auth/me"
PASSWORD = "Str0ngPass!"


@pytest.fixture(autouse=True)
def database():
    """A fresh in-memory SQLite database and an empty login-failure counter for every test."""
    engine = make_engine("sqlite://")
    init_db(engine, seed=False)

    def override_db():
        with Session(engine, expire_on_commit=False) as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    login_throttle.clear()
    yield engine
    app.dependency_overrides.pop(get_db, None)
    engine.dispose()


def register(username="olga", email="olga@example.com", password=PASSWORD, **extra):
    return client.post(REGISTER, json={"username": username, "email": email, "password": password, **extra})


def login(email="olga@example.com", password=PASSWORD):
    return client.post(LOGIN, json={"email": email, "password": password})


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def token_for(email="olga@example.com", password=PASSWORD) -> str:
    res = login(email, password)
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


def set_role(engine, email: str, role: str) -> None:
    with Session(engine) as session:
        session.scalars(select(User).where(User.email == email)).one().role = role
        session.commit()


def forge(payload: dict, secret: str | None = None, algorithm="HS256") -> str:
    return jwt.encode(payload, secret or jwt_secret(), algorithm=algorithm)


# --- configuration ---------------------------------------------------------------------------------


def test_missing_jwt_secret_stops_startup(monkeypatch):
    monkeypatch.delenv("JWT_SECRET")
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        with TestClient(app):
            pass


def test_short_jwt_secret_is_rejected(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "secret")
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        jwt_secret()


# --- registration ----------------------------------------------------------------------------------


def test_register_creates_parishioner_even_if_role_is_sent():
    res = register(role="admin")
    assert res.status_code == 201
    body = res.json()
    assert body["username"] == "olga" and body["role"] == "parishioner"
    uuid.UUID(body["user_id"])


def test_register_stores_password_hash_not_password(database):
    register()
    with Session(database) as session:
        stored = session.scalars(select(User)).one().password_hash
    assert PASSWORD not in stored and stored.startswith("$2")


def test_email_is_stored_lower_case_and_unique_ignoring_case(database):
    assert register(email="  Olga@Example.COM ").status_code == 201
    with Session(database) as session:
        assert session.scalars(select(User.email)).one() == "olga@example.com"
    res = register(username="other", email="olga@example.com")
    assert res.status_code == 409
    assert login(email="OLGA@example.com").status_code == 200


def test_username_is_unique_ignoring_case():
    register()
    assert register(username="OLGA", email="other@example.com").status_code == 409


@pytest.mark.parametrize(
    "password",
    [
        "qwerty",  # too short
        "password",  # no digit
        "12345678",  # no letter
        "a1" + "x" * 71,  # 73 bytes
        "Пароль1" + "я" * 30,  # 37 characters but 74 bytes in UTF-8
    ],
)
def test_weak_or_too_long_password_is_rejected(password):
    res = register(password=password)
    assert res.status_code == 422
    assert "Пароль" in res.json()["detail"][0]["msg"]


def test_72_byte_password_is_accepted():
    password = "a1" + "x" * 70
    assert register(password=password).status_code == 201
    assert login(password=password).status_code == 200


def test_bad_username_is_rejected():
    assert register(username="o l g a").status_code == 422


# --- login -----------------------------------------------------------------------------------------


def test_login_returns_token_and_role():
    register()
    body = login().json()
    assert body["token_type"] == "bearer" and body["role"] == "parishioner"
    assert body["expires_in"] == 60 * 60
    assert client.get(ME, headers=auth(body["access_token"])).json()["email"] == "olga@example.com"


def test_wrong_password_and_unknown_email_give_the_same_401():
    register()
    wrong = login(password="Wr0ngPass!")
    unknown = login(email="nobody@example.com")
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


def test_overlong_password_at_login_is_401_not_500():
    register()
    assert login(password="x" * 500).status_code == 401


def test_deleted_user_cannot_log_in(database):
    register()
    with Session(database) as session:
        session.scalars(select(User)).one().is_deleted = True
        session.commit()
    assert login().status_code == 401


def test_repeated_failures_block_login_even_with_right_password():
    register()
    for _ in range(5):
        assert login(password="Wr0ngPass!").status_code == 401
    res = login()
    assert res.status_code == 429
    assert int(res.headers["Retry-After"]) > 0


def test_successful_login_resets_failure_counter():
    register()
    for _ in range(4):
        login(password="Wr0ngPass!")
    assert login().status_code == 200
    for _ in range(4):
        login(password="Wr0ngPass!")
    assert login().status_code == 200


# --- token checks ----------------------------------------------------------------------------------


def test_me_without_token_is_401():
    res = client.get(ME)
    assert res.status_code == 401
    assert res.headers["WWW-Authenticate"] == "Bearer"


@pytest.mark.parametrize("make_token", ["garbage", "other_secret", "alg_none", "expired", "no_exp", "bad_sub"])
def test_invalid_tokens_are_401(make_token):
    register()
    user_id = client.get(ME, headers=auth(token_for())).json()["user_id"]
    now = datetime.now(timezone.utc)
    claims = {"sub": user_id, "iat": now, "exp": now + timedelta(hours=1)}
    token = {
        "garbage": lambda: "not-a-jwt",
        "other_secret": lambda: forge(claims, secret="another-secret-of-the-required-length-000"),
        "alg_none": lambda: jwt.encode(claims, None, algorithm="none"),
        "expired": lambda: forge({**claims, "exp": now - timedelta(seconds=1)}),
        "no_exp": lambda: forge({"sub": user_id, "iat": now}),
        "bad_sub": lambda: forge({**claims, "sub": "not-a-uuid"}),
    }[make_token]()
    assert client.get(ME, headers=auth(token)).status_code == 401


def test_token_of_deleted_user_is_rejected(database):
    register()
    token = token_for()
    with Session(database) as session:
        session.scalars(select(User)).one().is_deleted = True
        session.commit()
    assert client.get(ME, headers=auth(token)).status_code == 401


# --- roles -----------------------------------------------------------------------------------------


def role_url(user_id: str) -> str:
    return f"/api/v1/users/{user_id}/role"


def test_parishioner_and_priest_cannot_change_roles(database):
    register()
    register(username="ivan", email="ivan@example.com")
    target = client.get(ME, headers=auth(token_for("ivan@example.com"))).json()["user_id"]
    token = token_for()
    assert client.patch(role_url(target), json={"role": "admin"}, headers=auth(token)).status_code == 403
    set_role(database, "olga@example.com", "priest")
    assert client.patch(role_url(target), json={"role": "admin"}, headers=auth(token)).status_code == 403


def test_admin_changes_role_and_it_applies_to_existing_token(database):
    register(username="admin", email="admin@example.com")
    set_role(database, "admin@example.com", "admin")
    admin_token = token_for("admin@example.com")
    register()
    olga_token = token_for()
    olga_id = client.get(ME, headers=auth(olga_token)).json()["user_id"]

    res = client.patch(role_url(olga_id), json={"role": "priest"}, headers=auth(admin_token))
    assert res.status_code == 200 and res.json()["role"] == "priest"
    # The role is read from the database, so the token issued before the change already sees it.
    assert client.get(ME, headers=auth(olga_token)).json()["role"] == "priest"

    # Demotion works the same way: the former admin loses access immediately.
    client.patch(role_url(olga_id), json={"role": "admin"}, headers=auth(admin_token))
    set_role(database, "admin@example.com", "parishioner")
    assert client.patch(role_url(olga_id), json={"role": "priest"}, headers=auth(admin_token)).status_code == 403


def test_admin_role_change_validation(database):
    register(username="admin", email="admin@example.com")
    set_role(database, "admin@example.com", "admin")
    token = token_for("admin@example.com")
    admin_id = client.get(ME, headers=auth(token)).json()["user_id"]
    assert client.patch(role_url(admin_id), json={"role": "priest"}, headers=auth(token)).status_code == 400
    assert client.patch(role_url(uuid.uuid4()), json={"role": "priest"}, headers=auth(token)).status_code == 404
    assert client.patch(role_url(admin_id), json={"role": "superuser"}, headers=auth(token)).status_code == 422
