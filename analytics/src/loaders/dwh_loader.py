import logging
from typing import List
import pandas as pd
from sqlalchemy import create_engine, text
from analytics.src.config import settings
from analytics.src.schemas.validation import RawDonationRecord

logger = logging.getLogger(__name__)


class DWHLoader:
    """Handles idempotent batch loading into PostgreSQL DWH layers."""

    def __init__(self, connection_url: str = settings.database_url):
        self.engine = create_engine(connection_url)

    def load_staging_donations(self, records: List[RawDonationRecord]) -> int:
        """Inserts validated raw records into the staging layer."""
        if not records:
            logger.info("No records to load into staging.")
            return 0

        rows = [
            {
                "transaction_id": r.transaction_id,
                "user_id": r.user_id,
                "amount": r.amount,
                "currency": r.currency.value,
                "fund_type": r.fund_type.value,
                "payment_method": r.payment_method,
                "raw_created_at": r.created_at.isoformat(),
            }
            for r in records
        ]
        df = pd.DataFrame(rows)
        df.to_sql(
            name="stg_donations",
            schema="staging",
            con=self.engine,
            if_exists="append",
            index=False,
            method="multi",
        )
        logger.info(f"Loaded {len(df)} rows into staging.stg_donations.")
        return len(df)

    def upsert_daily_finances(self, df_metrics: pd.DataFrame) -> None:
        """Idempotently updates the daily finances datamart."""
        if df_metrics.empty:
            return

        with self.engine.begin() as conn:
            for _, row in df_metrics.iterrows():
                query = text("""
                    INSERT INTO marts.mart_daily_finances 
                        (report_date, fund_type, total_amount, transaction_count, avg_donation)
                    VALUES 
                        (:report_date, :fund_type, :total_amount, :transaction_count, :avg_donation)
                    ON CONFLICT (report_date, fund_type) DO UPDATE SET
                        total_amount = EXCLUDED.total_amount,
                        transaction_count = EXCLUDED.transaction_count,
                        avg_donation = EXCLUDED.avg_donation;
                """)
                conn.execute(query, row.to_dict())
        logger.info(f"Upserted {len(df_metrics)} rows into marts.mart_daily_finances.")
