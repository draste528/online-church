"""Connectivity check for The Hive. Run from the repository root with the Hive variables exported:

    HIVE_API_KEY=... python -m backend.app.check_hive "Привет!"

Prints the effective settings (never the key), the raw HTTP answer and the parsed reply.
With --chat the real chat pipeline runs (CHAT_PROVIDER=hive, model fallback, readable errors), so you see
exactly what the site would answer:

    HIVE_API_KEY=... python -m backend.app.check_hive --chat "Как молиться?"
"""
import asyncio
import os
import sys

import httpx
from fastapi import HTTPException

from .api.chat import HIVE, ChatMessageIn, build_messages, request_ai_reply_with_fallback
from .services import hive


async def run_chat(text: str, api_key: str) -> int:
    """Same path as POST /api/v1/chats/messages with CHAT_PROVIDER=hive, without the web server."""
    messages = build_messages(ChatMessageIn(content=text))
    try:
        reply = await request_ai_reply_with_fallback(api_key, hive.hive_models(), messages, HIVE)
    except HTTPException as exc:
        print(f"FAILED, the site would show (HTTP {exc.status_code}): {exc.detail}")
        return 1
    print(f"OK: {reply}")
    return 0


async def run_raw(text: str, api_key: str) -> int:
    model = hive.hive_models()[0]
    url = hive.hive_url()
    print(f"\nPOST {url}")
    try:
        async with httpx.AsyncClient(timeout=hive.hive_timeout()) as http:
            payload = hive.hive_payload(model, [{"role": "user", "content": text}])
            response = await http.post(url, json=payload, headers=hive.hive_headers(api_key))
    except httpx.HTTPError as exc:
        print(f"Request failed: {type(exc).__name__}")
        return 1
    print(f"HTTP {response.status_code}  content-type: {response.headers.get('content-type')}")
    print("--- raw body (first 800 chars) ---")
    print(response.text[:800])
    print("--- parsed reply ---")
    try:
        reply = (hive.hive_extract(response)[0] or "").strip() if response.status_code == 200 else ""
    except (ValueError, KeyError, IndexError, TypeError):
        reply = ""
    print(reply or "(no text)")
    return 0 if reply else 1


async def main(args: list[str]) -> int:
    api_key = os.getenv("HIVE_API_KEY", "").strip()
    print(f"url      : {hive.hive_url()}")
    print(f"models   : {', '.join(hive.hive_models())}")
    print(f"max_tokens: {hive.hive_max_tokens()}")
    print(f"key      : {'set (' + str(len(api_key)) + ' chars)' if api_key else 'NOT SET'}")
    if not api_key:
        print("\nExport HIVE_API_KEY and run again.")
        return 1
    if args and args[0] == "--chat":
        return await run_chat(" ".join(args[1:]) or "Привет! Как молиться?", api_key)
    return await run_raw(" ".join(args) or "Привет! Ответь одним предложением.", api_key)


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
