"""Registration analytics: who signs up, where they come from and whether they come back.

Reads the OLTP `users` table and completed `donations`. Only `user_id`, `role` and `created_at` are required;
every other profile column (see OPTIONAL_COLUMNS and analytics/sql/05_users_registration_profile.sql) is detected
at runtime, so the endpoint works before and after the backend adds them.

Privacy rules:
- demographics (age, city) are counted only for users with `analytics_consent = true`;
- any category with fewer than `min_group` users is merged into "other" so a single person cannot be singled out;
- no personal data (names, emails, ids) ever leaves this endpoint, only counts.
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

router = APIRouter(prefix="/api/v1/analytics/registrations", tags=["Analytics & Datamarts"])
log = logging.getLogger(__name__)

USERS_TABLE = "users"
DONATIONS_TABLE = "donations"
REQUIRED_COLUMNS = ("user_id", "role", "created_at")
# Profile columns the summary uses when they exist (whitelist: only these names are ever put into SQL).
OPTIONAL_COLUMNS = (
    "is_deleted",
    "last_seen",
    "analytics_consent",
    "birth_year",
    "city",
    "acquisition_source",
    "preferred_language",
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "referrer_domain",
    "device_type",
)
ROLES = ("parishioner", "priest", "admin")
OTHER = "other"
UNKNOWN = "unknown"

# Age buckets: (label, min age inclusive, max age inclusive or None). Users under the first bucket are not counted.
AGE_BUCKETS = (
    ("14-17", 14, 17),
    ("18-24", 18, 24),
    ("25-34", 25, 34),
    ("35-44", 35, 44),
    ("45-54", 45, 54),
    ("55-64", 55, 64),
    ("65+", 65, None),
)

DEFAULT_DAYS, MAX_DAYS = 30, 365
DEFAULT_MIN_GROUP, MAX_MIN_GROUP = 5, 50
DEFAULT_TOP, MAX_TOP = 10, 50
DEFAULT_RETURN_HOURS = 24  # a user "came back" when last_seen is at least this long after registration
DEFAULT_ACTIVATION_DAYS = 7  # a donation within this many days after registration counts as activation


class Bucket(BaseModel):
    key: str
    count: int
    share_percent: float


class DayBucket(BaseModel):
    date: str  # YYYY-MM-DD in the analytics time zone
    registrations: int


class Activation(BaseModel):
    window_days: int
    activated_users: int  # new users who made a completed donation within window_days
    activation_rate_percent: float
    avg_days_to_first_donation: float | None
    return_window_hours: int
    returned_users: int | None  # null while users.last_seen is not available
    return_rate_percent: float | None


class RegistrationSummary(BaseModel):
    total_users: int
    new_users: int  # registered in the last `days` days
    previous_period_users: int  # registered in the `days` days before that
    growth_percent: float | None  # null when the previous period had no registrations
    by_day: list[DayBucket]
    by_weekday: list[Bucket]  # Monday first
    by_hour: list[Bucket]  # 0..23
    by_role: list[Bucket]
    consent_available: bool
    consented_users: int
    consent_rate_percent: float
    by_source: list[Bucket]  # self-reported acquisition_source
    by_utm_source: list[Bucket]
    by_utm_campaign: list[Bucket]
    by_referrer: list[Bucket]
    by_device: list[Bucket]
    by_language: list[Bucket]
    by_age_group: list[Bucket]  # consenting users only
    top_cities: list[Bucket]  # consenting users only
    activation: Activation
    available_fields: list[str]  # optional profile columns present in the database
    min_group: int
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


def _as_bool(values: pd.Series) -> pd.Series:
    """SQLite stores booleans as 0/1 (or text), PostgreSQL as bool; NULL counts as False."""
    flags = values.map(lambda v: str(v).strip().lower() in {"1", "true", "t", "yes"} if pd.notna(v) else False)
    return flags.astype(bool)


def _clean(values: pd.Series) -> pd.Series:
    """Trim and lower-case a free-text category; empty values become 'unknown'."""
    text_values = values.astype("string").str.strip().str.lower()
    return text_values.mask(text_values.isna() | (text_values == ""), UNKNOWN).astype(str)


def _buckets(values: pd.Series, min_group: int, top: int | None = None, order: list[str] | None = None,
             suppress: bool = False) -> list[Bucket]:
    """Count categories; groups smaller than min_group (and those past `top`) are merged into 'other'.

    With `order`, every listed key is returned in that order (zeros included). Non-sensitive orderings
    (weekday, hour, role) are reported as is; with `suppress=True` a non-empty key below min_group is
    reported as 0 and its users are added to a trailing 'other' bucket.
    """
    total = len(values)
    counts = values.value_counts()
    if order is not None:
        result, hidden = [], 0
        for key in order:
            count = int(counts.get(key, 0))
            if suppress and 0 < count < min_group:
                hidden, count = hidden + count, 0
            result.append(Bucket(key=key, count=count, share_percent=_percent(count, total)))
        if hidden:
            result.append(Bucket(key=OTHER, count=hidden, share_percent=_percent(hidden, total)))
        return result
    counts = counts.sort_values(ascending=False, kind="stable")
    kept: list[tuple[str, int]] = []
    other = 0
    for key, count in counts.items():
        if key == OTHER or count < min_group or (top is not None and len(kept) >= top):
            other += int(count)
        else:
            kept.append((str(key), int(count)))
    if other:
        kept.append((OTHER, other))
    return [Bucket(key=k, count=c, share_percent=_percent(c, total)) for k, c in kept]


def _age_group(age: float) -> str | None:
    for label, low, high in AGE_BUCKETS:
        if age >= low and (high is None or age <= high):
            return label
    return None


def _activation(new: pd.DataFrame, donations: pd.DataFrame, tz: ZoneInfo, window_days: int,
                return_hours: int, has_last_seen: bool) -> Activation:
    activated, avg_days = 0, None
    if not new.empty and not donations.empty:
        first = (donations.assign(user_id=donations["user_id"].astype(str), at=_to_time(donations["created_at"], tz))
                 .groupby("user_id")["at"].min())
        joined = new.set_index("user_id")["registered_at"].to_frame().join(first.rename("first_donation"), how="inner")
        delay = joined["first_donation"] - joined["registered_at"]
        delay = delay[(delay >= timedelta(0)) & (delay <= timedelta(days=window_days))]
        activated = len(delay)
        if activated:
            avg_days = round(delay.dt.total_seconds().mean() / 86400, 2)

    returned, return_rate = None, None
    if has_last_seen:
        seen = pd.to_datetime(new["last_seen"], utc=True, format="ISO8601", errors="coerce").dt.tz_convert(tz)
        returned = int(((seen - new["registered_at"]) >= timedelta(hours=return_hours)).sum())
        return_rate = _percent(returned, len(new))

    return Activation(
        window_days=window_days, activated_users=activated, activation_rate_percent=_percent(activated, len(new)),
        avg_days_to_first_donation=avg_days, return_window_hours=return_hours,
        returned_users=returned, return_rate_percent=return_rate,
    )


def build_summary(
    users: pd.DataFrame,
    donations: pd.DataFrame,
    tz: ZoneInfo,
    days: int = DEFAULT_DAYS,
    min_group: int = DEFAULT_MIN_GROUP,
    top: int = DEFAULT_TOP,
    activation_days: int = DEFAULT_ACTIVATION_DAYS,
    return_hours: int = DEFAULT_RETURN_HOURS,
    now: datetime | None = None,
) -> RegistrationSummary:
    """Turn raw `users` rows (any subset of OPTIONAL_COLUMNS) and completed donations into the summary.

    Breakdowns describe the users registered in the last `days` days; `total_users` counts everyone.
    """
    now = (now or now_utc()).astimezone(tz)
    available = [c for c in OPTIONAL_COLUMNS if c in users.columns]
    day_keys = [(now.date() - timedelta(days=offset)).isoformat() for offset in range(days - 1, -1, -1)]
    period_start = datetime.fromisoformat(day_keys[0]).replace(tzinfo=tz)
    previous_start = period_start - timedelta(days=days)

    if "is_deleted" in users.columns:
        users = users.loc[~_as_bool(users["is_deleted"])]
    users = users.assign(user_id=users["user_id"].astype(str), registered_at=_to_time(users["created_at"], tz))
    users = users[users["registered_at"] <= now]

    new = users[users["registered_at"] >= period_start]
    previous = users[(users["registered_at"] >= previous_start) & (users["registered_at"] < period_start)]
    count = len(new)

    per_day = new["registered_at"].dt.strftime("%Y-%m-%d").value_counts()
    weekday = new["registered_at"].dt.dayofweek.map(lambda d: ["mon", "tue", "wed", "thu", "fri", "sat", "sun"][d])
    hour = new["registered_at"].dt.hour.astype(str)

    def column(name: str) -> pd.Series:
        return _clean(new[name]) if name in new.columns else pd.Series([], dtype=str)

    consent_available = "analytics_consent" in new.columns
    consenting = new.loc[_as_bool(new["analytics_consent"])] if consent_available else new.iloc[0:0]

    ages = pd.Series([], dtype=str)
    if "birth_year" in consenting.columns and not consenting.empty:
        years = pd.to_numeric(consenting["birth_year"], errors="coerce").dropna()
        ages = (now.year - years).map(_age_group).dropna()
    cities = pd.Series([], dtype=str)
    if "city" in consenting.columns:
        cities = _clean(consenting["city"]).str.title()
        cities = cities[cities != UNKNOWN.title()]

    growth = round((count - len(previous)) / len(previous) * 100, 1) if len(previous) else None
    return RegistrationSummary(
        total_users=len(users),
        new_users=count,
        previous_period_users=len(previous),
        growth_percent=growth,
        by_day=[DayBucket(date=d, registrations=int(per_day.get(d, 0))) for d in day_keys],
        by_weekday=_buckets(weekday, min_group, order=["mon", "tue", "wed", "thu", "fri", "sat", "sun"]),
        by_hour=_buckets(hour, min_group, order=[str(h) for h in range(24)]),
        by_role=_buckets(column("role"), min_group, order=list(ROLES)),
        consent_available=consent_available,
        consented_users=len(consenting),
        consent_rate_percent=_percent(len(consenting), count),
        by_source=_buckets(column("acquisition_source"), min_group, top),
        by_utm_source=_buckets(column("utm_source"), min_group, top),
        by_utm_campaign=_buckets(column("utm_campaign"), min_group, top),
        by_referrer=_buckets(column("referrer_domain"), min_group, top),
        by_device=_buckets(column("device_type"), min_group, top),
        by_language=_buckets(column("preferred_language"), min_group, top),
        by_age_group=(_buckets(ages, min_group, order=[label for label, _, _ in AGE_BUCKETS], suppress=True)
                      if len(ages) else []),
        top_cities=_buckets(cities, min_group, top),
        activation=_activation(new, donations, tz, activation_days, return_hours, "last_seen" in new.columns),
        available_fields=available,
        min_group=min_group,
        timezone=str(tz),
        days=days,
    )


def read_tables(engine: Engine) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Read only the user columns that exist (no names, emails or password hashes) and completed donations."""
    with engine.connect() as conn:
        inspector = inspect(conn)
        present = {c["name"] for c in inspector.get_columns(USERS_TABLE)}
        missing = [c for c in REQUIRED_COLUMNS if c not in present]
        if missing:
            raise SQLAlchemyError(f"users table lacks columns: {missing}")
        columns = [*REQUIRED_COLUMNS, *(c for c in OPTIONAL_COLUMNS if c in present)]
        users = pd.read_sql_query(text(f"SELECT {', '.join(columns)} FROM {USERS_TABLE}"), conn)
        if inspector.has_table(DONATIONS_TABLE):
            donations = pd.read_sql_query(
                text(f"SELECT user_id, created_at FROM {DONATIONS_TABLE} "
                     "WHERE payment_status = 'completed' AND user_id IS NOT NULL"),
                conn,
            )
        else:
            donations = pd.DataFrame(columns=["user_id", "created_at"])
    return users, donations


@router.get("/summary", response_model=RegistrationSummary)
def get_registrations_summary(
    days: int = Query(DEFAULT_DAYS, ge=1, le=MAX_DAYS, description="Analysed period in days (and length of by_day)"),
    min_group: int = Query(DEFAULT_MIN_GROUP, ge=1, le=MAX_MIN_GROUP,
                           description="Smaller categories are merged into 'other' (anonymity threshold)"),
    top: int = Query(DEFAULT_TOP, ge=1, le=MAX_TOP, description="Max categories per breakdown before 'other'"),
    activation_days: int = Query(DEFAULT_ACTIVATION_DAYS, ge=1, le=90,
                                 description="A donation within this many days after sign-up counts as activation"),
    return_hours: int = Query(DEFAULT_RETURN_HOURS, ge=1, le=24 * 30,
                              description="last_seen this long after sign-up counts as a return visit"),
    engine: Engine = Depends(get_engine),
):
    """Who registers: dynamics, roles, acquisition channels, devices, languages, age and city (with consent),
    and how many new users donate or come back."""
    started = time.perf_counter()
    try:
        users, donations = read_tables(engine)
    except (SQLAlchemyError, pd.errors.DatabaseError) as exc:
        log.error("Could not read users: %s", type(exc).__name__)
        raise HTTPException(
            status_code=503, detail="Статистика регистраций временно недоступна: нет связи с базой данных."
        ) from exc
    summary = build_summary(users, donations, resolve_timezone(settings.ANALYTICS_TIMEZONE), days, min_group, top,
                            activation_days, return_hours)
    log.info("Registration summary: %d new of %d users, fields %s, %.1f ms", summary.new_users, summary.total_users,
             ",".join(summary.available_fields) or "-", (time.perf_counter() - started) * 1000)
    return summary
