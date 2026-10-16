import asyncio
import json
import os
from unittest import mock

import httpx
import pytest
from fastapi import HTTPException

from backend.app import config
from backend.app.api import chat
from backend.app.services import hive

MESSAGES = [{"role": "user", "content": "Как молиться?"}]

SSE_REPLY = (
    'data: {"choices":[{"delta":{"role":"assistant","reasoning_content":"We need to answer in Russian"}}]}\n\n'
    'data: {"choices":[{"delta":{"content":"Мир "}}]}\n\n'
    'data: {"choices":[{"delta":{"content":"вам!"},"finish_reason":"stop"}]}\n\n'
    'data: {"choices":[],"usage":{"total_tokens":42}}\n\n'
    "data: [DONE]\n\n"
)


def run(coro):
    return asyncio.run(coro)


def hive_env(**values):
    """A clean Hive-related environment with the given overrides."""
    clean = {k: v for k, v in os.environ.items() if not k.startswith(("HIVE_", "OPENROUTER_", "CHAT_PROVIDER"))}
    return mock.patch.dict(os.environ, {**clean, **values}, clear=True)


def ask_hive(handler, model="vendor/model"):
    return chat.request_ai_reply("key", model, MESSAGES, transport=httpx.MockTransport(handler), provider=chat.HIVE)


def test_provider_defaults_to_openrouter_and_ignores_unknown_values():
    with hive_env():
        assert config.chat_provider() == "openrouter" and chat.active_provider() is chat.OPENROUTER
    with hive_env(CHAT_PROVIDER="skynet"):
        assert config.chat_provider() == "openrouter"
    with hive_env(CHAT_PROVIDER=" Hive "):
        assert chat.active_provider() is chat.HIVE


def test_chat_mode_looks_at_the_key_of_the_selected_provider():
    with hive_env(OPENROUTER_API_KEY="or-key"):
        assert config.chat_mode() == "ai"
    with hive_env(OPENROUTER_API_KEY="or-key", CHAT_PROVIDER="hive"):
        assert config.chat_mode() == "demo"
    with hive_env(HIVE_API_KEY="hive-key", CHAT_PROVIDER="hive"):
        assert config.chat_mode() == "ai"


def test_hive_request_has_key_model_and_streaming_flag():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(auth=request.headers["authorization"], url=str(request.url), body=json.loads(request.content))
        return httpx.Response(200, text=SSE_REPLY)

    with hive_env(HIVE_MAX_TOKENS="123", HIVE_REASONING_EFFORT="low"):
        assert run(ask_hive(handler)) == "Мир вам!"
    assert seen["auth"] == "Bearer key"
    assert seen["url"] == "https://api-cdn.thehive.ai/api/v3/chat/completions"
    assert seen["body"]["model"] == "vendor/model" and seen["body"]["messages"] == MESSAGES
    assert seen["body"]["max_tokens"] == 123 and seen["body"]["stream"] is True
    assert seen["body"]["reasoning_effort"] == "low"


def test_hive_reasoning_effort_is_not_sent_by_default():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(body=json.loads(request.content))
        return httpx.Response(200, json={"choices": [{"message": {"content": " Мир вам "}}]})

    with hive_env():
        assert run(ask_hive(handler)) == "Мир вам"
    assert "reasoning_effort" not in seen["body"] and seen["body"]["max_tokens"] == hive.DEFAULT_MAX_TOKENS


def test_hive_token_budget_is_clamped_and_validated():
    with hive_env(HIVE_MAX_TOKENS="1"):
        assert hive.hive_max_tokens() == hive.MIN_MAX_TOKENS
    with hive_env(HIVE_MAX_TOKENS="999999"):
        assert hive.hive_max_tokens() == hive.MAX_MAX_TOKENS
    with hive_env(HIVE_MAX_TOKENS="lots"):
        assert hive.hive_max_tokens() == hive.DEFAULT_MAX_TOKENS


def test_hive_models_are_split_and_default_when_empty():
    with hive_env(HIVE_MODEL=" a/one , b/two ,, "):
        assert hive.hive_models() == ["a/one", "b/two"]
    with hive_env():
        assert hive.hive_models() == [hive.DEFAULT_MODEL]


@pytest.mark.parametrize("status", [401, 402, 405, 429, 500])
def test_hive_http_errors_share_the_openrouter_messages(status):
    with hive_env(), pytest.raises(HTTPException) as exc_info:
        run(ask_hive(lambda request: httpx.Response(status, json={"error": "nope"})))
    assert exc_info.value.status_code == 502
    assert f"HTTP {status}" in exc_info.value.detail and "ИИ-сервис вернул ошибку" in exc_info.value.detail


def test_hive_empty_stream_with_only_reasoning_is_an_empty_reply():
    sse = 'data: {"choices":[{"delta":{"reasoning_content":"thinking..."}}]}\n\ndata: [DONE]\n\n'
    with hive_env(), pytest.raises(HTTPException) as exc_info:
        run(ask_hive(lambda request: httpx.Response(200, text=sse)))
    assert exc_info.value.status_code == 502 and "пустой ответ" in exc_info.value.detail


def test_hive_out_of_tokens_names_the_hive_variable():
    sse = 'data: {"choices":[{"delta":{"reasoning_content":"x"},"finish_reason":"length"}]}\n\n'
    with hive_env(), pytest.raises(HTTPException) as exc_info:
        run(ask_hive(lambda request: httpx.Response(200, text=sse)))
    assert "HIVE_MAX_TOKENS" in exc_info.value.detail


def test_hive_garbage_body_is_an_unexpected_payload():
    with hive_env(), pytest.raises(HTTPException) as exc_info:
        run(ask_hive(lambda request: httpx.Response(200, text="<html>oops</html>")))
    assert exc_info.value.status_code == 502 and "неожиданный" in exc_info.value.detail


def test_hive_uses_the_same_model_fallback():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        model = json.loads(request.content)["model"]
        seen.append(model)
        if model == "first":
            return httpx.Response(429, json={"error": {"message": "slow down"}})
        return httpx.Response(200, text=SSE_REPLY)

    real_client = httpx.AsyncClient

    def client_with_mock(*args, **kwargs):
        return real_client(*args, **{**kwargs, "transport": httpx.MockTransport(handler)})

    with hive_env(), mock.patch.object(chat.httpx, "AsyncClient", client_with_mock):
        reply = run(chat.request_ai_reply_with_fallback("k", ["first", "second"], MESSAGES, chat.HIVE))
    assert reply == "Мир вам!" and seen == ["first", "second"]


def test_send_message_uses_hive_when_selected():
    calls = {}

    async def fake_reply(api_key, model, messages, *, provider):
        calls.update(api_key=api_key, model=model, provider=provider)
        return "Ответ Hive"

    with hive_env(CHAT_PROVIDER="hive", HIVE_API_KEY="h1", HIVE_MODEL="vendor/hive"):
        with mock.patch.object(chat, "request_ai_reply", fake_reply):
            result = run(chat.send_message(chat.ChatMessageIn(content="Вопрос")))
    assert result.mode == "ai" and result.reply == "Ответ Hive"
    assert calls == {"api_key": "h1", "model": "vendor/hive", "provider": chat.HIVE}


def test_send_message_with_hive_but_no_hive_key_uses_demo_mode():
    with hive_env(CHAT_PROVIDER="hive", OPENROUTER_API_KEY="only-for-openrouter"):
        result = run(chat.send_message(chat.ChatMessageIn(content="Вопрос")))
    assert result.mode == "demo" and result.reply == chat.DEMO_REPLY
