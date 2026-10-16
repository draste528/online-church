"""ORM models. Only the tables the API currently reads or writes are mapped.

The authoritative DDL is docs/church_db_init.sql; the constraints are mirrored here so that the
SQLite database used by local runs and tests behaves like PostgreSQL.
"""
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base

ITEM_CATEGORIES = ("candle", "icon", "prosphora", "incense", "cross", "literature")
CURRENCY = "USD"  # the only donation currency; the analytics service filters by the same value
FUND_CODES = ("general", "temple_restoration", "choir", "charity", "minecraft_church")
PAYMENT_STATUSES = ("pending", "completed", "failed")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Item(Base):
    """A shop product (candles, icons, prosphora, ...)."""

    __tablename__ = "items"
    __table_args__ = (
        CheckConstraint(f"category IN {ITEM_CATEGORIES}", name="ck_items_category"),
        CheckConstraint("price >= 0", name="ck_items_price_non_negative"),
        CheckConstraint("stock_quantity >= 0", name="ck_items_stock_non_negative"),
        Index("idx_items_category", "category"),
    )

    item_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(150))
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(50))
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    stock_quantity: Mapped[int] = mapped_column(Integer, default=0)
    image_url: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), server_default=func.now())
    is_available: Mapped[bool] = mapped_column(Boolean, default=True)


class ShopOrder(Base):
    """A checked-out cart from the church shop. Declared in docs/church_db_init.sql; also created on startup."""

    __tablename__ = "shop_orders"
    __table_args__ = (CheckConstraint("total >= 0", name="ck_shop_orders_total_non_negative"),)

    order_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    customer_name: Mapped[str | None] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(20), default="accepted")
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), server_default=func.now())

    lines: Mapped[list["ShopOrderLine"]] = relationship(back_populates="order", cascade="all, delete-orphan")


class ShopOrderLine(Base):
    __tablename__ = "shop_order_lines"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_shop_order_lines_quantity_positive"),
        Index("idx_order_lines_order", "order_id"),
    )

    line_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shop_orders.order_id", ondelete="CASCADE"))
    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("items.item_id"))
    title: Mapped[str] = mapped_column(String(150))  # snapshot of the title at purchase time
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    line_total: Mapped[Decimal] = mapped_column(Numeric(12, 2))

    order: Mapped[ShopOrder] = relationship(back_populates="lines")


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
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default=CURRENCY)
    target_fund: Mapped[str] = mapped_column(String(50), nullable=False)
    payment_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    minecraft_blocks_awarded: Mapped[int] = mapped_column(nullable=False, default=0)
    transaction_reference: Mapped[str | None] = mapped_column(String(100), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
