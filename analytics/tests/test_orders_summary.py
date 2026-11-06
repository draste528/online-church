from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from analytics.src.api.main import app
from analytics.src.api.routes import orders as orders_route
from analytics.src.config import settings
from analytics.src.db import get_engine

URL = "/api/v1/analytics/orders/summary"
NOW = datetime(2026, 11, 6, 12, 0, tzinfo=UTC)

# Mirrors the columns the endpoint reads (see backend/app/models.py and docs/church_db_init.sql).
CREATE_ORDERS = """
CREATE TABLE shop_orders (order_id TEXT PRIMARY KEY, status TEXT NOT NULL, total NUMERIC NOT NULL,
                          created_at TEXT NOT NULL)
"""
CREATE_LINES = """
CREATE TABLE shop_order_lines (line_id INTEGER PRIMARY KEY, order_id TEXT NOT NULL, title TEXT NOT NULL,
                               quantity INTEGER NOT NULL, line_total NUMERIC NOT NULL)
"""
CREATE_EVENTS = """
CREATE TABLE shop_order_events (event_id INTEGER PRIMARY KEY, order_id TEXT NOT NULL, status TEXT NOT NULL,
                                note TEXT, created_at TEXT NOT NULL)
"""


@pytest.fixture()
def engine():
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    with eng.begin() as conn:
        conn.execute(text(CREATE_ORDERS))
        conn.execute(text(CREATE_LINES))
    yield eng
    eng.dispose()


@pytest.fixture()
def with_history(engine):
    with engine.begin() as conn:
        conn.execute(text(CREATE_EVENTS))
    return engine


@pytest.fixture()
def client(engine, monkeypatch):
    monkeypatch.setattr(settings, "ANALYTICS_TIMEZONE", "UTC")
    monkeypatch.setattr(orders_route, "now_utc", lambda: NOW)
    app.dependency_overrides[get_engine] = lambda: engine
    yield TestClient(app)
    app.dependency_overrides.pop(get_engine, None)


def add_order(engine, order_id, status, created_at, lines):
    """lines: list of (title, quantity, line_total); the order total is their sum."""
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO shop_orders VALUES (:id, :s, :t, :c)"),
            {"id": order_id, "s": status, "t": sum(line[2] for line in lines), "c": created_at},
        )
        for title, qty, line_total in lines:
            conn.execute(
                text("INSERT INTO shop_order_lines (order_id, title, quantity, line_total) VALUES (:id, :t, :q, :lt)"),
                {"id": order_id, "t": title, "q": qty, "lt": line_total},
            )


def add_event(engine, order_id, status, created_at):
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO shop_order_events (order_id, status, created_at) VALUES (:id, :s, :c)"),
            {"id": order_id, "s": status, "c": created_at},
        )


def seed(engine):
    add_order(engine, "o1", "completed", "2026-11-06 09:00:00", [("Свеча", 4, 12), ("Ладан", 1, 6.5)])
    add_order(engine, "o2", "assembling", "2026-11-05 10:00:00.123456", [("Свеча", 2, 6)])
    add_order(engine, "o3", "cancelled", "2026-11-05 11:00:00", [("Икона", 1, 40)])
    add_order(engine, "o4", "accepted", "2026-10-01 08:00:00", [("Ладан", 1, 6.5)])  # outside a 14-day window


def test_empty_tables_give_a_zero_summary(client):
    res = client.get(URL)

    assert res.status_code == 200
    body = res.json()
    assert body["orders_count"] == 0 and body["revenue"] == 0 and body["top_items"] == []
    assert [s["status"] for s in body["by_status"]] == ["accepted", "assembling", "ready", "completed", "cancelled"]
    assert len(body["by_day"]) == 14 and body["by_day"][-1]["date"] == "2026-11-06"
    assert body["fulfilment"] == {"tracking_available": False, "avg_hours_to_ready": None,
                                  "avg_hours_to_completed": None}


def test_counts_revenue_and_cancellation(client, engine):
    seed(engine)

    body = client.get(URL).json()

    assert body["orders_count"] == 4
    assert body["active_orders"] == 2 and body["completed_orders"] == 1 and body["cancelled_orders"] == 1
    assert body["cancellation_rate_percent"] == 25.0
    assert body["revenue"] == 31.0  # 18.5 + 6 + 6.5, the cancelled 40 is excluded
    assert body["average_order_value"] == pytest.approx(10.33)
    assert body["items_sold"] == 8
    by_status = {s["status"]: s["count"] for s in body["by_status"]}
    assert by_status == {"accepted": 1, "assembling": 1, "ready": 0, "completed": 1, "cancelled": 1}


def test_top_items_exclude_cancelled_orders_and_respect_the_limit(client, engine):
    seed(engine)

    body = client.get(URL, params={"top": 2}).json()

    assert [(i["title"], i["quantity"], i["revenue"]) for i in body["top_items"]] == [
        ("Свеча", 6, 18.0), ("Ладан", 2, 13.0)
    ]


def test_by_day_uses_the_window_and_skips_cancelled_revenue(client, engine):
    seed(engine)

    body = client.get(URL, params={"days": 3}).json()

    assert body["days"] == 3
    assert body["by_day"] == [
        {"date": "2026-11-04", "orders": 0, "revenue": 0.0},
        {"date": "2026-11-05", "orders": 2, "revenue": 6.0},
        {"date": "2026-11-06", "orders": 1, "revenue": 18.5},
    ]


def test_funnel_without_history_uses_the_current_status(client, engine):
    seed(engine)

    funnel = {s["status"]: s["reached"] for s in client.get(URL).json()["funnel"]}

    assert funnel == {"accepted": 4, "assembling": 2, "ready": 1, "completed": 1}


def test_history_enables_funnel_and_fulfilment_times(client, with_history):
    engine = with_history
    seed(engine)
    for status, at in [("accepted", "09:00"), ("assembling", "10:00"), ("ready", "12:00"), ("completed", "15:00")]:
        add_event(engine, "o1", status, f"2026-11-06 {at}:00")
    add_event(engine, "o2", "accepted", "2026-11-05 10:00:00")
    add_event(engine, "o2", "assembling", "2026-11-05 11:00:00")
    for status, at in [("accepted", "11:00"), ("assembling", "11:30"), ("cancelled", "12:00")]:
        add_event(engine, "o3", status, f"2026-11-05 {at}:00")

    body = client.get(URL).json()

    funnel = {s["status"]: s["reached"] for s in body["funnel"]}
    assert funnel == {"accepted": 4, "assembling": 3, "ready": 1, "completed": 1}  # o3 got to assembling first
    assert body["fulfilment"] == {"tracking_available": True, "avg_hours_to_ready": 3.0,
                                  "avg_hours_to_completed": 6.0}


def test_hours_follow_the_configured_timezone(client, engine, monkeypatch):
    add_order(engine, "o1", "accepted", "2026-11-05 22:30:00", [("Свеча", 1, 3)])  # 01:30 on Nov 6 in Moscow
    monkeypatch.setattr(settings, "ANALYTICS_TIMEZONE", "Europe/Moscow")

    body = client.get(URL, params={"days": 2}).json()

    assert body["timezone"] == "Europe/Moscow"
    assert [d["orders"] for d in body["by_day"]] == [0, 1]


@pytest.mark.parametrize("params", [{"days": 0}, {"days": 91}, {"top": 0}, {"top": 21}, {"days": "week"}])
def test_query_parameters_out_of_range_are_422(client, params):
    assert client.get(URL, params=params).status_code == 422


def test_database_failure_answers_503():
    broken = create_engine("sqlite://")  # no tables at all
    app.dependency_overrides[get_engine] = lambda: broken
    try:
        res = TestClient(app).get(URL)
    finally:
        app.dependency_overrides.pop(get_engine, None)

    assert res.status_code == 503
    assert "недоступна" in res.json()["detail"]
