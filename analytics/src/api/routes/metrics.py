from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import create_engine, text
from analytics.src.config import settings

router = APIRouter(prefix="/api/v1/analytics", tags=["Analytics & Datamarts"])
engine = create_engine(settings.database_url)


class DailySummaryResponse(BaseModel):
    report_date: date
    fund_type: str
    total_amount: float
    transaction_count: int
    avg_donation: float


class FundDistributionItem(BaseModel):
    fund_type: str
    total_collected: float
    percentage: float


@router.get("/summary", response_model=List[DailySummaryResponse])
async def get_daily_summary(target_date: Optional[date] = Query(default=None)):
    """Returns aggregated donation metrics for a given date or all available dates."""
    query = """
        SELECT report_date, fund_type, total_amount, transaction_count, avg_donation
        FROM marts.mart_daily_finances
        WHERE (:target_date IS NULL OR report_date = :target_date)
        ORDER BY report_date DESC, total_amount DESC;
    """
    with engine.connect() as conn:
        result = conn.execute(text(query), {"target_date": target_date}).fetchall()
        return [
            DailySummaryResponse(
                report_date=r.report_date,
                fund_type=r.fund_type,
                total_amount=float(r.total_amount),
                transaction_count=r.transaction_count,
                avg_donation=float(r.avg_donation),
            )
            for r in result
        ]


@router.get("/funds-distribution", response_model=List[FundDistributionItem])
async def get_funds_distribution():
    """Provides percentage breakdown of donations across church funds for pie charts."""
    query = """
        WITH TotalSum AS (
            SELECT COALESCE(SUM(total_amount), 1.0) AS grand_total 
            FROM marts.mart_daily_finances
        )
        SELECT 
            fund_type,
            SUM(total_amount) AS total_collected,
            ROUND((SUM(total_amount) / (SELECT grand_total FROM TotalSum) * 100)::numeric, 2) AS percentage
        FROM marts.mart_daily_finances
        GROUP BY fund_type;
    """
    with engine.connect() as conn:
        result = conn.execute(text(query)).fetchall()
        return [
            FundDistributionItem(
                fund_type=r.fund_type,
                total_collected=float(r.total_collected),
                percentage=float(r.percentage),
            )
            for r in result
        ]
