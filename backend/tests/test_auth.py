import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.config import cors_origins, jwt_secret
from backend.app.db import get_db, init_db, make_engine
from backend.app.main import app
from backend.app.models import RefreshToken, User
from backend.app.security import login_throttle


def browser() -> TestClient:
    """A client with its own cookie jar. https, because the refresh cookie is Secure by default."""
    return TestClient(app, base_url="https://testserver")


client = browser()

REGISTER = "/api/v1/auth/register"
LOGIN = "/api/v1/auth/login"
ME = "/api/v1/auth/me"
REFRESH = "/api/v1/auth/refresh"
LOGOUT = "/api/v1/auth/logout"
CHANGE_PASSWORD = "/api/v1/auth/change-password"
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
    client.cookies.clear()
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


def test_register_answers_with_the_me_profile():
    profile = {"first_name": "Ольга", "city": "Минск", "birth_year": 1990, "preferred_language": "be"}
    body = register(analytics_consent=True, **profile).json()
    assert body == client.get(ME, headers=auth(token_for())).json()
    assert body["first_name"] == "Ольга" and body["email"] == "olga@example.com"
    assert (body["analytics_consent"], body["city"], body["birth_year"], body["preferred_language"]) == (
        True,
        "Минск",
        1990,
        "be",
    )
    assert "utm_source" not in body and "password_hash" not in body


def stored_user(engine) -> User:
    with Session(engine) as session:
        return session.scalars(select(User)).one()


def test_registration_analytics_fields_are_stored(database):
    res = register(
        analytics_consent=True,
        acquisition_source="parish",
        utm_source="vk",
        utm_medium="social",
        utm_campaign="easter",
        referrer_domain="https://WWW.Example.COM:443/path/page?q=1#top",
        device_type="mobile",
    )
    assert res.status_code == 201, res.text
    user = stored_user(database)
    assert (user.acquisition_source, user.utm_source, user.utm_medium, user.utm_campaign) == (
        "parish",
        "vk",
        "social",
        "easter",
    )
    assert user.referrer_domain == "www.example.com" and user.device_type == "mobile"


@pytest.mark.parametrize(
    ("raw", "domain"),
    [("example.com/news", "example.com"), ("HTTP://Sub.Example.org", "sub.example.org"), ("not a domain", None)],
)
def test_referrer_is_cut_to_the_domain(database, raw, domain):
    assert register(referrer_domain=raw).status_code == 201
    assert stored_user(database).referrer_domain == domain


def test_demographics_are_dropped_without_consent(database):
    body = register(city="Минск", birth_year=1990, preferred_language="en", acquisition_source="friends").json()
    assert body["analytics_consent"] is False and body["city"] is None and body["birth_year"] is None
    user = stored_user(database)
    assert user.city is None and user.birth_year is None
    assert user.preferred_language == "en" and user.acquisition_source == "friends"  # not demographics


def test_empty_form_fields_are_stored_as_null(database):
    assert register(first_name="", last_name="  ", acquisition_source="").status_code == 201
    user = stored_user(database)
    assert user.first_name is None and user.last_name is None and user.acquisition_source is None


@pytest.mark.parametrize(
    "extra",
    [
        {"birth_year": 1899},
        {"birth_year": datetime.now().year - 13},
        {"city": "x" * 81},
        {"acquisition_source": "tv"},
        {"preferred_language": "de"},
        {"device_type": "watch"},
        {"utm_source": "x" * 101},
    ],
)
def test_invalid_profile_fields_are_422(extra):
    res = register(analytics_consent=True, **extra)
    assert res.status_code == 422
    assert res.json()["detail"][0]["loc"] == ["body", next(iter(extra))]


def test_youngest_allowed_birth_year_is_accepted():
    assert register(analytics_consent=True, birth_year=datetime.now().year - 14).status_code == 201


def test_demographics_consent_is_enforced_by_the_database(database):
    with Session(database) as session:
        session.add(User(username="x1", email="x1@example.com", password_hash="h", city="Минск"))
        with pytest.raises(IntegrityError):
            session.commit()


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


def test_database_rejects_usernames_differing_only_in_case(database):
    # What a race between two concurrent sign-ups would do, past the application's own check.
    with Session(database) as session:
        session.add(User(username="Olga", email="a@example.com", password_hash="h"))
        session.commit()
        session.add(User(username="olga", email="b@example.com", password_hash="h"))
        with pytest.raises(IntegrityError):
            session.commit()


@pytest.mark.parametrize(
    "password",
    [
        "qwerty",  # too short
        "Abcdefg12",  # 9 characters
        "passwordpassword",  # no digit
        "1234567890",  # no letter
        "a1" + "x" * 71,  # 73 bytes
        "Пароль1" + "я" * 30,  # 37 characters but 74 bytes in UTF-8
    ],
)
def test_weak_or_too_long_password_is_rejected(password):
    res = register(password=password)
    assert res.status_code == 422
    assert "Пароль" in res.json()["detail"][0]["msg"]


@pytest.mark.parametrize(
    ("username", "email", "password"),
    [("olga", "olga2026@example.com", "OLGA2026@example.com"), ("olga2026ab", "olga@example.com", "Olga2026AB")],
)
def test_password_equal_to_email_or_username_is_rejected(username, email, password):
    res = register(username=username, email=email, password=password)
    assert res.status_code == 422
    assert res.json()["detail"][0]["loc"] == ["body", "password"]


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


# --- refresh cookie, logout ------------------------------------------------------------------------


def set_cookie_header(res) -> str:
    return "; ".join(v for k, v in res.headers.multi_items() if k == "set-cookie")


def test_login_sets_http_only_refresh_cookie():
    register()
    cookie = set_cookie_header(login())
    assert cookie.startswith("refresh_token=")
    for flag in ("HttpOnly", "SameSite=strict", "Path=/api/v1/auth", "Secure", "Max-Age=2592000"):
        assert flag in cookie, cookie


def test_cookie_without_secure_flag_when_disabled(monkeypatch):
    monkeypatch.setenv("COOKIE_SECURE", "false")
    register()
    assert "Secure" not in set_cookie_header(login())


def test_refresh_returns_new_access_token_like_login():
    register()
    login()
    res = client.post(REFRESH)  # only the cookie, as after F5
    assert res.status_code == 200
    body = res.json()
    assert set(body) == {"access_token", "token_type", "expires_in", "role"}
    assert body["token_type"] == "bearer" and body["role"] == "parishioner"
    assert client.get(ME, headers=auth(body["access_token"])).status_code == 200


def test_refresh_without_or_with_unknown_cookie_is_401():
    assert client.post(REFRESH).status_code == 401
    client.cookies.set("refresh_token", "made-up", domain="testserver", path="/api/v1/auth")
    assert client.post(REFRESH).status_code == 401


def test_refresh_token_is_stored_hashed(database):
    register()
    login()
    token = client.cookies["refresh_token"]
    with Session(database) as session:
        stored = session.scalars(select(RefreshToken.token_hash)).one()
    assert token not in stored and len(stored) == 64


def test_expired_refresh_token_is_401(database):
    register()
    login()
    with Session(database) as session:
        session.scalars(select(RefreshToken)).one().expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        session.commit()
    assert client.post(REFRESH).status_code == 401


def test_refresh_of_deleted_user_is_401(database):
    register()
    login()
    with Session(database) as session:
        session.scalars(select(User)).one().is_deleted = True
        session.commit()
    assert client.post(REFRESH).status_code == 401


def test_logout_revokes_refresh_token_and_deletes_cookie():
    register()
    login()
    stolen = client.cookies["refresh_token"]
    res = client.post(LOGOUT)
    assert res.status_code == 204 and res.content == b""
    cookie = set_cookie_header(res)
    assert cookie.startswith("refresh_token=") and "Max-Age=0" in cookie and "Path=/api/v1/auth" in cookie
    assert client.post(REFRESH).status_code == 401
    # The revoked token is useless even if someone kept a copy of the cookie.
    client.cookies.set("refresh_token", stolen, domain="testserver", path="/api/v1/auth")
    assert client.post(REFRESH).status_code == 401


def test_logout_without_cookie_is_204():
    assert client.post(LOGOUT).status_code == 204


def test_logout_ends_only_this_session():
    register()
    login()
    other = browser()
    other.post(LOGIN, json={"email": "olga@example.com", "password": PASSWORD})
    client.post(LOGOUT)
    assert other.post(REFRESH).status_code == 200


# --- PATCH /me -------------------------------------------------------------------------------------


def patch_me(token: str, **fields):
    return client.patch(ME, json=fields, headers=auth(token))


def test_patch_me_changes_profile_and_ignores_role_and_email():
    register()
    token = token_for()
    res = patch_me(
        token,
        first_name="Ольга",
        last_name="Петрова",
        analytics_consent=True,
        city="Гродно",
        birth_year=1985,
        preferred_language="en",
        role="admin",
        email="evil@example.com",
        username="admin",
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert (body["first_name"], body["last_name"], body["city"], body["birth_year"], body["preferred_language"]) == (
        "Ольга",
        "Петрова",
        "Гродно",
        1985,
        "en",
    )
    assert body["analytics_consent"] is True
    assert (body["role"], body["email"], body["username"]) == ("parishioner", "olga@example.com", "olga")
    assert client.get(ME, headers=auth(token)).json() == body


def test_patch_me_keeps_fields_that_are_not_sent():
    register(first_name="Ольга", analytics_consent=True, city="Минск")
    body = patch_me(token_for(), last_name="Петрова").json()
    assert body["first_name"] == "Ольга" and body["city"] == "Минск" and body["analytics_consent"] is True


def test_withdrawn_consent_erases_birth_year_and_city():
    register(analytics_consent=True, city="Минск", birth_year=1990, preferred_language="ru")
    body = patch_me(token_for(), analytics_consent=False).json()
    assert body["analytics_consent"] is False and body["city"] is None and body["birth_year"] is None
    assert body["preferred_language"] == "ru"


def test_patch_me_without_consent_does_not_store_demographics():
    register()
    body = patch_me(token_for(), city="Минск", birth_year=1990).json()
    assert body["city"] is None and body["birth_year"] is None


def test_patch_me_validates_and_needs_a_token():
    register()
    assert patch_me(token_for(), birth_year=1800).status_code == 422
    assert client.patch(ME, json={"first_name": "X"}).status_code == 401


# --- change password -------------------------------------------------------------------------------

NEW_PASSWORD = "N3wPassword!"


def change_password(token: str, current=PASSWORD, new=NEW_PASSWORD):
    return client.post(CHANGE_PASSWORD, json={"current_password": current, "new_password": new}, headers=auth(token))


def test_change_password():
    register()
    res = change_password(token_for())
    assert res.status_code == 204
    assert login().status_code == 401
    assert login(password=NEW_PASSWORD).status_code == 200


def test_change_password_with_wrong_current_password_is_422_on_that_field():
    register()
    res = change_password(token_for(), current="Wr0ngPass!")
    assert res.status_code == 422
    assert res.json()["detail"][0]["loc"] == ["body", "current_password"]
    assert login().status_code == 200


@pytest.mark.parametrize("new", ["short1", "passwordpassword", "OLGA2026ab"])
def test_change_password_checks_the_new_password_rules(new):
    register(username="olga2026ab")
    res = change_password(token_for(), new=new)
    assert res.status_code == 422
    assert res.json()["detail"][0]["loc"] == ["body", "new_password"]


def test_change_password_revokes_other_sessions_but_keeps_this_one():
    register()
    other = browser()
    other.post(LOGIN, json={"email": "olga@example.com", "password": PASSWORD})
    assert change_password(token_for()).status_code == 204
    assert other.post(REFRESH).status_code == 401
    assert client.post(REFRESH).status_code == 200  # this browser got a fresh cookie


def test_change_password_guessing_is_throttled():
    register()
    token = token_for()
    for _ in range(5):
        change_password(token, current="Wr0ngPass!")
    assert change_password(token).status_code == 429


def test_change_password_needs_a_token():
    assert client.post(CHANGE_PASSWORD, json={"current_password": "a", "new_password": "b"}).status_code == 401


# --- CORS ------------------------------------------------------------------------------------------

FRONTEND = "http://localhost:3000"


@pytest.mark.parametrize("path", [LOGIN, REFRESH, LOGOUT, CHANGE_PASSWORD, ME])
def test_cors_preflight_allows_the_frontend_with_credentials(path):
    res = client.options(
        path,
        headers={
            "Origin": FRONTEND,
            "Access-Control-Request-Method": "PATCH" if path == ME else "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    assert res.status_code == 200
    assert res.headers["access-control-allow-origin"] == FRONTEND
    assert res.headers["access-control-allow-credentials"] == "true"


def test_cors_response_carries_credentials_header():
    register()
    res = client.post(LOGIN, json={"email": "olga@example.com", "password": PASSWORD}, headers={"Origin": FRONTEND})
    assert res.headers["access-control-allow-origin"] == FRONTEND
    assert res.headers["access-control-allow-credentials"] == "true"


def test_cors_rejects_other_origins():
    res = client.options(LOGIN, headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"})
    assert res.status_code == 400
    assert "access-control-allow-origin" not in res.headers


def test_cors_origins_default_and_list(monkeypatch):
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    assert cors_origins()[0] == [FRONTEND]
    monkeypatch.setenv("CORS_ORIGINS", "http://a.example/, http://b.example")
    assert cors_origins()[0] == ["http://a.example", "http://b.example"]


def test_cors_wildcard_is_refused(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "http://a.example,*")
    with pytest.raises(RuntimeError, match="CORS_ORIGINS"):
        cors_origins()
