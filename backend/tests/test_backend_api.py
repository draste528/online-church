from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_health():
    assert client.get("/health").json()["status"] == "ok"


def test_chat_message():
    res = client.post("/api/v1/chats/messages", json={"content": "Мир вам"})
    assert res.status_code == 200 and res.json()["reply"]


def test_chat_rejects_empty_message():
    assert client.post("/api/v1/chats/messages", json={"content": ""}).status_code == 422
