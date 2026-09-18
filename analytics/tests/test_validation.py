from datetime import datetime, timedelta, timezone
import pytest
from analytics.src.schemas.validation import RawDonationRecord, validate_donations_batch


def test_valid_donation_record():
    payload = {
        "transaction_id": "tx_valid_001",
        "user_id": "usr_10",
        "amount": 250.0,
        "currency": "RUB",
        "fund_type": "temple_restoration",
        "created_at": datetime.now(timezone.utc),
    }
    record = RawDonationRecord(**payload)
    assert record.amount == 250.0
    assert record.fund_type == "temple_restoration"


def test_reject_negative_amount():
    payload = {
        "transaction_id": "tx_invalid_amount",
        "amount": -50.0,
        "currency": "RUB",
        "fund_type": "general",
        "created_at": datetime.now(timezone.utc),
    }
    with pytest.raises(ValueError):
        RawDonationRecord(**payload)


def test_reject_future_timestamp():
    future_time = datetime.now(timezone.utc) + timedelta(days=2)
    payload = {
        "transaction_id": "tx_future",
        "amount": 100.0,
        "currency": "RUB",
        "fund_type": "charity",
        "created_at": future_time,
    }
    with pytest.raises(ValueError, match="Transaction timestamp cannot be in the future"):
        RawDonationRecord(**payload)


def test_validate_batch_isolation():
    items = [
        {
            "transaction_id": "tx_good",
            "amount": 100.0,
            "currency": "BYN",
            "fund_type": "choir",
            "created_at": datetime.now(timezone.utc),
        },
        {
            "transaction_id": "tx_bad",
            "amount": 0.0,  # Invalid: amount must be > 0
            "currency": "BYN",
            "fund_type": "choir",
            "created_at": datetime.now(timezone.utc),
        },
    ]
    valid, bad = validate_donations_batch(items)
    assert len(valid) == 1
    assert len(bad) == 1
    assert valid[0].transaction_id == "tx_good"
