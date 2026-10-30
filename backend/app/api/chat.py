"""Chat endpoint: an AI consultant answered through OpenRouter, with an offline demo mode.

Set OPENROUTER_API_KEY (and optionally OPENROUTER_MODEL) to get real AI replies.
OPENROUTER_MODEL may list several models separated by commas: when one is overloaded or rate-limited,
the next one is tried automatically. OPENROUTER_MAX_TOKENS and OPENROUTER_REASONING tune the reply budget
(reasoning models spend part of the budget on thinking and may return no text if it is too small).
Without a key the endpoint stays usable and answers in demo mode, so the UI keeps working.

CHAT_PROVIDER=hive switches to The Hive (HIVE_API_KEY, HIVE_MODEL, ..., see services/hive.py). The Hive goes through
the same model fallback and produces the same error messages; only the request and the answer format differ.
"""
import logging
import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from typing import Literal

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..config import CHAT_PROVIDERS, chat_provider
from ..services import hive

router = APIRouter(prefix="/api/v1/chats", tags=["Chat"])
log = logging.getLogger(__name__)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "deepseek/deepseek-chat"
REQUEST_TIMEOUT_SECONDS = 30.0
DEFAULT_MAX_REPLY_TOKENS = 1500  # reasoning models count their "thinking" tokens against this budget
MIN_REPLY_TOKENS = 50
MAX_REPLY_TOKENS_LIMIT = 8000
DEFAULT_REASONING = "low"  # off | low | medium | high | default (do not send the parameter)
MAX_HISTORY_USED = 10  # how many previous turns are sent to the model
RETRYABLE_STATUS_CODES = {400, 404, 408, 429}  # plus every 5xx: another model may still answer
ERROR_REASON_MAX_CHARS = 300

DISCLAIMER = "Разговор с ИИ-консультантом не заменяет таинство исповеди и личную беседу со священником."
DEMO_REPLY = (
    "Мир вам! Ваше сообщение получено. Сейчас включён демонстрационный режим: "
    "ИИ-консультант не подключён (не задан ключ OPENROUTER_API_KEY или HIVE_API_KEY)."
)
SYSTEM_PROMPT = (
    "Ты — ИИ-консультант православного прихода «Онлайн-Церковь». Отвечай по-русски, спокойно, доброжелательно "
    "и кратко (до 5–6 предложений). Помогай с вопросами о церковной жизни: подготовка к исповеди и причастию, "
    "посты, молитвы, церковные праздники, работа сайта. Не называй себя священником и не давай отпущения грехов: "
    "если человеку нужна исповедь или личная духовная беседа, мягко предложи прийти в храм или записаться "
    "к священнику. По медицинским, юридическим и другим нецерковным вопросам скажи, что не можешь помочь, и "
    "посоветуй обратиться к специалисту. Если человек пишет, что хочет причинить себе вред, сочувственно "
    "посоветуй срочно обратиться к близким людям или в экстренную службу."
)


class HistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class ChatMessageIn(BaseModel):
    content: str = Field(min_length=1, max_length=2000)
    history: list[HistoryMessage] = Field(default_factory=list, max_length=20)


class ChatMessageOut(BaseModel):
    reply: str
    disclaimer: str = DISCLAIMER
    mode: Literal["ai", "demo"]


class UpstreamError(HTTPException):
    """A failed OpenRouter call; `retryable` says whether another model may succeed."""

    def __init__(self, status_code: int, detail: str, *, retryable: bool = False) -> None:
        super().__init__(status_code=status_code, detail=detail)
        self.retryable = retryable


def parse_upstream_error(response: httpx.Response) -> str:
    """Short reason taken from an OpenRouter error body (the key is never part of it)."""
    try:
        error = response.json()["error"]
        message = error.get("message") or ""
        raw = (error.get("metadata") or {}).get("raw")
        if isinstance(raw, str) and raw:
            message = f"{message} | {raw}"
    except (ValueError, KeyError, AttributeError, TypeError):
        message = response.text
    return " ".join(str(message).split())[:ERROR_REASON_MAX_CHARS]


def describe_http_error(code: int, provider_name: str = "OpenRouter") -> str:
    """Readable message for the chat window; always contains the HTTP code."""
    hints = {
        401: f"Ключ {provider_name} недействителен или отозван.",
        402: f"На аккаунте {provider_name} недостаточно средств для этой модели.",
        403: "Запрос отклонён: проверьте настройки приватности и ограничения ключа.",
        404: "Модель не найдена или у неё нет доступных провайдеров: проверьте название и настройки приватности.",
        405: f"Запрос не принят: проверьте адрес API (так отвечает {provider_name} и при нулевом балансе аккаунта).",
        429: "Бесплатная модель перегружена или исчерпан лимит запросов. Подождите минуту или смените модель.",
    }
    return f"ИИ-сервис вернул ошибку (HTTP {code}). " + hints.get(code, "Попробуйте ещё раз позже.")


def max_reply_tokens() -> int:
    """Token budget of one reply (OPENROUTER_MAX_TOKENS), clamped to a sane range."""
    raw = os.getenv("OPENROUTER_MAX_TOKENS", "").strip()
    if not raw:
        return DEFAULT_MAX_REPLY_TOKENS
    try:
        return min(max(int(raw), MIN_REPLY_TOKENS), MAX_REPLY_TOKENS_LIMIT)
    except ValueError:
        log.warning("Ignoring invalid OPENROUTER_MAX_TOKENS=%r", raw)
        return DEFAULT_MAX_REPLY_TOKENS


def reasoning_option() -> dict | None:
    """OPENROUTER_REASONING -> the `reasoning` request parameter (None means: do not send it)."""
    value = os.getenv("OPENROUTER_REASONING", "").strip().lower() or DEFAULT_REASONING
    if value == "default":
        return None
    if value == "off":
        return {"enabled": False}
    if value in {"low", "medium", "high"}:
        return {"effort": value}
    log.warning("Ignoring invalid OPENROUTER_REASONING=%r", value)
    return {"effort": DEFAULT_REASONING}


@dataclass(frozen=True)
class Provider:
    """What differs between AI services; the call, the error handling and the model fallback are shared."""

    name: str  # shown in logs and in error messages
    url: Callable[[], str]
    timeout: Callable[[], float]
    headers: Callable[[str], dict[str, str]]
    payload: Callable[[str, list[dict]], dict]
    extract_reply: Callable[[httpx.Response], tuple[str | None, str | None]]  # (text, finish_reason)
    models: Callable[[], list[str]]
    max_tokens_env: str  # named in the "out of tokens" message


def _openrouter_payload(model: str, messages: list[dict]) -> dict:
    payload = {"model": model, "messages": messages, "max_tokens": max_reply_tokens(), "temperature": 0.5}
    reasoning = reasoning_option()
    if reasoning is not None:
        payload["reasoning"] = reasoning
    return payload


def _openrouter_extract_reply(response: httpx.Response) -> tuple[str | None, str | None]:
    choice = response.json()["choices"][0]
    return choice["message"]["content"], choice.get("finish_reason")


OPENROUTER = Provider(
    name="OpenRouter",
    url=lambda: OPENROUTER_URL,
    timeout=lambda: REQUEST_TIMEOUT_SECONDS,
    headers=lambda api_key: {"Authorization": f"Bearer {api_key}", "X-Title": "Online Church"},
    payload=_openrouter_payload,
    extract_reply=_openrouter_extract_reply,
    models=lambda: configured_models(),
    max_tokens_env="OPENROUTER_MAX_TOKENS",
)
HIVE = Provider(
    name="The Hive",
    url=hive.hive_url,
    timeout=hive.hive_timeout,
    headers=hive.hive_headers,
    payload=hive.hive_payload,
    extract_reply=hive.hive_extract,
    models=hive.hive_models,
    max_tokens_env="HIVE_MAX_TOKENS",
)
PROVIDERS = {"openrouter": OPENROUTER, "hive": HIVE}


def active_provider() -> Provider:
    """The provider chosen by CHAT_PROVIDER (OpenRouter by default)."""
    return PROVIDERS[chat_provider()]


def build_messages(message: ChatMessageIn) -> list[dict]:
    """System prompt + the last turns of the dialogue + the new user message."""
    history = [{"role": h.role, "content": h.content} for h in message.history[-MAX_HISTORY_USED:]]
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        *history,
        {"role": "user", "content": message.content},
    ]


async def request_ai_reply(
    api_key: str,
    model: str,
    messages: list[dict],
    *,
    transport: httpx.AsyncBaseTransport | None = None,
    provider: Provider = OPENROUTER,
) -> str:
    """Ask the AI service for a reply. Every failure becomes an HTTPException with a readable message."""
    name = provider.name
    payload = provider.payload(model, messages)
    started = time.perf_counter()

    def elapsed_ms() -> float:
        return (time.perf_counter() - started) * 1000

    log.debug("%s request: model=%s messages=%d", name, model, len(messages))
    try:
        async with httpx.AsyncClient(timeout=provider.timeout(), transport=transport) as client:
            response = await client.post(provider.url(), json=payload, headers=provider.headers(api_key))
        response.raise_for_status()
        reply, finish_reason = provider.extract_reply(response)
    except httpx.TimeoutException as exc:
        log.warning("%s timed out: model=%s after %.0f ms", name, model, elapsed_ms())
        raise UpstreamError(
            504, "ИИ-консультант не ответил вовремя. Попробуйте ещё раз.", retryable=True
        ) from exc
    except httpx.HTTPStatusError as exc:
        code = exc.response.status_code
        log.warning(
            "%s returned HTTP %s: model=%s after %.0f ms; reason: %s",
            name, code, model, elapsed_ms(), parse_upstream_error(exc.response),
        )
        raise UpstreamError(
            502, describe_http_error(code, name), retryable=code in RETRYABLE_STATUS_CODES or code >= 500
        ) from exc
    except httpx.HTTPError as exc:
        log.warning("%s request failed: %s after %.0f ms", name, type(exc).__name__, elapsed_ms())
        raise UpstreamError(502, "Не удалось связаться с ИИ-сервисом.", retryable=True) from exc
    except (KeyError, IndexError, TypeError, ValueError, AttributeError) as exc:
        log.warning("%s sent an unexpected payload: %s after %.0f ms", name, type(exc).__name__, elapsed_ms())
        raise UpstreamError(502, "ИИ-сервис вернул неожиданный ответ.", retryable=True) from exc
    if not isinstance(reply, str) or not reply.strip():
        if finish_reason == "length":
            log.warning(
                "%s ran out of tokens before any text: model=%s max_tokens=%s after %.0f ms",
                name, model, payload["max_tokens"], elapsed_ms(),
            )
            raise UpstreamError(
                502,
                "Модель израсходовала лимит токенов на размышления и не успела ответить. "
                f"Увеличьте {provider.max_tokens_env} или выберите другую модель.",
                retryable=True,
            )
        log.warning("%s returned an empty reply: model=%s after %.0f ms", name, model, elapsed_ms())
        raise UpstreamError(502, "ИИ-сервис вернул пустой ответ.", retryable=True)
    log.info(
        "%s answered: model=%s status=%s in %.0f ms, reply %d chars",
        name, model, response.status_code, elapsed_ms(), len(reply),
    )
    return reply.strip()


def configured_models() -> list[str]:
    """Models from OPENROUTER_MODEL (comma-separated, tried in order); the default when it is empty."""
    models = [m.strip() for m in os.getenv("OPENROUTER_MODEL", "").split(",") if m.strip()]
    return models or [DEFAULT_MODEL]


async def request_ai_reply_with_fallback(
    api_key: str, models: list[str], messages: list[dict], provider: Provider = OPENROUTER
) -> str:
    """Try the models one by one; move on only when the failure may be specific to the model."""
    # OpenRouter stays the default and is called exactly as before; other providers get the keyword.
    ask = request_ai_reply if provider is OPENROUTER else partial(request_ai_reply, provider=provider)
    for index, model in enumerate(models[:-1]):
        try:
            return await ask(api_key, model, messages)
        except UpstreamError as exc:
            if not exc.retryable:
                raise
            log.warning("Model %s failed (HTTP %s), falling back to %s", model, exc.status_code, models[index + 1])
    return await ask(api_key, models[-1], messages)


@router.post("/messages", response_model=ChatMessageOut)
async def send_message(message: ChatMessageIn):
    """Answer a parishioner's message. Real AI reply when a key is configured, demo reply otherwise."""
    provider = active_provider()
    api_key = os.getenv(CHAT_PROVIDERS[chat_provider()], "").strip()
    # Only sizes are logged, never the text of a parishioner's message.
    log.info(
        "Chat message: %d chars, %d history turns, mode=%s", len(message.content), len(message.history),
        "ai" if api_key else "demo",
    )
    if not api_key:
        return ChatMessageOut(reply=DEMO_REPLY, mode="demo")
    reply = await request_ai_reply_with_fallback(api_key, provider.models(), build_messages(message), provider)
    return ChatMessageOut(reply=reply, mode="ai")
