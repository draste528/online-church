from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_health():
    assert client.get("/health").json()["status"] == "ok"


def test_items_filter_by_category():
    data = client.get("/api/v1/items", params={"category": "candle"}).json()
    assert data and all(i["category"] == "candle" for i in data)


def test_items_filter_available():
    data = client.get("/api/v1/items", params={"is_available": True}).json()
    assert all(i["is_available"] for i in data)


def test_item_not_found():
    assert client.get("/api/v1/items/nope").status_code == 404


def test_chat_message():
    res = client.post("/api/v1/chats/messages", json={"content": "Мир вам"})
    assert res.status_code == 200 and res.json()["reply"]


def test_chat_rejects_empty_message():
    assert client.post("/api/v1/chats/messages", json={"content": ""}).status_code == 422
