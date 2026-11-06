"""Shop order statistics for the order tracking feature, computed straight from the OLTP shop tables.

Reads `shop_orders` and `shop_order_lines`. The status history table `shop_order_events` (SCRUM-27) is optional:
while it does not exist the funnel is built from the current status and fulfilment times are reported as null.
"""
import logging
import time
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import Engine, inspect, text
from sqlalchemy.exc import SQLAlchemyError

from analytics.src.api.routes.donations import resolve_timezone
from analytics.src.config import settings
from analytics.src.db import get_engine

router = APIRouter(prefix="/api/v1/analytics/orders", tags=["Analytics & Datamarts"])
log = logging.getLogger(__name__)

CURRENCY = "USD"
FLOW = ["accepted", "assembling", "ready", "completed"]  # the normal path of an order
STATUSES = [*FLOW, "cancelled"]
ACTIVE = {"accepted", "assembling", "ready"}

DEFAULT_DAYS, MAX_DAYS = 14, 90
DEFAULT_TOP, MAX_TOP = 5, 20

ORDERS_SQL = text("SELECT order_id, status, total, created_at FROM shop_orders")
LINES_SQL = text("SELECT order_id, title, quantity, line_total FROM shop_order_lines")
EVENTS_TABLE = "shop_order_events"
EVENTS_SQL = text(f"SELECT order_id, status, created_at FROM {EVENTS_TABLE}")


class StatusCount(BaseModel):
    status: str
    count: int
    share_percent: float


class FunnelStep(BaseModel):
    status: str
    reached: int
    reached_percent: float


class TopItem(BaseModel):
    title: str
    quantity: int
    revenue: float


class DayBucket(BaseModel):
    date: str  # YYYY-MM-DD in the analytics time zone
    orders: int
    revenue: float


class Fulfilment(BaseModel):
    tracking_available: bool  # False until the status history table exists
    avg_hours_to_ready: float | None
    avg_hours_to_completed: float | None


class OrderSummary(BaseModel):
    currency: str
    orders_count: int
    active_orders: int
    completed_orders: int
    cancelled_orders: int
    cancellation_rate_percent: float
    revenue: float  # cancelled orders are excluded
    average_order_value: float
    items_sold: int
    by_status: list[StatusCount]
    funnel: list[FunnelStep]
    top_items: list[TopItem]
    by_day: list[DayBucket]
    fulfilment: Fulfilment
    timezone: str
    days: int


def now_utc() -> datetime:
    """Separate function so that tests can pin the clock."""
    return datetime.now(UTC)


def _percent(part: int, whole: int) -> float:
    return round(part / whole * 100, 1) if whole else 0.0


def _to_time(values: pd.Series, tz: ZoneInfo) -> pd.Series:
    # PostgreSQL returns aware datetimes, SQLite returns text; both are treated as UTC.
    return pd.to_datetime(values, utc=True, format="ISO8601").dt.tz_convert(tz)


def _reached_steps(orders: pd.DataFrame, events: pd.DataFrame | None) -> dict[str, int]:
    """How many orders reached each step of FLOW (reaching a later step implies the earlier ones)."""
    rank = {status: i for i, status in enumerate(FLOW)}
    if events is not None and not events.empty:
        best = events["status"].map(rank).groupby(events["order_id"].astype(str)).max()
        best = best.reindex(orders["order_id"].astype(str)).fillna(0)  # an order without events is at least accepted
    else:
        best = orders["status"].map(rank).fillna(0)  # cancelled without history: only "accepted" is known
    return {status: int((best >= i).sum()) for i, status in enumerate(FLOW)}


def _avg_hours(events: pd.DataFrame, target: str, tz: ZoneInfo) -> float | None:
    """Average time from the "accepted" event to the first `target` event, over orders that reached it."""
    times = events.assign(at=_to_time(events["created_at"], tz), order_id=events["order_id"].astype(str))
    start = times[times["status"] == "accepted"].groupby("order_id")["at"].min()
    end = times[times["status"] == target].groupby("order_id")["at"].min()
    spans = (end - start).dropna()
    if spans.empty:
        return None
    return round(spans.dt.total_seconds().mean() / 3600, 2)


def build_summary(
    orders: pd.DataFrame,
    lines: pd.DataFrame,
    events: pd.DataFrame | None,
    tz: ZoneInfo,
    days: int = DEFAULT_DAYS,
    top: int = DEFAULT_TOP,
    now: datetime | None = None,
) -> OrderSummary:
    """Turn raw order rows into the summary. `events` is None when the status history table does not exist."""
    now = (now or now_utc()).astimezone(tz)
    day_keys = [(now.date() - timedelta(days=offset)).isoformat() for offset in range(days - 1, -1, -1)]
    fulfilment = Fulfilment(tracking_available=events is not None, avg_hours_to_ready=None,
                            avg_hours_to_completed=None)

    if orders.empty:
        return OrderSummary(
            currency=CURRENCY, orders_count=0, active_orders=0, completed_orders=0, cancelled_orders=0,
            cancellation_rate_percent=0.0, revenue=0.0, average_order_value=0.0, items_sold=0,
            by_status=[StatusCount(status=s, count=0, share_percent=0.0) for s in STATUSES],
            funnel=[FunnelStep(status=s, reached=0, reached_percent=0.0) for s in FLOW],
            top_items=[], by_day=[DayBucket(date=d, orders=0, revenue=0.0) for d in day_keys],
            fulfilment=fulfilment, timezone=str(tz), days=days,
        )

    orders = orders.assign(total=pd.to_numeric(orders["total"]), order_id=orders["order_id"].astype(str))
    count = len(orders)
    status_counts = orders["status"].value_counts()
    paid = orders[orders["status"] != "cancelled"]
    revenue = float(paid["total"].sum())
    cancelled = int(status_counts.get("cancelled", 0))

    paid_lines = lines.assign(order_id=lines["order_id"].astype(str))
    paid_lines = paid_lines[paid_lines["order_id"].isin(paid["order_id"])]
    items = (
        paid_lines.assign(quantity=pd.to_numeric(paid_lines["quantity"]),
                          line_total=pd.to_numeric(paid_lines["line_total"]))
        .groupby("title")[["quantity", "line_total"]].sum()
        .sort_values(["quantity", "line_total"], ascending=False)
    )

    created_day = _to_time(orders["created_at"], tz).dt.strftime("%Y-%m-%d")
    per_day = orders.assign(day=created_day, paid_total=orders["total"].where(orders["status"] != "cancelled", 0))
    per_day = per_day.groupby("day").agg(orders=("order_id", "count"), revenue=("paid_total", "sum"))

    reached = _reached_steps(orders, events)
    if events is not None and not events.empty:
        fulfilment.avg_hours_to_ready = _avg_hours(events, "ready", tz)
        fulfilment.avg_hours_to_completed = _avg_hours(events, "completed", tz)

    return OrderSummary(
        currency=CURRENCY,
        orders_count=count,
        active_orders=int(orders["status"].isin(ACTIVE).sum()),
        completed_orders=int(status_counts.get("completed", 0)),
        cancelled_orders=cancelled,
        cancellation_rate_percent=_percent(cancelled, count),
        revenue=round(revenue, 2),
        average_order_value=round(revenue / len(paid), 2) if len(paid) else 0.0,
        items_sold=int(items["quantity"].sum()) if not items.empty else 0,
        by_status=[StatusCount(status=s, count=int(status_counts.get(s, 0)),
                               share_percent=_percent(int(status_counts.get(s, 0)), count)) for s in STATUSES],
        funnel=[FunnelStep(status=s, reached=reached[s], reached_percent=_percent(reached[s], count)) for s in FLOW],
        top_items=[TopItem(title=str(title), quantity=int(row["quantity"]), revenue=round(float(row["line_total"]), 2))
                   for title, row in items.head(top).iterrows()],
        by_day=[DayBucket(date=d, orders=int(per_day["orders"].get(d, 0)),
                          revenue=round(float(per_day["revenue"].get(d, 0.0)), 2)) for d in day_keys],
        fulfilment=fulfilment,
        timezone=str(tz),
        days=days,
    )


@router.get("/summary", response_model=OrderSummary)
def get_orders_summary(
    days: int = Query(DEFAULT_DAYS, ge=1, le=MAX_DAYS, description="Length of the by_day series"),
    top: int = Query(DEFAULT_TOP, ge=1, le=MAX_TOP, description="How many best-selling items to return"),
    engine: Engine = Depends(get_engine),
):
    """Order counts by status, funnel, revenue, best-selling items, daily dynamics and fulfilment times."""
    started = time.perf_counter()
    try:
        with engine.connect() as conn:
            orders = pd.read_sql_query(ORDERS_SQL, conn)
            lines = pd.read_sql_query(LINES_SQL, conn)
            has_events = inspect(conn).has_table(EVENTS_TABLE)
            events = pd.read_sql_query(EVENTS_SQL, conn) if has_events else None
    except (SQLAlchemyError, pd.errors.DatabaseError) as exc:  # pandas wraps errors such as a missing table
        log.error("Could not read shop orders: %s", type(exc).__name__)
        raise HTTPException(
            status_code=503, detail="Статистика заказов временно недоступна: нет связи с базой данных или таблиц лавки."
        ) from exc
    summary = build_summary(orders, lines, events, resolve_timezone(settings.ANALYTICS_TIMEZONE), days, top)
    log.info(
        "Order summary: %d orders, history %s, %.1f ms", summary.orders_count,
        "on" if has_events else "off", (time.perf_counter() - started) * 1000,
    )
    return summary
