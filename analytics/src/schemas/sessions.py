"""Validation schemas for parishioner session analytics."""
from datetime import datetime
from pydantic import BaseModel, Field


class RawSessionRecord(BaseModel):
    session_id: str = Field(..., min_length=5, max_length=64)
    started_at: datetime
    ended_at: datetime
    duration_seconds: int = Field(default=0, ge=0)
    pages_visited: list[str] = Field(default_factory=list)
    total_donated: float = Field(default=0.0, ge=0.0)
    total_ordered: float = Field(default=0.0, ge=0.0)
    chat_messages_count: int = Field(default=0, ge=0)
    candles_lit_count: int = Field(default=0, ge=0)
    language: str = Field(default="ru", max_length=10)


class SessionAnalyticsSummary(BaseModel):
    total_sessions: int
    avg_duration_seconds: float
    total_amount_collected: float
    sessions_with_payments_count: int
    conversion_rate_percent: float
    top_visited_pages: list[dict]
    total_chat_questions: int
    total_candles_lit: int