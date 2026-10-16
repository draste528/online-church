"""Chat endpoint: an AI consultant answered through OpenRouter, with an offline demo mode.

Set OPENROUTER_API_KEY (and optionally OPENROUTER_MODEL) to get real AI replies.
OPENROUTER_MODEL may list several models separated by commas: when one is overloaded or rate-limited,
the next one is tried automatically. OPENROUTER_MAX_TOKENS and OPENROUTER_REASONING tune the reply budget
(reasoning models spend part of the budget on thinking and may return no text if it is too small).
Without a key the endpoint stays usable and answers in demo mode, so the UI keeps working.
"""
import logging
import os
import time
from typing import Literal

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

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
    "ИИ-консультант не подключён (не задан ключ OPENROUTER_API_KEY)."
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


def describe_http_error(code: int) -> str:
    """Readable message for the chat window; always contains the HTTP code."""
    hints = {
        401: "Ключ OpenRouter недействителен или отозван.",
        402: "На аккаунте OpenRouter недостаточно средств для этой модели.",
        403: "Запрос отклонён: проверьте настройки приватности и ограничения ключа.",
        404: "Модель не найдена или у неё нет доступных провайдеров: проверьте название и настройки приватности.",
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
) -> str:
    """Ask OpenRouter for a reply. Every failure becomes an HTTPException with a readable message."""
    headers = {"Authorization": f"Bearer {api_key}", "X-Title": "Online Church"}
    payload = {"model": model, "messages": messages, "max_tokens": max_reply_tokens(), "temperature": 0.5}
    reasoning = reasoning_option()
    if reasoning is not None:
        payload["reasoning"] = reasoning
    started = time.perf_counter()

    def elapsed_ms() -> float:
        return (time.perf_counter() - started) * 1000

    log.debug("OpenRouter request: model=%s messages=%d", model, len(messages))
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS, transport=transport) as client:
            response = await client.post(OPENROUTER_URL, json=payload, headers=headers)
        response.raise_for_status()
        choice = response.json()["choices"][0]
        reply = choice["message"]["content"]
        finish_reason = choice.get("finish_reason")
    except httpx.TimeoutException as exc:
        log.warning("OpenRouter timed out: model=%s after %.0f ms", model, elapsed_ms())
        raise UpstreamError(
            504, "ИИ-консультант не ответил вовремя. Попробуйте ещё раз.", retryable=True
        ) from exc
    except httpx.HTTPStatusError as exc:
        code = exc.response.status_code
        log.warning(
            "OpenRouter returned HTTP %s: model=%s after %.0f ms; reason: %s",
            code, model, elapsed_ms(), parse_upstream_error(exc.response),
        )
        raise UpstreamError(
            502, describe_http_error(code), retryable=code in RETRYABLE_STATUS_CODES or code >= 500
        ) from exc
    except httpx.HTTPError as exc:
        log.warning("OpenRouter request failed: %s after %.0f ms", type(exc).__name__, elapsed_ms())
        raise UpstreamError(502, "Не удалось связаться с ИИ-сервисом.", retryable=True) from exc
    except (KeyError, IndexError, TypeError, ValueError, AttributeError) as exc:
        log.warning("OpenRouter sent an unexpected payload: %s after %.0f ms", type(exc).__name__, elapsed_ms())
        raise UpstreamError(502, "ИИ-сервис вернул неожиданный ответ.", retryable=True) from exc
    if not isinstance(reply, str) or not reply.strip():
        if finish_reason == "length":
            log.warning(
                "OpenRouter ran out of tokens before any text: model=%s max_tokens=%s after %.0f ms",
                model, payload["max_tokens"], elapsed_ms(),
            )
            raise UpstreamError(
                502,
                "Модель израсходовала лимит токенов на размышления и не успела ответить. "
                "Увеличьте OPENROUTER_MAX_TOKENS или выберите другую модель.",
                retryable=True,
            )
        log.warning("OpenRouter returned an empty reply: model=%s after %.0f ms", model, elapsed_ms())
        raise UpstreamError(502, "ИИ-сервис вернул пустой ответ.", retryable=True)
    log.info(
        "OpenRouter answered: model=%s status=%s in %.0f ms, reply %d chars",
        model, response.status_code, elapsed_ms(), len(reply),
    )
    return reply.strip()


def configured_models() -> list[str]:
    """Models from OPENROUTER_MODEL (comma-separated, tried in order); the default when it is empty."""
    models = [m.strip() for m in os.getenv("OPENROUTER_MODEL", "").split(",") if m.strip()]
    return models or [DEFAULT_MODEL]


async def request_ai_reply_with_fallback(api_key: str, models: list[str], messages: list[dict]) -> str:
    """Try the models one by one; move on only when the failure may be specific to the model."""
    for index, model in enumerate(models[:-1]):
        try:
            return await request_ai_reply(api_key, model, messages)
        except UpstreamError as exc:
            if not exc.retryable:
                raise
            log.warning("Model %s failed (HTTP %s), falling back to %s", model, exc.status_code, models[index + 1])
    return await request_ai_reply(api_key, models[-1], messages)


@router.post("/messages", response_model=ChatMessageOut)
async def send_message(message: ChatMessageIn):
    """Answer a parishioner's message. Real AI reply when a key is configured, demo reply otherwise."""
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    # Only sizes are logged, never the text of a parishioner's message.
    log.info(
        "Chat message: %d chars, %d history turns, mode=%s", len(message.content), len(message.history),
        "ai" if api_key else "demo",
    )
    if not api_key:
        return ChatMessageOut(reply=DEMO_REPLY, mode="demo")
    reply = await request_ai_reply_with_fallback(api_key, configured_models(), build_messages(message))
    return ChatMessageOut(reply=reply, mode="ai")
