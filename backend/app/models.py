"""ORM models. Only the tables the API currently writes to are mapped.

The authoritative DDL is docs/church_db_init.sql; the constraints are mirrored here so that the
SQLite database used by local runs and tests behaves like PostgreSQL.
"""
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base

FUND_CODES = ("general", "temple_restoration", "choir", "charity", "minecraft_church")
PAYMENT_STATUSES = ("pending", "completed", "failed")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Donation(Base):
    """A donation. Card data is never stored: the table has no column for it."""

    __tablename__ = "donations"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_donations_amount_positive"),
        CheckConstraint(f"target_fund IN {FUND_CODES}", name="ck_donations_target_fund"),
        CheckConstraint(f"payment_status IN {PAYMENT_STATUSES}", name="ck_donations_payment_status"),
    )

    donation_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # The real table has a foreign key to users; guest donations leave it empty.
    user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="RUB")
    target_fund: Mapped[str] = mapped_column(String(50), nullable=False)
    payment_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    minecraft_blocks_awarded: Mapped[int] = mapped_column(nullable=False, default=0)
    transaction_reference: Mapped[str | None] = mapped_column(String(100), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
