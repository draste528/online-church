from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional, Tuple
from pydantic import BaseModel, Field, field_validator, model_validator


class FundType(str, Enum):
    GENERAL = "general"
    TEMPLE_RESTORATION = "temple_restoration"
    CHOIR = "choir"
    CHARITY = "charity"
    MINECRAFT_CHURCH = "minecraft_church"


class CurrencyType(str, Enum):
    RUB = "RUB"
    BYN = "BYN"
    USD = "USD"


class RawDonationRecord(BaseModel):
    transaction_id: str = Field(..., min_length=5, max_length=100)
    user_id: Optional[str] = Field(default=None, max_length=100)
    amount: float = Field(..., gt=0, description="Amount must be strictly positive")
    currency: CurrencyType
    fund_type: FundType
    payment_method: str = Field(default="card", max_length=50)
    created_at: datetime
    note_text: Optional[str] = Field(default=None, max_length=500)

    @field_validator("created_at")
    @classmethod
    def validate_not_in_future(cls, v: datetime) -> datetime:
        # Ensure timestamp is timezone-aware for comparison
        target_time = v if v.tzinfo else v.replace(tzinfo=timezone.utc)
        current_time = datetime.now(timezone.utc)
        if target_time > current_time:
            raise ValueError("Transaction timestamp cannot be in the future")
        return target_time


class RawStreamMetricRecord(BaseModel):
    stream_id: str = Field(..., min_length=3, max_length=100)
    service_name: str = Field(..., max_length=150)
    peak_viewers: int = Field(..., ge=0)
    avg_watch_time_seconds: int = Field(..., ge=0)
    chat_messages_count: int = Field(..., ge=0)
    donations_during_stream: float = Field(..., ge=0.0)


def validate_donations_batch(records: List[dict]) -> Tuple[List[RawDonationRecord], List[dict]]:
    """Separates a batch of dictionary payloads into valid records and error records."""
    valid_records: List[RawDonationRecord] = []
    bad_records: List[dict] = []

    for raw_item in records:
        try:
            validated = RawDonationRecord(**raw_item)
            valid_records.append(validated)
        except Exception as exc:
            bad_records.append({"raw_data": raw_item, "error": str(exc)})

    return valid_records, bad_records
