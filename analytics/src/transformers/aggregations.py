from typing import List
import pandas as pd
from analytics.src.schemas.validation import RawDonationRecord


# Exchange rates relative to base currency (BYN)
FX_RATES_TO_BYN = {
    "BYN": 1.0,
    "RUB": 0.035,
    "USD": 3.25,
}


def transform_donations_to_dataframe(records: List[RawDonationRecord]) -> pd.DataFrame:
    """Converts Pydantic records to DataFrame, removes duplicates, and standardizes currency."""
    if not records:
        return pd.DataFrame()

    data = [item.model_dump() for item in records]
    df = pd.DataFrame(data)

    # 1. Deduplication by unique transaction_id
    df = df.drop_duplicates(subset=["transaction_id"], keep="first")

    # 2. Currency normalization to base currency (BYN)
    df["fx_rate"] = df["currency"].map(FX_RATES_TO_BYN).fillna(1.0)
    df["amount_base"] = (df["amount"] * df["fx_rate"]).round(2)

    # 3. Datetime extraction
    df["report_date"] = pd.to_datetime(df["created_at"]).dt.date

    return df


def calculate_daily_fund_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Computes daily aggregated finance metrics per fund."""
    if df.empty:
        return pd.DataFrame(columns=["report_date", "fund_type", "total_amount", "transaction_count", "avg_donation"])

    aggregated = (
        df.groupby(["report_date", "fund_type"])
        .agg(
            total_amount=("amount_base", "sum"),
            transaction_count=("transaction_id", "count"),
            avg_donation=("amount_base", "mean"),
        )
        .reset_index()
    )

    aggregated["total_amount"] = aggregated["total_amount"].round(2)
    aggregated["avg_donation"] = aggregated["avg_donation"].round(2)

    return aggregated
