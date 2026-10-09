"""Chat endpoint: an AI consultant answered through OpenRouter, with an offline demo mode.

Set OPENROUTER_API_KEY (and optionally OPENROUTER_MODEL) to get real AI replies.
Without a key the endpoint stays usable and answers in demo mode, so the UI keeps working.
"""
import logging
import os
from typing import Literal

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/v1/chats", tags=["Chat"])
log = logging.getLogger(__name__)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "deepseek/deepseek-chat"
REQUEST_TIMEOUT_SECONDS = 30.0
MAX_REPLY_TOKENS = 500
MAX_HISTORY_USED = 10  # how many previous turns are sent to the model

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
    payload = {"model": model, "messages": messages, "max_tokens": MAX_REPLY_TOKENS, "temperature": 0.5}
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS, transport=transport) as client:
            response = await client.post(OPENROUTER_URL, json=payload, headers=headers)
        response.raise_for_status()
        reply = response.json()["choices"][0]["message"]["content"]
    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=504, detail="ИИ-консультант не ответил вовремя. Попробуйте ещё раз.") from exc
    except httpx.HTTPStatusError as exc:
        code = exc.response.status_code
        log.warning("OpenRouter returned HTTP %s", code)
        raise HTTPException(
            status_code=502, detail=f"ИИ-сервис вернул ошибку (HTTP {code}). Проверьте ключ и название модели."
        ) from exc
    except httpx.HTTPError as exc:
        log.warning("OpenRouter request failed: %s", type(exc).__name__)
        raise HTTPException(status_code=502, detail="Не удалось связаться с ИИ-сервисом.") from exc
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=502, detail="ИИ-сервис вернул неожиданный ответ.") from exc
    if not isinstance(reply, str) or not reply.strip():
        raise HTTPException(status_code=502, detail="ИИ-сервис вернул пустой ответ.")
    return reply.strip()


@router.post("/messages", response_model=ChatMessageOut)
async def send_message(message: ChatMessageIn):
    """Answer a parishioner's message. Real AI reply when a key is configured, demo reply otherwise."""
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        return ChatMessageOut(reply=DEMO_REPLY, mode="demo")
    model = os.getenv("OPENROUTER_MODEL", "").strip() or DEFAULT_MODEL
    reply = await request_ai_reply(api_key, model, build_messages(message))
    return ChatMessageOut(reply=reply, mode="ai")
