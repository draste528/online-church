import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.db import get_db, init_db, make_engine
from backend.app.main import app
from backend.app.models import Item

# SQLite has no native Decimal type; the warning is expected and harmless here.
pytestmark = pytest.mark.filterwarnings("ignore:Dialect sqlite")

client = TestClient(app)


@pytest.fixture(autouse=True)
def database():
    """A fresh in-memory SQLite database (with the demo catalogue) for every test."""
    engine = make_engine("sqlite://")
    init_db(engine, seed=True)

    def override_db():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    yield engine
    app.dependency_overrides.pop(get_db, None)
    engine.dispose()


def find_item(title_part: str) -> dict:
    items = client.get("/api/v1/items").json()
    return next(i for i in items if title_part in i["title"])


def test_items_filter_by_category():
    data = client.get("/api/v1/items", params={"category": "candle"}).json()
    assert data and all(i["category"] == "candle" for i in data)


def test_items_filter_available():
    data = client.get("/api/v1/items", params={"is_available": True}).json()
    assert data and all(i["is_available"] for i in data)


def test_item_by_id_and_not_found():
    item = find_item("Молитвослов")
    assert client.get(f"/api/v1/items/{item['item_id']}").json()["title"] == "Молитвослов"
    assert client.get("/api/v1/items/00000000-0000-0000-0000-000000000000").status_code == 404
    assert client.get("/api/v1/items/nope").status_code == 422


def test_items_search_is_case_insensitive_for_cyrillic():
    data = client.get("/api/v1/items", params={"q": "СВЕЧА"}).json()
    assert data and all("свеч" in (i["title"] + i["description"]).lower() for i in data)


def test_items_sort_and_price_range():
    data = client.get("/api/v1/items", params={"sort": "price_desc"}).json()
    prices = [i["price"] for i in data]
    assert prices == sorted(prices, reverse=True)
    ranged = client.get("/api/v1/items", params={"min_price": 10, "max_price": 20}).json()
    assert ranged and all(10 <= i["price"] <= 20 for i in ranged)


def test_item_categories():
    names = {c["category"] for c in client.get("/api/v1/items/categories").json()}
    assert {"candle", "icon", "incense", "prosphora", "cross", "literature"} <= names


def test_init_db_does_not_duplicate_seed(database):
    before = len(client.get("/api/v1/items").json())
    assert init_db(database, seed=True) == (True, "ok")
    assert len(client.get("/api/v1/items").json()) == before


def test_init_db_without_seed_leaves_catalogue_empty():
    engine = make_engine("sqlite://")
    try:
        assert init_db(engine, seed=False) == (True, "ok")
        with Session(engine) as session:
            assert session.query(Item).count() == 0
    finally:
        engine.dispose()


def test_order_saves_totals_and_decreases_stock():
    candle = find_item("Свеча восковая")
    lines = [{"item_id": candle["item_id"], "quantity": 2}, {"item_id": candle["item_id"], "quantity": 1}]
    res = client.post("/api/v1/orders", json={"lines": lines})
    assert res.status_code == 201
    body = res.json()
    assert body["total"] == 4.5 and body["lines"][0]["quantity"] == 3
    after = client.get(f"/api/v1/items/{candle['item_id']}").json()
    assert after["stock_quantity"] == candle["stock_quantity"] - 3


def test_order_selling_last_items_makes_item_unavailable(database):
    with Session(database) as session:
        item = session.query(Item).filter(Item.title.like("Икона Спасителя")).one()
        item.stock_quantity = 2
        session.commit()
        item_id = str(item.item_id)
    assert client.post("/api/v1/orders", json={"lines": [{"item_id": item_id, "quantity": 2}]}).status_code == 201
    assert client.get(f"/api/v1/items/{item_id}").json()["is_available"] is False
    assert client.post("/api/v1/orders", json={"lines": [{"item_id": item_id, "quantity": 1}]}).status_code == 409


def test_order_rejects_bad_requests():
    sold_out = find_item("Просфора")
    assert sold_out["is_available"] is False
    lines = [{"item_id": sold_out["item_id"], "quantity": 1}]
    assert client.post("/api/v1/orders", json={"lines": lines}).status_code == 409
    unknown = [{"item_id": "00000000-0000-0000-0000-000000000000", "quantity": 1}]
    assert client.post("/api/v1/orders", json={"lines": unknown}).status_code == 404
    assert client.post("/api/v1/orders", json={"lines": []}).status_code == 422


def test_failed_order_changes_nothing():
    candle = find_item("Свеча восковая")
    sold_out = find_item("Просфора")
    lines = [{"item_id": candle["item_id"], "quantity": 1}, {"item_id": sold_out["item_id"], "quantity": 1}]
    assert client.post("/api/v1/orders", json={"lines": lines}).status_code == 409
    assert find_item("Свеча восковая")["stock_quantity"] == candle["stock_quantity"]
