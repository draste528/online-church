from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from analytics.src.api.main import app
from analytics.src.api.routes import registrations as route
from analytics.src.config import settings
from analytics.src.db import get_engine

URL = "/api/v1/analytics/registrations/summary"
NOW = datetime(2026, 11, 13, 12, 0, tzinfo=UTC)

# The columns of docs/church_db_init.sql today (no registration profile yet).
CREATE_USERS_BASE = """
CREATE TABLE users (user_id TEXT PRIMARY KEY, username TEXT, email TEXT, password_hash TEXT, role TEXT NOT NULL,
                    created_at TEXT NOT NULL, last_seen TEXT, is_deleted INTEGER DEFAULT 0)
"""
# The same table after analytics/sql/05_users_registration_profile.sql.
PROFILE_COLUMNS = [
    "analytics_consent INTEGER DEFAULT 0", "birth_year INTEGER", "city TEXT", "acquisition_source TEXT",
    "preferred_language TEXT", "utm_source TEXT", "utm_medium TEXT", "utm_campaign TEXT", "referrer_domain TEXT",
    "device_type TEXT",
]
CREATE_DONATIONS = """
CREATE TABLE donations (donation_id TEXT PRIMARY KEY, user_id TEXT, amount NUMERIC, payment_status TEXT,
                        created_at TEXT NOT NULL)
"""


def make_engine(profile: bool):
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    with eng.begin() as conn:
        conn.execute(text(CREATE_USERS_BASE))
        conn.execute(text(CREATE_DONATIONS))
        if profile:
            for column in PROFILE_COLUMNS:
                conn.execute(text(f"ALTER TABLE users ADD COLUMN {column}"))
    return eng


def add_user(engine, user_id, created_at, role="parishioner", **fields):
    values = {"user_id": user_id, "username": f"u{user_id}", "email": f"{user_id}@secret.example",
              "password_hash": "hash-must-not-leak", "role": role, "created_at": created_at, **fields}
    names = ", ".join(values)
    params = ", ".join(f":{k}" for k in values)
    with engine.begin() as conn:
        conn.execute(text(f"INSERT INTO users ({names}) VALUES ({params})"), values)


def add_donation(engine, donation_id, user_id, created_at, status="completed"):
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO donations VALUES (:d, :u, 10, :s, :c)"),
                     {"d": donation_id, "u": user_id, "s": status, "c": created_at})


@pytest.fixture()
def client_for(monkeypatch):
    monkeypatch.setattr(settings, "ANALYTICS_TIMEZONE", "UTC")
    monkeypatch.setattr(route, "now_utc", lambda: NOW)

    def make(engine):
        app.dependency_overrides[get_engine] = lambda: engine
        return TestClient(app)

    yield make
    app.dependency_overrides.pop(get_engine, None)


def by_key(buckets):
    return {b["key"]: b["count"] for b in buckets}


def test_empty_database(client_for):
    body = client_for(make_engine(profile=True)).get(URL, params={"days": 7}).json()
    assert body["total_users"] == 0 and body["new_users"] == 0
    assert body["growth_percent"] is None
    assert [d["registrations"] for d in body["by_day"]] == [0] * 7
    assert body["by_age_group"] == [] and body["top_cities"] == []
    assert body["activation"]["activated_users"] == 0


def test_works_before_profile_columns_exist(client_for):
    engine = make_engine(profile=False)
    add_user(engine, "a", "2026-11-12T10:00:00+00:00", last_seen="2026-11-13T11:00:00+00:00")
    add_user(engine, "b", "2026-11-12T11:00:00+00:00", role="priest", last_seen="2026-11-12T11:05:00+00:00")
    body = client_for(engine).get(URL, params={"days": 7, "min_group": 1}).json()
    assert body["available_fields"] == ["is_deleted", "last_seen"]
    assert body["new_users"] == 2 and body["consent_available"] is False
    assert by_key(body["by_role"]) == {"parishioner": 1, "priest": 1, "admin": 0}
    assert body["by_source"] == [] and body["by_age_group"] == []
    assert body["activation"]["returned_users"] == 1 and body["activation"]["return_rate_percent"] == 50.0


def test_period_growth_and_deleted_users(client_for):
    engine = make_engine(profile=True)
    for i in range(3):
        add_user(engine, f"new{i}", f"2026-11-1{i}T09:00:00+00:00")
    add_user(engine, "old", "2026-11-03T09:00:00+00:00")
    add_user(engine, "gone", "2026-11-12T09:00:00+00:00", is_deleted=1)
    add_user(engine, "ancient", "2026-01-01T09:00:00+00:00")
    body = client_for(engine).get(URL, params={"days": 7}).json()
    assert body["total_users"] == 5  # the deleted user is excluded everywhere
    assert body["new_users"] == 3 and body["previous_period_users"] == 1
    assert body["growth_percent"] == 200.0
    assert by_key(body["by_weekday"])["tue"] == 1  # 2026-11-10 is a Tuesday
    assert by_key(body["by_hour"])["9"] == 3


def test_demographics_only_with_consent_and_small_groups_merged(client_for):
    engine = make_engine(profile=True)
    for i in range(5):
        add_user(engine, f"m{i}", "2026-11-12T10:00:00+00:00", analytics_consent=1, birth_year=2000, city=" minsk ")
    add_user(engine, "g", "2026-11-12T10:00:00+00:00", analytics_consent=1, birth_year=1960, city="Grodno")
    add_user(engine, "x", "2026-11-12T10:00:00+00:00", analytics_consent=0, birth_year=1990, city="Brest")
    body = client_for(engine).get(URL, params={"days": 7, "min_group": 5}).json()
    assert body["consented_users"] == 6 and body["consent_rate_percent"] == 85.7
    assert by_key(body["top_cities"]) == {"Minsk": 5, "other": 1}  # Grodno (1 user) is not exposed, Brest not consented
    ages = by_key(body["by_age_group"])
    assert ages["25-34"] == 5  # born 2000
    assert ages["65+"] == 0 and ages["other"] == 1  # the single 66-year-old is hidden in "other"
    assert sum(ages.values()) == 6


def test_channels_devices_languages(client_for):
    engine = make_engine(profile=True)
    rows = [("tg", "telegram", "mobile", "ru")] * 3 + [("ig", "google.com", "desktop", "be")] * 2
    for i, (utm, ref, device, lang) in enumerate(rows):
        add_user(engine, f"u{i}", "2026-11-12T10:00:00+00:00", utm_source=utm, referrer_domain=ref,
                 device_type=device, preferred_language=lang, acquisition_source="friends" if i < 4 else "")
    body = client_for(engine).get(URL, params={"days": 7, "min_group": 2, "top": 1}).json()
    assert by_key(body["by_utm_source"]) == {"tg": 3, "other": 2}  # top=1 keeps the biggest, the rest is "other"
    assert by_key(body["by_device"]) == {"mobile": 3, "other": 2}
    assert by_key(body["by_source"]) == {"friends": 4, "other": 1}  # the empty answer is 'unknown', 1 < min_group


def test_activation_counts_first_donation_within_window(client_for):
    engine = make_engine(profile=True)
    add_user(engine, "fast", "2026-11-10T10:00:00+00:00")
    add_user(engine, "late", "2026-11-01T10:00:00+00:00")
    add_user(engine, "none", "2026-11-11T10:00:00+00:00")
    add_donation(engine, "d1", "fast", "2026-11-11T10:00:00+00:00")
    add_donation(engine, "d2", "fast", "2026-11-12T10:00:00+00:00")
    add_donation(engine, "d3", "late", "2026-11-12T10:00:00+00:00")  # 11 days after sign-up
    add_donation(engine, "d4", "none", "2026-11-12T10:00:00+00:00", status="failed")
    body = client_for(engine).get(URL, params={"days": 30, "activation_days": 7}).json()
    activation = body["activation"]
    assert activation["activated_users"] == 1 and activation["activation_rate_percent"] == 33.3
    assert activation["avg_days_to_first_donation"] == 1.0


def test_no_personal_data_in_response(client_for):
    engine = make_engine(profile=True)
    add_user(engine, "p", "2026-11-12T10:00:00+00:00")
    raw = client_for(engine).get(URL).text
    assert "secret.example" not in raw and "hash-must-not-leak" not in raw and '"p"' not in raw


def test_validation_and_unavailable_database(client_for):
    engine = make_engine(profile=True)
    client = client_for(engine)
    assert client.get(URL, params={"days": 0}).status_code == 422
    assert client.get(URL, params={"min_group": 51}).status_code == 422
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE users"))
    response = client.get(URL)
    assert response.status_code == 503
    assert "регистраций" in response.json()["detail"]
