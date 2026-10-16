"""Donations with a FAKE card payment.

Nothing is charged: if the card fields have a valid format the payment counts as successful and a row with
payment_status='completed' is written. The card number and CVC are validated and then dropped; they are never
stored or logged, only the last four digits appear in the response and in the log.
"""
import logging
import re
import secrets
import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import CURRENCY, FUND_CODES, Donation

router = APIRouter(prefix="/api/v1/donations", tags=["Donations"])
log = logging.getLogger(__name__)

MAX_DONATION_AMOUNT = Decimal("5000")
MAX_REFERENCE_ATTEMPTS = 3

CARD_NUMBER_RE = re.compile(r"^\d{4}([ -]?\d{4}){3}$")
CARD_EXPIRY_RE = re.compile(r"^(0[1-9]|1[0-2])/(\d{2})$")
CARD_CVC_RE = re.compile(r"^\d{3}$")

FundCode = Literal[*FUND_CODES]  # the same list as the CHECK constraint of the donations table


def current_month() -> tuple[int, int]:
    """(year, month) of today in UTC. A separate function so tests can pin the clock."""
    now = datetime.now(timezone.utc)
    return now.year, now.month


class DonationIn(BaseModel):
    amount: Decimal
    target_fund: FundCode
    # repr=False keeps the card data out of tracebacks and accidental log lines.
    card_number: str = Field(repr=False)
    card_expiry: str
    card_cvc: str = Field(repr=False)

    @field_validator("amount", mode="before")
    @classmethod
    def parse_amount(cls, value: object) -> Decimal:
        if isinstance(value, bool) or value is None:
            raise ValueError("Укажите сумму числом.")
        try:
            return Decimal(str(value).strip())
        except InvalidOperation as exc:
            raise ValueError("Укажите сумму числом.") from exc

    @field_validator("amount")
    @classmethod
    def check_amount(cls, value: Decimal) -> Decimal:
        if not value.is_finite() or value <= 0:
            raise ValueError("Сумма должна быть больше нуля.")
        if value > MAX_DONATION_AMOUNT:
            raise ValueError(f"Сумма не может превышать {MAX_DONATION_AMOUNT:,.0f} $.".replace(",", " "))
        if value.as_tuple().exponent < -2:
            raise ValueError("У суммы не может быть больше двух знаков после запятой.")
        return value

    @field_validator("card_number")
    @classmethod
    def check_card_number(cls, value: str) -> str:
        if not CARD_NUMBER_RE.fullmatch(value.strip()):
            raise ValueError("Номер карты: 16 цифр в четыре группы по четыре (пробелы и дефисы допустимы).")
        return re.sub(r"\D", "", value)

    @field_validator("card_expiry")
    @classmethod
    def check_card_expiry(cls, value: str) -> str:
        match = CARD_EXPIRY_RE.fullmatch(value.strip())
        if not match:
            raise ValueError("Срок действия карты: формат ММ/ГГ, например 08/27.")
        month, year = int(match.group(1)), 2000 + int(match.group(2))
        if (year, month) < current_month():
            raise ValueError("Срок действия карты истёк.")
        return value.strip()

    @field_validator("card_cvc")
    @classmethod
    def check_card_cvc(cls, value: str) -> str:
        if not CARD_CVC_RE.fullmatch(value.strip()):
            raise ValueError("CVC: ровно три цифры.")
        return value.strip()


class DonationOut(BaseModel):
    donation_id: uuid.UUID
    payment_status: Literal["completed"]
    amount: float
    currency: str
    target_fund: FundCode
    transaction_reference: str
    card_last4: str
    minecraft_blocks_awarded: int
    created_at: datetime
    demo: bool = True


def generate_transaction_reference() -> str:
    """Unique, unguessable reference such as DON-20261015-3F9A1C07B2D4."""
    return f"DON-{datetime.now(timezone.utc):%Y%m%d}-{secrets.token_hex(6).upper()}"


@router.post("", response_model=DonationOut, status_code=201)
def create_donation(payload: DonationIn, db: Session = Depends(get_db)):
    """Accept a (fake) card payment and record the donation as completed."""
    last4 = payload.card_number[-4:]
    # 1 US dollar = 1 block of the Minecraft cathedral (see docs/API.md).
    blocks = int(payload.amount) if payload.target_fund == "minecraft_church" else 0
    donation = None
    try:
        for attempt in range(1, MAX_REFERENCE_ATTEMPTS + 1):
            donation = Donation(
                amount=payload.amount,
                currency=CURRENCY,
                target_fund=payload.target_fund,
                payment_status="completed",
                minecraft_blocks_awarded=blocks,
                transaction_reference=generate_transaction_reference(),
            )
            db.add(donation)
            try:
                db.commit()
                break
            except IntegrityError:
                # Practically impossible, but a clash of the unique reference must not fail the payment.
                db.rollback()
                log.warning("Transaction reference clash, retrying (attempt %d)", attempt)
                donation = None
    except SQLAlchemyError as exc:
        db.rollback()
        log.error("Could not save donation: %s", type(exc).__name__)
        raise HTTPException(
            status_code=503, detail="Сервис пожертвований временно недоступен. Попробуйте позже."
        ) from exc
    if donation is None:
        log.error("Could not generate a unique transaction reference after %d attempts", MAX_REFERENCE_ATTEMPTS)
        raise HTTPException(status_code=500, detail="Не удалось оформить пожертвование. Попробуйте ещё раз.")

    log.info(
        "Donation completed: id=%s fund=%s amount=%s %s card_last4=%s ref=%s",
        donation.donation_id, donation.target_fund, donation.amount, CURRENCY, last4, donation.transaction_reference,
    )
    return DonationOut(
        donation_id=donation.donation_id,
        payment_status="completed",
        amount=float(donation.amount),
        currency=donation.currency,
        target_fund=donation.target_fund,
        transaction_reference=donation.transaction_reference,
        card_last4=last4,
        minecraft_blocks_awarded=donation.minecraft_blocks_awarded,
        created_at=donation.created_at,
    )
