from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..data import ITEMS

router = APIRouter(prefix="/api/v1/items", tags=["Shop"])


class Item(BaseModel):
    item_id: str
    title: str
    description: str = ""
    category: str
    price: float = Field(ge=0)
    stock_quantity: int = Field(ge=0)
    image_url: str | None = None
    is_available: bool = True


@router.get("", response_model=list[Item])
async def list_items(category: str | None = None, is_available: bool | None = None):
    """Return shop items, optionally filtered by category and availability."""
    items = ITEMS
    if category is not None:
        items = [i for i in items if i["category"] == category]
    if is_available is not None:
        items = [i for i in items if i["is_available"] == is_available]
    return items


@router.get("/{item_id}", response_model=Item)
async def get_item(item_id: str):
    for item in ITEMS:
        if item["item_id"] == item_id:
            return item
    raise HTTPException(status_code=404, detail="Item not found")
