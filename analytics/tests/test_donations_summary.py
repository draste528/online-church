import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from analytics.src.api.main import app
from analytics.src.config import settings
from analytics.src.db import get_engine

# Mirrors the columns of the `donations` table that the endpoint reads (see docs/church_db_init.sql).
CREATE_TABLE = """
CREATE TABLE donations (
    donation_id INTEGER PRIMARY KEY,
    amount NUMERIC NOT NULL,
    currency TEXT NOT NULL DEFAULT 'RUB',
    target_fund TEXT NOT NULL,
    payment_status TEXT NOT NULL,
    created_at TEXT NOT NULL
)
"""


@pytest.fixture()
def engine():
    """A throw-away in-memory database: the tests never need PostgreSQL."""
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    with eng.begin() as conn:
        conn.execute(text(CREATE_TABLE))
    yield eng
    eng.dispose()


@pytest.fixture()
def client(engine, monkeypatch):
    monkeypatch.setattr(settings, "ANALYTICS_TIMEZONE", "UTC")
    app.dependency_overrides[get_engine] = lambda: engine
    yield TestClient(app)
    app.dependency_overrides.pop(get_engine, None)


def add(engine, amount, fund, created_at, status="completed", currency="RUB"):
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO donations (amount, currency, target_fund, payment_status, created_at) "
                "VALUES (:a, :c, :f, :s, :t)"
            ),
            {"a": amount, "c": currency, "f": fund, "s": status, "t": created_at},
        )


def test_empty_table_gives_a_zero_summary(client):
    res = client.get("/api/v1/analytics/donations/summary")

    assert res.status_code == 200
    body = res.json()
    assert body["donations_count"] == 0 and body["total_amount"] == 0
    assert body["by_fund"] == [] and body["peak_hour"] is None
    assert [bucket["hour"] for bucket in body["by_hour"]] == list(range(24))


def test_summary_aggregates_completed_donations_only(client, engine):
    add(engine, 100, "general", "2026-10-01 09:10:00.000000")
    add(engine, 300, "general", "2026-10-02 09:50:00")  # no microseconds: both forms must parse
    add(engine, 200, "charity", "2026-10-02 18:00:00.123456")
    add(engine, 999, "choir", "2026-10-02 12:00:00", status="pending")
    add(engine, 999, "choir", "2026-10-02 12:00:00", status="failed")
    add(engine, 999, "choir", "2026-10-02 12:00:00", currency="USD")

    body = client.get("/api/v1/analytics/donations/summary").json()

    assert body["total_amount"] == 600
    assert body["donations_count"] == 3
    assert body["average_amount"] == 200
    assert [(f["fund"], f["total"], f["count"]) for f in body["by_fund"]] == [("general", 400, 2), ("charity", 200, 1)]
    assert body["by_fund"][0]["share_percent"] == pytest.approx(66.7)
    assert body["peak_hour"] == 9
    assert body["by_hour"][9]["count"] == 2 and body["by_hour"][18]["count"] == 1


def test_hours_follow_the_configured_timezone(client, engine, monkeypatch):
    add(engine, 100, "general", "2026-10-01 06:30:00")  # 09:30 in Moscow
    monkeypatch.setattr(settings, "ANALYTICS_TIMEZONE", "Europe/Moscow")

    body = client.get("/api/v1/analytics/donations/summary").json()

    assert body["peak_hour"] == 9 and body["timezone"] == "Europe/Moscow"


# TODO(Anton): the tests below are yours. Remove the skip marker and fill in the body one by one.
@pytest.mark.skip(reason="TODO(Anton): peak hour on a tie (two hours with the same count) picks the earlier hour")
def test_peak_hour_tie():
    ...


@pytest.mark.skip(reason="TODO(Anton): an unknown ANALYTICS_TIMEZONE falls back to UTC instead of failing")
def test_unknown_timezone_falls_back_to_utc():
    ...


@pytest.mark.skip(reason="TODO(Anton): database failure answers 503 with a readable message")
def test_database_failure_answers_503():
    # Idea: override get_engine with an engine pointing at a missing database file or a closed port.
    ...


@pytest.mark.skip(reason="TODO(Anton): share_percent values add up to ~100 and a single fund gets 100")
def test_fund_shares_add_up():
    ...
