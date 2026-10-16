import uuid
from enum import Enum

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Item as ItemRow

router = APIRouter(prefix="/api/v1/items", tags=["Shop"])


class Item(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    item_id: uuid.UUID
    title: str
    description: str | None = ""
    category: str
    price: float = Field(ge=0)
    stock_quantity: int = Field(ge=0)
    image_url: str | None = None
    is_available: bool = True


class CategoryInfo(BaseModel):
    category: str
    count: int


class SortOrder(str, Enum):
    default = "default"
    price_asc = "price_asc"
    price_desc = "price_desc"
    title = "title"


@router.get("", response_model=list[Item])
def list_items(
    category: str | None = None,
    is_available: bool | None = None,
    q: str | None = Query(default=None, description="Case-insensitive search in title and description"),
    min_price: float | None = Query(default=None, ge=0),
    max_price: float | None = Query(default=None, ge=0),
    sort: SortOrder = SortOrder.default,
    db: Session = Depends(get_db),
):
    """Return shop items with optional filters (category, availability, text, price range) and sorting."""
    stmt = select(ItemRow)
    if category is not None:
        stmt = stmt.where(ItemRow.category == category)
    if is_available is not None:
        stmt = stmt.where(ItemRow.is_available == is_available)
    if q and q.strip():
        needle = q.strip().lower()
        stmt = stmt.where(
            func.lower(ItemRow.title).contains(needle, autoescape=True)
            | func.lower(func.coalesce(ItemRow.description, "")).contains(needle, autoescape=True)
        )
    if min_price is not None:
        stmt = stmt.where(ItemRow.price >= min_price)
    if max_price is not None:
        stmt = stmt.where(ItemRow.price <= max_price)

    if sort == SortOrder.price_asc:
        stmt = stmt.order_by(ItemRow.price, ItemRow.title)
    elif sort == SortOrder.price_desc:
        stmt = stmt.order_by(ItemRow.price.desc(), ItemRow.title)
    elif sort == SortOrder.title:
        stmt = stmt.order_by(func.lower(ItemRow.title))
    else:
        stmt = stmt.order_by(ItemRow.created_at, ItemRow.title)
    return db.scalars(stmt).all()


@router.get("/categories", response_model=list[CategoryInfo])
def list_categories(db: Session = Depends(get_db)):
    """Categories that currently have at least one item, with item counts."""
    rows = db.execute(select(ItemRow.category, func.count()).group_by(ItemRow.category).order_by(ItemRow.category))
    return [CategoryInfo(category=category, count=count) for category, count in rows]


@router.get("/{item_id}", response_model=Item)
def get_item(item_id: uuid.UUID, db: Session = Depends(get_db)):
    item = db.get(ItemRow, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return item
