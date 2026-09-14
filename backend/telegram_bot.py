"""Telegram bot front-end for SIA - same agent.chat() the website uses, just
a different door in. No website account needed: a chat_id stands in for a
user_id long enough to remember which FPL team a chat is asking about
(see db.telegram_users), and every call passes user_id=None to agent.chat(),
which already handles that gracefully (skips usage logging, falls back to
a team's live squad when there's no saved draft to look up)."""

import asyncio
import os

import requests
from fastapi import APIRouter, Request

from . import agent, db

router = APIRouter(prefix="/api/telegram", tags=["telegram"])

TELEGRAM_API_BASE = "https://api.telegram.org"

WELCOME_MESSAGE = (
    "⚽ Hey, I'm SIA - your Fantasy Premier League assistant.\n\n"
    "Set your FPL team ID first:\n"
    "/setteam 1234567\n\n"
    "(Find it in your team's URL on fantasy.premierleague.com, e.g. "
    "the number in /entry/1234567/event/1)\n\n"
    "Then just ask me anything - \"who should I captain?\", \"is my transfer "
    "worth it?\", \"how's my rank?\""
)


def _bot_token() -> str | None:
    return os.environ.get("TELEGRAM_BOT_TOKEN")


def _send_message(chat_id: int, text: str) -> None:
    token = _bot_token()
    if not token:
        return
    try:
        requests.post(
            f"{TELEGRAM_API_BASE}/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=15,
        )
    except requests.RequestException:
        pass  # best-effort - Telegram will not retry a 200, nothing more to do


def _handle_message(chat_id: int, text: str) -> None:
    """Runs off the request/response cycle - agent.chat() can take 10-30+
    seconds with tool calls, well past what Telegram expects from a webhook
    before it assumes failure and retries (which would otherwise mean a
    second identical reply landing in the chat)."""
    if text.startswith("/start"):
        _send_message(chat_id, WELCOME_MESSAGE)
    elif text.startswith("/setteam"):
        parts = text.split(maxsplit=1)
        team_id = parts[1].strip() if len(parts) > 1 else ""
        if not team_id.isdigit():
            _send_message(chat_id, "That doesn't look like a team ID - it should be just numbers, e.g. /setteam 1234567")
        else:
            db.set_telegram_team_id(chat_id, team_id)
            _send_message(chat_id, f"Got it - team {team_id} saved. Ask me anything about your squad now.")
    else:
        team_id = db.get_telegram_team_id(chat_id)
        try:
            reply = agent.chat([{"role": "user", "content": text}], team_id=team_id, user_id=None)
        except Exception:
            reply = "SIA is temporarily unavailable - please try again in a moment."
        _send_message(chat_id, agent.strip_player_tags(reply))


@router.post("/webhook")
async def telegram_webhook(request: Request) -> dict:
    update = await request.json()
    message = update.get("message") or {}
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    text = (message.get("text") or "").strip()

    if chat_id and text:
        asyncio.create_task(asyncio.to_thread(_handle_message, chat_id, text))

    return {"ok": True}
