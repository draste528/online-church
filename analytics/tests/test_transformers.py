from datetime import datetime, timezone
from analytics.src.schemas.validation import RawDonationRecord
from analytics.src.transformers.aggregations import (
    calculate_daily_fund_metrics,
    transform_donations_to_dataframe,
)


def test_dataframe_deduplication_and_fx_conversion():
    now = datetime.now(timezone.utc)
    records = [
        RawDonationRecord(
            transaction_id="tx_dup_1",
            amount=100.0,
            currency="USD",  # 100 * 3.25 = 325.0 BYN
            fund_type="general",
            created_at=now,
        ),
        RawDonationRecord(
            transaction_id="tx_dup_1",  # Duplicate ID
            amount=100.0,
            currency="USD",
            fund_type="general",
            created_at=now,
        ),
    ]

    df = transform_donations_to_dataframe(records)
    assert len(df) == 1
    assert df.iloc[0]["amount_base"] == 325.0


def test_calculate_daily_fund_metrics():
    now = datetime.now(timezone.utc)
    records = [
        RawDonationRecord(
            transaction_id="tx_1",
            amount=100.0,
            currency="BYN",
            fund_type="general",
            created_at=now,
        ),
        RawDonationRecord(
            transaction_id="tx_2",
            amount=200.0,
            currency="BYN",
            fund_type="general",
            created_at=now,
        ),
    ]

    df = transform_donations_to_dataframe(records)
    metrics_df = calculate_daily_fund_metrics(df)

    assert len(metrics_df) == 1
    row = metrics_df.iloc[0]
    assert row["transaction_count"] == 2
    assert row["total_amount"] == 300.0
    assert row["avg_donation"] == 150.0
