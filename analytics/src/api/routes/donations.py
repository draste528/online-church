"""Donation statistics for the "Пожертвования" page, computed straight from the OLTP `donations` table."""
import logging
import time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError

from analytics.src.config import settings
from analytics.src.db import get_engine

router = APIRouter(prefix="/api/v1/analytics/donations", tags=["Analytics & Datamarts"])
log = logging.getLogger(__name__)

CURRENCY = "USD"  # amounts of different currencies must not be added up; the donation flow only produces USD

# Aggregation is done in pandas rather than in SQL so that the same code runs on PostgreSQL and on SQLite in tests.
COMPLETED_DONATIONS_SQL = text(
    "SELECT amount, target_fund, created_at FROM donations WHERE payment_status = 'completed' AND currency = :currency"
)


class FundTotal(BaseModel):
    fund: str
    total: float
    count: int
    share_percent: float


class HourBucket(BaseModel):
    hour: int
    count: int
    total: float


class DonationSummary(BaseModel):
    currency: str
    total_amount: float
    donations_count: int
    average_amount: float
    by_fund: list[FundTotal]
    by_hour: list[HourBucket]
    peak_hour: int | None
    timezone: str


def resolve_timezone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        log.warning("Unknown ANALYTICS_TIMEZONE %r, using UTC", name)
        return ZoneInfo("UTC")


def build_summary(df: pd.DataFrame, tz: ZoneInfo) -> DonationSummary:
    """Turn the completed donations (columns amount, target_fund, created_at) into the summary."""
    hours = [HourBucket(hour=h, count=0, total=0.0) for h in range(24)]
    if df.empty:
        return DonationSummary(
            currency=CURRENCY, total_amount=0.0, donations_count=0, average_amount=0.0,
            by_fund=[], by_hour=hours, peak_hour=None, timezone=str(tz),
        )

    amounts = pd.to_numeric(df["amount"])
    # PostgreSQL returns aware datetimes, SQLite returns text; both are treated as UTC and shown in `tz`.
    created = pd.to_datetime(df["created_at"], utc=True, format="ISO8601").dt.tz_convert(tz)
    frame = pd.DataFrame({"amount": amounts, "fund": df["target_fund"], "hour": created.dt.hour})

    total = float(frame["amount"].sum())
    count = int(len(frame))

    by_fund = frame.groupby("fund")["amount"].agg(["sum", "count"]).sort_values("sum", ascending=False)
    funds = [
        FundTotal(fund=str(fund), total=round(float(row["sum"]), 2), count=int(row["count"]),
                  share_percent=round(float(row["sum"]) / total * 100, 1))
        for fund, row in by_fund.iterrows()
    ]

    by_hour = frame.groupby("hour")["amount"].agg(["sum", "count"])
    for hour, row in by_hour.iterrows():
        hours[int(hour)] = HourBucket(hour=int(hour), count=int(row["count"]), total=round(float(row["sum"]), 2))
    peak = max(hours, key=lambda bucket: (bucket.count, -bucket.hour))

    return DonationSummary(
        currency=CURRENCY, total_amount=round(total, 2), donations_count=count,
        average_amount=round(total / count, 2), by_fund=funds, by_hour=hours,
        peak_hour=peak.hour, timezone=str(tz),
    )


@router.get("/summary", response_model=DonationSummary)
def get_donations_summary(engine: Engine = Depends(get_engine)):
    """Total, count, average, per-fund totals and the hour-of-day distribution of completed donations."""
    started = time.perf_counter()
    try:
        with engine.connect() as conn:
            df = pd.read_sql_query(COMPLETED_DONATIONS_SQL, conn, params={"currency": CURRENCY})
    except SQLAlchemyError as exc:
        log.error("Could not read donations: %s", type(exc).__name__)
        raise HTTPException(
            status_code=503, detail="Статистика временно недоступна: нет связи с базой данных."
        ) from exc
    summary = build_summary(df, resolve_timezone(settings.ANALYTICS_TIMEZONE))
    log.info(
        "Donation summary: %d donations, %.1f ms", summary.donations_count, (time.perf_counter() - started) * 1000
    )
    return summary
