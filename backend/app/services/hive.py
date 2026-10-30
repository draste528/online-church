"""The Hive (OpenAI-compatible chat completions) as an optional chat provider: CHAT_PROVIDER=hive.

This module only knows how to talk to The Hive: where to send the request, how to build it and how to read
the answer. Retries across models and the readable error messages are shared with OpenRouter (see api/chat.py).

Settings (environment variables): HIVE_API_KEY, HIVE_BASE_URL, HIVE_MODEL (comma-separated list, tried in order),
HIVE_TIMEOUT_SECONDS, HIVE_MAX_TOKENS, HIVE_REASONING_EFFORT (low | medium | high; empty = not sent), HIVE_TEMPERATURE.
"""
import json
import logging
import os

import httpx

log = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://api-cdn.thehive.ai/api/v3"
DEFAULT_MODEL = "deepseek-ai/deepseek-v4.1-flash"
DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_MAX_TOKENS = 1500  # reasoning models count their hidden "thinking" tokens against it
MIN_MAX_TOKENS = 50
MAX_MAX_TOKENS = 8000
DEFAULT_TEMPERATURE = 0.4
REASONING_EFFORTS = {"low", "medium", "high"}


def _number_from_env(name: str, default: float, convert=float) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return convert(raw)
    except ValueError:
        log.warning("Ignoring invalid %s=%r", name, raw)
        return default


def hive_url() -> str:
    return f"{os.getenv('HIVE_BASE_URL', '').strip().rstrip('/') or DEFAULT_BASE_URL}/chat/completions"


def hive_timeout() -> float:
    return _number_from_env("HIVE_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS)


def hive_max_tokens() -> int:
    """Token budget of one reply (HIVE_MAX_TOKENS), clamped to a sane range."""
    return min(max(int(_number_from_env("HIVE_MAX_TOKENS", DEFAULT_MAX_TOKENS, int)), MIN_MAX_TOKENS), MAX_MAX_TOKENS)


def hive_models() -> list[str]:
    """Models from HIVE_MODEL (comma-separated, tried in order); the default when it is empty."""
    models = [m.strip() for m in os.getenv("HIVE_MODEL", "").split(",") if m.strip()]
    return models or [DEFAULT_MODEL]


def hive_headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
    }


def hive_payload(model: str, messages: list[dict]) -> dict:
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": hive_max_tokens(),
        "temperature": _number_from_env("HIVE_TEMPERATURE", DEFAULT_TEMPERATURE),
        "stream": True,  # The Hive streams SSE; the whole stream is collected and returned as one reply
    }
    effort = os.getenv("HIVE_REASONING_EFFORT", "").strip().lower()
    if effort in REASONING_EFFORTS:
        payload["reasoning_effort"] = effort
    elif effort:
        log.warning("Ignoring invalid HIVE_REASONING_EFFORT=%r", effort)
    return payload


def hive_extract(response: httpx.Response) -> tuple[str | None, str | None]:
    """(reply text, finish_reason) from a plain JSON completion or, if the server streams anyway, from SSE chunks.

    Raises ValueError / KeyError / IndexError / TypeError when the body is neither. Hidden reasoning chunks
    (`reasoning_content`) are ignored: only `content` is part of the reply.
    """
    try:
        choice = response.json()["choices"][0]
        return choice["message"]["content"], choice.get("finish_reason")
    except (ValueError, KeyError, IndexError, TypeError):
        pass

    parts: list[str] = []
    finish_reason = None
    chunks = 0
    for line in response.text.splitlines():
        line = line.strip()
        if not line.startswith("data:") or line == "data: [DONE]":
            continue
        try:
            choices = json.loads(line[5:])["choices"]
        except (ValueError, KeyError, TypeError):
            continue
        chunks += 1
        if choices:
            parts.append(choices[0].get("delta", {}).get("content") or "")
            finish_reason = choices[0].get("finish_reason") or finish_reason
    if chunks == 0:
        raise ValueError("neither a JSON completion nor an event stream")
    return "".join(parts), finish_reason
