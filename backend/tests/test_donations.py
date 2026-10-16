import logging
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.app.db import Base, get_db
from backend.app.main import app
from backend.app.models import Donation

# SQLite has no native Decimal type; the warning is expected and harmless here.
pytestmark = pytest.mark.filterwarnings("ignore:Dialect sqlite")

CARD = "4111 1111 1111 1111"
CVC = "123"


def future_expiry() -> str:
    return f"12/{(datetime.now(timezone.utc).year + 2) % 100:02d}"


def valid_payload(**overrides) -> dict:
    payload = {
        "amount": 500,
        "target_fund": "charity",
        "card_number": CARD,
        "card_expiry": future_expiry(),
        "card_cvc": CVC,
    }
    payload.update(overrides)
    return payload


@pytest.fixture()
def db_engine():
    """A throw-away in-memory database: the tests never need PostgreSQL."""
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def client(db_engine):
    def override_get_db():
        with Session(db_engine, expire_on_commit=False) as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.pop(get_db, None)


def test_valid_donation_is_recorded_as_completed(client, db_engine):
    res = client.post("/api/v1/donations", json=valid_payload())

    assert res.status_code == 201
    body = res.json()
    assert body["payment_status"] == "completed"
    assert body["card_last4"] == "1111"
    assert body["currency"] == "USD"
    assert body["transaction_reference"].startswith("DON-")
    with Session(db_engine) as session:
        row = session.scalars(select(Donation)).one()
    assert row.payment_status == "completed"
    assert float(row.amount) == 500.0
    assert row.target_fund == "charity"
    assert row.transaction_reference == body["transaction_reference"]


def test_card_number_and_cvc_are_neither_stored_nor_logged(client, db_engine, caplog):
    with caplog.at_level(logging.DEBUG):
        res = client.post("/api/v1/donations", json=valid_payload())

    assert res.status_code == 201
    assert CARD not in res.text and "4111111111111111" not in res.text
    logged = " ".join(record.getMessage() for record in caplog.records)
    assert "4111" not in logged.replace("card_last4=1111", "")
    assert "card_last4=1111" in logged
    columns = {column.name for column in Donation.__table__.columns}
    assert not {"card_number", "card_cvc", "card_expiry"} & columns


def test_invalid_card_is_rejected_with_422_and_nothing_is_echoed(client, db_engine):
    res = client.post("/api/v1/donations", json=valid_payload(card_number="1234 5678"))

    assert res.status_code == 422
    assert "1234 5678" not in res.text
    assert any(error["loc"][-1] == "card_number" for error in res.json()["detail"])
    with Session(db_engine) as session:
        assert session.scalars(select(Donation)).all() == []


# TODO(Anton): the tests below are yours. Remove the skip marker and fill in the body one by one.
@pytest.mark.skip(reason="TODO(Anton): boundary amounts: 0, -1, 0.01, 5000, 5000.01, three decimal places")
def test_amount_boundaries():
    # Idea: parametrize over the amounts, expect 422 below/above the limits and 201 on the limits themselves.
    ...


@pytest.mark.skip(reason="TODO(Anton): invalid card numbers: letters, 15/17 digits, mixed separators, empty string")
def test_invalid_card_numbers():
    ...


@pytest.mark.skip(reason="TODO(Anton): expired card (last month) is rejected, the current month is still accepted")
def test_expired_card_is_rejected():
    # Idea: patch backend.app.api.donations.current_month to pin the clock.
    ...


@pytest.mark.skip(reason="TODO(Anton): CVC must be exactly three digits (two, four, letters, spaces)")
def test_invalid_cvc():
    ...


@pytest.mark.skip(reason="TODO(Anton): unknown target_fund answers 422 and writes nothing")
def test_unknown_fund_is_rejected():
    ...


@pytest.mark.skip(reason="TODO(Anton): a clashing transaction_reference is retried and the payment still succeeds")
def test_duplicate_transaction_reference_is_retried():
    # Idea: patch generate_transaction_reference to return the same value twice, then a new one.
    ...


@pytest.mark.skip(reason="TODO(Anton): database failure answers 503 with a readable message")
def test_database_failure_answers_503():
    # Idea: override get_db with a session whose commit raises sqlalchemy.exc.OperationalError.
    ...


@pytest.mark.skip(reason="TODO(Anton): minecraft_church awards one block per US dollar, other funds award none")
def test_minecraft_blocks_are_awarded_only_for_the_minecraft_fund():
    ...
