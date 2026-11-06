"""Order tracking API (SCRUM-27), written against the contract in the TE-002 task.

GET   /api/v1/orders/{id}         -> 200 {order_id, status, created_at, total, lines[], history[{status, at, note}]}
PATCH /api/v1/orders/{id}/status  -> 200 / 404 / 409 (forbidden transition) / 422 (unknown status, note > 200 chars)

Flow: accepted -> assembling -> ready -> completed; "cancelled" only from accepted/assembling; cancel returns stock.

TODO(SCRUM-27): the endpoints are not on `dev` yet, so the whole module is marked xfail. Delete the single
`pytest.mark.xfail(...)` entry in `pytestmark` below as soon as SCRUM-27 is merged.
"""
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.db import get_db, init_db, make_engine
from backend.app.main import app
from backend.app.models import Item

pytestmark = [
    # SQLite has no native Decimal type; the warning is expected and harmless here.
    pytest.mark.filterwarnings("ignore:Dialect sqlite"),
    pytest.mark.xfail(reason="SCRUM-27"),
]

client = TestClient(app)

FLOW = ["accepted", "assembling", "ready", "completed"]
NOTE_LIMIT = 200


@pytest.fixture(autouse=True)
def database():
    """A fresh in-memory SQLite database (with the demo catalogue) for every test: no test depends on another."""
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


def create_order(title_part: str = "Свеча восковая", quantity: int = 2) -> dict:
    item = find_item(title_part)
    res = client.post("/api/v1/orders", json={"lines": [{"item_id": item["item_id"], "quantity": quantity}]})
    assert res.status_code == 201, res.text
    return res.json()


def set_status(order_id: str, status: str, **extra):
    return client.patch(f"/api/v1/orders/{order_id}/status", json={"status": status, **extra})


def get_order(order_id: str) -> dict:
    res = client.get(f"/api/v1/orders/{order_id}")
    assert res.status_code == 200, res.text
    return res.json()


def advance_to(order_id: str, target: str) -> None:
    for status in FLOW[1 : FLOW.index(target) + 1]:
        assert set_status(order_id, status).status_code == 200


# 1. A freshly created order
def test_new_order_is_accepted_and_matches_the_create_response():
    created = create_order(quantity=3)

    res = client.get(f"/api/v1/orders/{created['order_id']}")

    assert res.status_code == 200
    body = res.json()
    assert body["order_id"] == created["order_id"]
    assert body["status"] == "accepted"
    assert body["created_at"]
    assert body["lines"] == created["lines"]
    assert body["total"] == created["total"]
    assert len(body["history"]) == 1
    assert body["history"][0]["status"] == "accepted"


# 2. Reading: not found / invalid id
def test_get_unknown_order_is_404():
    assert client.get(f"/api/v1/orders/{uuid.uuid4()}").status_code == 404


def test_get_order_with_invalid_uuid_is_422():
    assert client.get("/api/v1/orders/abc").status_code == 422


# 3. The full happy path
def test_full_path_accepted_to_completed_grows_history_in_order():
    order_id = create_order()["order_id"]

    for step, status in enumerate(FLOW[1:], start=2):
        res = set_status(order_id, status)
        assert res.status_code == 200, res.text
        assert get_order(order_id)["status"] == status
        assert len(get_order(order_id)["history"]) == step

    history = get_order(order_id)["history"]
    assert [event["status"] for event in history] == FLOW
    timestamps = [event["at"] for event in history]
    assert timestamps == sorted(timestamps)  # ISO-8601 strings in one format sort chronologically


# 4. Forbidden transitions
@pytest.mark.parametrize(
    ("path", "forbidden"),
    [
        ([], "ready"),  # accepted -> ready
        ([], "completed"),  # accepted -> completed
        (["assembling", "ready"], "cancelled"),  # ready -> cancelled
        (["assembling", "ready", "completed"], "assembling"),  # completed -> assembling
        (["cancelled"], "accepted"),  # cancelled -> accepted
    ],
    ids=["accepted-ready", "accepted-completed", "ready-cancelled", "completed-assembling", "cancelled-accepted"],
)
def test_forbidden_transition_is_409_and_status_does_not_change(path, forbidden):
    order_id = create_order()["order_id"]
    for status in path:
        assert set_status(order_id, status).status_code == 200
    before = get_order(order_id)

    res = set_status(order_id, forbidden)

    assert res.status_code == 409
    after = get_order(order_id)
    assert after["status"] == before["status"]
    assert len(after["history"]) == len(before["history"])


# 5. Validation of the request body
def test_unknown_status_is_422():
    order_id = create_order()["order_id"]

    assert set_status(order_id, "shipped").status_code == 422
    assert get_order(order_id)["status"] == "accepted"


def test_note_longer_than_200_chars_is_422():
    order_id = create_order()["order_id"]

    assert set_status(order_id, "assembling", note="x" * (NOTE_LIMIT + 1)).status_code == 422
    assert get_order(order_id)["status"] == "accepted"


def test_note_of_exactly_200_chars_is_accepted_and_saved_in_history():
    order_id = create_order()["order_id"]
    note = "x" * NOTE_LIMIT

    assert set_status(order_id, "assembling", note=note).status_code == 200
    assert get_order(order_id)["history"][-1]["note"] == note


# 6. Cancelling returns stock
def test_cancel_returns_stock_to_the_value_before_the_order():
    stock_before = find_item("Свеча восковая")["stock_quantity"]
    order_id = create_order("Свеча восковая", quantity=3)["order_id"]
    assert find_item("Свеча восковая")["stock_quantity"] == stock_before - 3

    assert set_status(order_id, "cancelled").status_code == 200

    assert find_item("Свеча восковая")["stock_quantity"] == stock_before
    assert get_order(order_id)["status"] == "cancelled"


def test_cancel_from_assembling_also_returns_stock():
    stock_before = find_item("Молитвослов")["stock_quantity"]
    order_id = create_order("Молитвослов", quantity=1)["order_id"]
    assert set_status(order_id, "assembling").status_code == 200

    assert set_status(order_id, "cancelled").status_code == 200

    assert find_item("Молитвослов")["stock_quantity"] == stock_before


def test_cancel_makes_a_sold_out_item_available_again(database):
    item = find_item("Свеча восковая")
    with Session(database) as session:
        session.get(Item, uuid.UUID(item["item_id"])).stock_quantity = 2
        session.commit()
    order_id = create_order("Свеча восковая", quantity=2)["order_id"]
    sold_out = find_item("Свеча восковая")
    assert sold_out["stock_quantity"] == 0
    assert sold_out["is_available"] is False

    assert set_status(order_id, "cancelled").status_code == 200

    restored = find_item("Свеча восковая")
    assert restored["stock_quantity"] == 2
    assert restored["is_available"] is True


# 7. Updating a nonexistent order
def test_patch_unknown_order_is_404():
    assert set_status(str(uuid.uuid4()), "assembling").status_code == 404
