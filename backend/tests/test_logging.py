import asyncio
import logging
from unittest import mock

import httpx
from fastapi.testclient import TestClient

from backend.app import logging_config
from backend.app.api import chat, items
from backend.app.main import app

client = TestClient(app)


def test_response_carries_request_id():
    res = client.get("/health")
    assert len(res.headers["X-Request-ID"]) == 8


def test_request_ids_differ_between_requests():
    assert client.get("/health").headers["X-Request-ID"] != client.get("/health").headers["X-Request-ID"]


def test_request_line_has_method_path_status_and_duration(caplog):
    with caplog.at_level(logging.INFO, logger="backend"):
        client.get("/api/v1/items", params={"category": "candle"})
    line = next(r.getMessage() for r in caplog.records if r.name == "backend.app.logging_config")
    assert line.startswith("GET /api/v1/items -> 200 in ")
    assert line.endswith(" ms")
    assert "category" not in line  # query strings are not logged


def test_chat_logs_length_but_not_text(caplog):
    secret_text = "очень личное сообщение"
    with caplog.at_level(logging.DEBUG, logger="backend"):
        client.post("/api/v1/chats/messages", json={"content": secret_text})
    logged = " ".join(r.getMessage() for r in caplog.records)
    assert secret_text not in logged
    assert f"{len(secret_text)} chars" in logged
    assert "mode=demo" in logged


def test_openrouter_call_is_logged_without_the_key(caplog):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": "Мир вам"}}]})

    messages = [{"role": "user", "content": "private question"}]
    with caplog.at_level(logging.DEBUG, logger="backend"):
        asyncio.run(
            chat.request_ai_reply("sk-secret-key", "vendor/model", messages, transport=httpx.MockTransport(handler))
        )
    logged = " ".join(r.getMessage() for r in caplog.records)
    assert "vendor/model" in logged and "status=200" in logged
    assert "sk-secret-key" not in logged
    assert "private question" not in logged


def test_unhandled_error_becomes_500_with_request_id():
    with mock.patch.object(items, "ITEMS", None):  # makes the list endpoint raise TypeError
        res = TestClient(app, raise_server_exceptions=False).get("/api/v1/items")
    assert res.status_code == 500
    assert res.headers["X-Request-ID"]
    assert res.json()["detail"]


def test_unknown_log_level_falls_back_to_info():
    assert logging_config.resolve_log_level("nonsense") == (logging.INFO, False)
    assert logging_config.resolve_log_level("debug") == (logging.DEBUG, True)
    assert logging_config.resolve_log_level(None) == (logging.INFO, True)
