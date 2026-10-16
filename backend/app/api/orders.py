import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Item, ShopOrder, ShopOrderLine

router = APIRouter(prefix="/api/v1/orders", tags=["Shop"])


class OrderLineIn(BaseModel):
    item_id: uuid.UUID
    quantity: int = Field(ge=1, le=99)


class OrderIn(BaseModel):
    lines: list[OrderLineIn] = Field(min_length=1, max_length=50)
    customer_name: str | None = Field(default=None, max_length=80)


class OrderLineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    item_id: uuid.UUID
    title: str
    quantity: int
    unit_price: float
    line_total: float


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    order_id: uuid.UUID
    status: str
    lines: list[OrderLineOut]
    total: float


@router.post("", response_model=OrderOut, status_code=201)
def create_order(order: OrderIn, db: Session = Depends(get_db)):
    """Check the cart against stock, save the order and decrease stock, all in one transaction."""
    quantities: dict[uuid.UUID, int] = {}
    for line in order.lines:  # merge duplicate lines
        quantities[line.item_id] = quantities.get(line.item_id, 0) + line.quantity

    # Lock the rows in a stable order so that concurrent checkouts cannot oversell or deadlock.
    items = {
        item.item_id: item
        for item in db.scalars(
            select(Item).where(Item.item_id.in_(quantities)).order_by(Item.item_id).with_for_update()
        )
    }
    for item_id, quantity in quantities.items():
        item = items.get(item_id)
        if item is None:
            raise HTTPException(status_code=404, detail=f"Item not found: {item_id}")
        if not item.is_available or quantity > item.stock_quantity:
            raise HTTPException(status_code=409, detail=f"Not enough stock: {item_id}")

    new_order = ShopOrder(customer_name=order.customer_name, status="accepted", total=Decimal("0"))
    for item_id, quantity in quantities.items():
        item = items[item_id]
        line_total = item.price * quantity
        new_order.lines.append(
            ShopOrderLine(
                item_id=item_id, title=item.title, quantity=quantity, unit_price=item.price, line_total=line_total
            )
        )
        new_order.total += line_total
        item.stock_quantity -= quantity
        if item.stock_quantity == 0:
            item.is_available = False

    db.add(new_order)
    db.commit()
    db.refresh(new_order)
    return new_order
