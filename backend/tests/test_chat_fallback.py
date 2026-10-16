import asyncio
import json
import os
from unittest import mock

import httpx
import pytest

from backend.app.api import chat


def run(coro):
    return asyncio.run(coro)


MESSAGES = [{"role": "user", "content": "Как поститься?"}]


def test_configured_models_splits_and_trims():
    with mock.patch.dict(os.environ, {"OPENROUTER_MODEL": " a/one:free , b/two:free ,, "}):
        assert chat.configured_models() == ["a/one:free", "b/two:free"]


def test_configured_models_default_when_empty():
    with mock.patch.dict(os.environ, {"OPENROUTER_MODEL": "  "}):
        assert chat.configured_models() == [chat.DEFAULT_MODEL]


def test_parse_upstream_error_includes_provider_message():
    body = {"error": {"message": "Provider returned error", "metadata": {"raw": "rate-limited upstream"}}}
    reason = chat.parse_upstream_error(httpx.Response(429, json=body))
    assert "Provider returned error" in reason and "rate-limited upstream" in reason


def test_parse_upstream_error_handles_non_json_and_truncates():
    assert chat.parse_upstream_error(httpx.Response(502, text="<html>bad gateway</html>")).startswith("<html>")
    assert len(chat.parse_upstream_error(httpx.Response(500, text="x" * 5000))) == chat.ERROR_REASON_MAX_CHARS


@pytest.mark.parametrize("code", [401, 402, 404, 429, 500])
def test_describe_http_error_mentions_code(code):
    assert f"HTTP {code}" in chat.describe_http_error(code)


def test_rate_limit_error_is_retryable_and_auth_error_is_not():
    def make(status):
        transport = httpx.MockTransport(lambda request: httpx.Response(status, json={"error": {"message": "x"}}))
        with pytest.raises(chat.UpstreamError) as exc_info:
            run(chat.request_ai_reply("key", "m", MESSAGES, transport=transport))
        return exc_info.value

    assert make(429).retryable is True
    assert make(503).retryable is True
    assert make(401).retryable is False
    assert make(402).retryable is False


def test_fallback_uses_next_model_after_rate_limit():
    tried = []

    async def fake_reply(api_key, model, messages):
        tried.append(model)
        if model == "first":
            raise chat.UpstreamError(502, chat.describe_http_error(429), retryable=True)
        return "ok from " + model

    with mock.patch.object(chat, "request_ai_reply", fake_reply):
        assert run(chat.request_ai_reply_with_fallback("k", ["first", "second"], MESSAGES)) == "ok from second"
    assert tried == ["first", "second"]


def test_fallback_stops_on_non_retryable_error():
    tried = []

    async def fake_reply(api_key, model, messages):
        tried.append(model)
        raise chat.UpstreamError(502, chat.describe_http_error(401), retryable=False)

    with mock.patch.object(chat, "request_ai_reply", fake_reply):
        with pytest.raises(chat.UpstreamError):
            run(chat.request_ai_reply_with_fallback("k", ["first", "second"], MESSAGES))
    assert tried == ["first"]


def test_fallback_raises_last_error_when_all_models_fail():
    async def fake_reply(api_key, model, messages):
        raise chat.UpstreamError(502, chat.describe_http_error(429), retryable=True)

    with mock.patch.object(chat, "request_ai_reply", fake_reply):
        with pytest.raises(chat.UpstreamError) as exc_info:
            run(chat.request_ai_reply_with_fallback("k", ["first", "second"], MESSAGES))
    assert "HTTP 429" in exc_info.value.detail


# ---- reply budget and reasoning models
def _capture_payload(env_values):
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(json.loads(request.content))
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}]})

    clean = {k: v for k, v in os.environ.items() if not k.startswith("OPENROUTER_")}
    with mock.patch.dict(os.environ, {**clean, **env_values}, clear=True):
        run(chat.request_ai_reply("key", "m", MESSAGES, transport=httpx.MockTransport(handler)))
    return seen


def test_default_token_budget_and_reasoning_effort():
    body = _capture_payload({})
    assert body["max_tokens"] == chat.DEFAULT_MAX_REPLY_TOKENS
    assert body["reasoning"] == {"effort": "low"}


def test_token_budget_from_env_is_clamped_and_validated():
    assert _capture_payload({"OPENROUTER_MAX_TOKENS": "3000"})["max_tokens"] == 3000
    assert _capture_payload({"OPENROUTER_MAX_TOKENS": "1"})["max_tokens"] == chat.MIN_REPLY_TOKENS
    assert _capture_payload({"OPENROUTER_MAX_TOKENS": "999999"})["max_tokens"] == chat.MAX_REPLY_TOKENS_LIMIT
    assert _capture_payload({"OPENROUTER_MAX_TOKENS": "lots"})["max_tokens"] == chat.DEFAULT_MAX_REPLY_TOKENS


def test_reasoning_modes():
    assert _capture_payload({"OPENROUTER_REASONING": "off"})["reasoning"] == {"enabled": False}
    assert _capture_payload({"OPENROUTER_REASONING": "HIGH"})["reasoning"] == {"effort": "high"}
    assert "reasoning" not in _capture_payload({"OPENROUTER_REASONING": "default"})
    assert _capture_payload({"OPENROUTER_REASONING": "nonsense"})["reasoning"] == {"effort": "low"}


def test_out_of_tokens_reasoning_model_is_retryable_with_clear_message():
    body = {"choices": [{"finish_reason": "length", "message": {"content": None, "reasoning": "thinking..."}}]}
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=body))
    with pytest.raises(chat.UpstreamError) as exc_info:
        run(chat.request_ai_reply("key", "m", MESSAGES, transport=transport))
    assert exc_info.value.retryable is True
    assert "OPENROUTER_MAX_TOKENS" in exc_info.value.detail


def test_bad_request_is_retryable_so_the_next_model_is_tried():
    transport = httpx.MockTransport(lambda request: httpx.Response(400, json={"error": {"message": "bad"}}))
    with pytest.raises(chat.UpstreamError) as exc_info:
        run(chat.request_ai_reply("key", "m", MESSAGES, transport=transport))
    assert exc_info.value.retryable is True
