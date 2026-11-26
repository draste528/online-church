import os
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import date, datetime, time, timedelta
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from analytics.src.api.main import app as analytics_app
from analytics.src.loaders.appointment_metrics import run
from backend.app.db import get_db, make_engine
from backend.app.main import app
from backend.app.models import User
from backend.app.security import create_access_token

URL = "/api/v1/analytics/appointments/summary"
MOSCOW = ZoneInfo("Europe/Moscow")
MIGRATION = Path(__file__).resolve().parents[2] / "analytics/sql/06_appointment_metrics.sql"
SUMMARY = text("SELECT * FROM appointment_metrics.summary() ORDER BY week_start")


@pytest.fixture(scope="module")
def postgres():
    url = os.environ.get("APPOINTMENTS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("requires APPOINTMENTS_TEST_DATABASE_URL pointing to a PostgreSQL test server")
    database = f"appointment_test_{uuid4().hex}"
    admin = create_engine(url, isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            conn.exec_driver_sql(f"CREATE DATABASE {database}")
        engine = make_engine(make_url(url).set(database=database).render_as_string(hide_password=False))
        try:
            yield engine
        finally:
            engine.dispose()
            with admin.connect() as conn:
                conn.exec_driver_sql(f"DROP DATABASE {database}")
    finally:
        admin.dispose()


@pytest.fixture
def database(postgres):
    with postgres.connect() as conn, conn.connection.cursor() as cursor:
        cursor.execute(MIGRATION.read_text())
    with postgres.begin() as conn:
        conn.exec_driver_sql(
            "TRUNCATE appointment_events.events, appointment_metrics.coverage, appointment_metrics.weekly"
        )
        User.__table__.create(conn, checkfirst=True)
        conn.exec_driver_sql("TRUNCATE public.users")
    return postgres


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "test-only-appointment-analytics-secret-0123456789")
    previous = app.dependency_overrides.copy()

    # TestClient without a lifespan context keeps startup seeding out of the test database.
    def http_for(engine):
        def session():
            with Session(engine, expire_on_commit=False) as db:
                yield db

        app.dependency_overrides[get_db] = session
        return TestClient(app)

    yield http_for
    app.dependency_overrides.clear()
    app.dependency_overrides.update(previous)


def auth(engine, role):
    with Session(engine, expire_on_commit=False) as db:
        name = uuid4().hex
        user = User(username=name, email=f"{name}@example.test", password_hash="unused", role=role)
        db.add(user)
        db.commit()
    token, _ = create_access_token(user.user_id)
    return {"Authorization": f"Bearer {token}"}, user.user_id


def simulate_coverage(conn, started_at):
    conn.execute(text("INSERT INTO appointment_metrics.coverage (started_at) VALUES (:at)"), {"at": started_at})


def insert_events(conn, event_type, occurred_at, count=1):
    conn.execute(
        text("INSERT INTO appointment_events.events VALUES (:id, :event, :at)"),
        [{"id": uuid4(), "event": event_type, "at": occurred_at} for _ in range(count)],
    )


def test_main_api_requires_admin_and_rejects_parameters(client):
    engine = make_engine("sqlite://")
    User.__table__.create(engine)
    try:
        with closing(client(engine)) as http:
            # The protection and parameter validation run before accessing the mart.
            for role in ("parishioner", "priest"):
                headers, _ = auth(engine, role)
                assert http.get(URL, headers=headers).status_code == 403
            anonymous = http.get(URL)
            assert anonymous.status_code == 401
            assert anonymous.headers["WWW-Authenticate"] == "Bearer"
            headers, user_id = auth(engine, "admin")
            response = http.get(URL, headers=headers, params={"filter": "private"})
            assert response.status_code == 422
            assert "private" not in response.text
            with Session(engine) as db:
                user = db.get(User, user_id)
                user.role = "parishioner"
                db.commit()
            assert http.get(URL, headers=headers).status_code == 403
        assert URL not in analytics_app.openapi()["paths"]
        assert URL in app.openapi()["paths"]
    finally:
        engine.dispose()


def test_report_weeks_respects_moscow_coverage_and_publication_deadline(database):
    query = text("SELECT week_start, starts_at, ends_at FROM appointment_metrics.report_weeks(:at) ORDER BY week_start")
    with database.begin() as conn:
        conn.exec_driver_sql("SET LOCAL TIME ZONE 'UTC'")
        # Activation on Monday at 00:01 leaves that first week partially covered.
        simulate_coverage(conn, datetime(2026, 11, 2, 0, 1, tzinfo=MOSCOW))
        before = conn.execute(query, {"at": datetime(2026, 11, 16, 0, 59, 59, tzinfo=MOSCOW)}).all()
        after = conn.execute(query, {"at": datetime(2026, 11, 16, 1, tzinfo=MOSCOW)}).one()
        assert before == []
        assert tuple(after) == (
            date(2026, 11, 9),
            datetime(2026, 11, 9, tzinfo=MOSCOW),
            datetime(2026, 11, 16, tzinfo=MOSCOW),
        )
        later = conn.execute(query, {"at": datetime(2027, 2, 1, 1, tzinfo=MOSCOW)}).all()
        assert len(later) == 8
        assert later[0].week_start == date(2026, 12, 7)
        assert later[-1].week_start == date(2027, 1, 25)


def test_event_record_is_atomic_and_idempotent(database, monkeypatch):
    monkeypatch.setenv("APPOINTMENTS_ETL_DATABASE_URL", database.url.render_as_string(hide_password=False))
    assert run("enable") == run("enable")
    record = text("SELECT appointment_events.record(:id, :event)")
    params = {"id": uuid4(), "event": "requested"}
    with database.connect() as conn:
        conn.execute(record, params)
        conn.rollback()
    with database.begin() as conn:
        assert conn.scalar(text("SELECT count(*) FROM appointment_events.events")) == 0
        conn.execute(record, params)
        conn.execute(record, params)
        conn.execute(record, {**params, "event": "approved"})
        assert conn.scalar(text("SELECT count(*) FROM appointment_events.events")) == 2
    assert run("refresh") == 0


def test_refresh_and_main_api_match_mart_on_synthetic_data(database, client):
    headers, _ = auth(database, "admin")
    with closing(client(database)) as http:
        assert http.get(URL, headers=headers).status_code == 503  # migration applied, collection off
        with database.begin() as conn:
            local_today = conn.scalar(text("SELECT clock_timestamp()")).astimezone(MOSCOW).date()
            monday = local_today - timedelta(days=local_today.weekday())
            small = datetime.combine(monday - timedelta(weeks=4), time(), MOSCOW)
            visible = small + timedelta(weeks=1)
            empty = visible + timedelta(weeks=1)
            simulate_coverage(conn, small)
            insert_events(conn, "requested", small - timedelta(microseconds=1), 9)  # before coverage
            insert_events(conn, "requested", small, 5)
            insert_events(conn, "approved", visible - timedelta(microseconds=1), 4)
            for event_type in ("requested", "approved", "rejected", "completed"):
                insert_events(conn, event_type, visible, 5)
            insert_events(conn, "requested", datetime.combine(monday, time(), MOSCOW), 9)  # current week

        assert http.get(URL, headers=headers).status_code == 503  # the due weeks are still missing
        with database.begin() as conn:
            assert conn.scalar(text("SELECT appointment_metrics.refresh()")) >= 3
            assert conn.scalar(text("SELECT appointment_metrics.refresh()")) == 0
            rows = conn.execute(text("SELECT * FROM appointment_metrics.weekly ORDER BY week_start")).mappings().all()
            stored = {row["week_start"]: dict(row) for row in rows}
        assert stored[small.date()]["requested"] == 5 and stored[small.date()]["approved"] == 4
        assert {stored[visible.date()][key] for key in ("requested", "approved", "rejected", "completed")} == {5}

        response = http.get(URL, headers=headers)
        assert response.status_code == 200
        assert response.headers["Cache-Control"] == "no-store"
        assert response.headers["X-Request-ID"]
        body = response.json()
        assert body["timezone"] == "Europe/Moscow" and body["minimum_group"] == 5
        weeks = {week["week_start"]: week for week in body["weeks"]}
        assert list(weeks) == sorted(weeks) and monday.isoformat() not in weeks

        assert weeks[small.date().isoformat()] == {
            "week_start": small.date().isoformat(),
            "requested": None, "approved": None, "rejected": None, "completed": None, "suppressed": True,
        }
        assert weeks[visible.date().isoformat()] == {
            "week_start": visible.date().isoformat(),
            "requested": 5, "approved": 5, "rejected": 5, "completed": 5, "suppressed": False,
        }
        assert weeks[empty.date().isoformat()] == {
            "week_start": empty.date().isoformat(),
            "requested": 0, "approved": 0, "rejected": 0, "completed": 0, "suppressed": False,
        }

        with database.begin() as conn:
            insert_events(conn, "completed", empty)
        with pytest.raises(DBAPIError, match="Published appointment counts differ"), database.begin() as conn:
            conn.execute(text("SELECT appointment_metrics.refresh()"))
        assert http.get(URL, headers=headers).json() == body


def test_refresh_waits_for_committed_source_transaction(database):
    with database.begin() as conn:
        local_today = conn.scalar(text("SELECT clock_timestamp()")).astimezone(MOSCOW).date()
        closed_week = local_today - timedelta(days=local_today.weekday(), weeks=2)
        start = datetime.combine(closed_week, time(), MOSCOW)
        simulate_coverage(conn, start)

    def refresh():
        with database.begin() as conn:
            conn.exec_driver_sql("SET LOCAL lock_timeout = '3s'")
            return conn.scalar(text("SELECT appointment_metrics.refresh()"))

    with ThreadPoolExecutor(max_workers=1) as pool, database.connect() as writer:
        insert_events(writer, "requested", start, 5)
        pending = pool.submit(refresh)
        try:
            with database.connect() as observer:
                for _ in range(40):
                    observer.exec_driver_sql("SELECT pg_sleep(0.025)")
                    waits = observer.scalar(text(
                        "SELECT count(*) FROM pg_locks WHERE NOT granted AND mode = 'ShareRowExclusiveLock' "
                        "AND relation = 'appointment_events.events'::regclass"
                    ))
                    if waits:
                        break
            assert waits == 1
            writer.commit()
        finally:
            writer.rollback()
        assert pending.result(timeout=5) >= 1
    with database.connect() as conn:
        assert conn.execute(SUMMARY).mappings().first()["requested"] == 5


def test_database_roles_only_access_their_functions(database):
    roles = {name: f"test_{name}_{uuid4().hex}" for name in ("reader", "writer", "etl")}
    with database.connect() as conn:
        for role in roles.values():
            conn.exec_driver_sql(f"CREATE ROLE {role}")
        for name, schema, functions in (
            ("reader", "appointment_metrics", ("summary()",)),
            ("writer", "appointment_events", ("record(uuid, text)",)),
            ("etl", "appointment_metrics", ("enable()", "refresh()")),
        ):
            role = roles[name]
            conn.exec_driver_sql(f"GRANT USAGE ON SCHEMA {schema} TO {role}")
            for function in functions:
                conn.exec_driver_sql(f"GRANT EXECUTE ON FUNCTION {schema}.{function} TO {role}")

        checks = {
            "reader": ("SELECT appointment_metrics.enable()", "SELECT * FROM appointment_metrics.weekly",
                       "SELECT * FROM appointment_events.events"),
            "writer": ("SELECT * FROM appointment_events.events", "SELECT * FROM appointment_metrics.summary()"),
            "etl": ("SELECT * FROM appointment_events.events", "SELECT * FROM appointment_metrics.weekly"),
        }
        for name, statements in checks.items():
            conn.exec_driver_sql(f"SET LOCAL ROLE {roles[name]}")
            for statement in statements:
                with pytest.raises(DBAPIError, match="permission denied"), conn.begin_nested():
                    conn.exec_driver_sql(statement)
            if name == "writer":
                conn.execute(text("SELECT appointment_events.record(:id, 'requested')"), {"id": uuid4()})
            if name == "etl":
                conn.exec_driver_sql("SELECT appointment_metrics.enable()")
                assert conn.scalar(text("SELECT appointment_metrics.refresh()")) == 0
            conn.exec_driver_sql("RESET ROLE")
        conn.exec_driver_sql(f"SET LOCAL ROLE {roles['reader']}")
        assert conn.execute(SUMMARY).all() == []
        conn.rollback()
