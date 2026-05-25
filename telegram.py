"""Telegram notifier.

Outbound: bot sendMessage with an inline keyboard ("Dismiss" / "Trigger now").
Inbound: long-polling getUpdates; maps callback_query buttons to UserReply,
and slash commands (/arm, /disarm, /snooze, /status, /panic) to UserCommand.

Setup:
  1. Talk to @BotFather on Telegram, create a bot, get TELEGRAM_BOT_TOKEN.
  2. Send any message to your bot, then visit
       https://api.telegram.org/bot<TOKEN>/getUpdates
     to find your chat id. Set TELEGRAM_CHAT_ID.
  3. The bot only responds to messages from TELEGRAM_CHAT_ID (whitelist).

Dependencies: httpx (async HTTP). Listed in pyproject.toml.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime

from ...domain.events import UserCommand, UserReply, UserResponse
from ...ports.clock import Clock
from ...ports.notifier import AlertMessage, Notifier


@dataclass
class TelegramNotifier(Notifier):
    bot_token: str
    chat_id: int
    clock: Clock
    api_base: str = "https://api.telegram.org"
    poll_timeout: int = 25

    _last_update_id: int = 0
    _closed: bool = False
    _client: object | None = field(default=None, init=False)  # httpx.AsyncClient

    async def _http(self):  # type: ignore[no-untyped-def]
        import httpx

        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.poll_timeout + 5)
        return self._client

    async def send(self, msg: AlertMessage) -> str:
        nid = f"tg-{uuid.uuid4().hex[:8]}"
        payload: dict = {"chat_id": self.chat_id, "text": msg.text}
        if msg.awaiting_reply:
            payload["reply_markup"] = json.dumps(
                {
                    "inline_keyboard": [
                        [
                            {"text": "✅ Dismiss", "callback_data": f"dismiss:{nid}"},
                            {"text": "🚨 Trigger now", "callback_data": f"confirm:{nid}"},
                        ]
                    ]
                }
            )
        client = await self._http()
        r = await client.post(f"{self.api_base}/bot{self.bot_token}/sendMessage", data=payload)
        r.raise_for_status()
        return nid

    async def inbound(self) -> AsyncIterator[UserReply | UserCommand]:
        client = await self._http()
        while not self._closed:
            try:
                r = await client.get(
                    f"{self.api_base}/bot{self.bot_token}/getUpdates",
                    params={"timeout": self.poll_timeout, "offset": self._last_update_id + 1},
                )
                r.raise_for_status()
                updates = r.json().get("result", [])
            except Exception:
                await asyncio.sleep(2)
                continue

            for u in updates:
                self._last_update_id = max(self._last_update_id, int(u["update_id"]))
                for item in self._translate(u):
                    yield item

    def _translate(self, update: dict) -> list[UserReply | UserCommand]:
        now: datetime = self.clock.now()

        # Button taps (replies to alerts).
        cb = update.get("callback_query")
        if cb:
            chat = cb.get("message", {}).get("chat", {}).get("id")
            if chat != self.chat_id:
                return []
            data = str(cb.get("data", ""))
            if ":" not in data:
                return []
            action, nid = data.split(":", 1)
            if action == "dismiss":
                return [UserReply(UserResponse.DISMISS, now, nid)]
            if action == "confirm":
                return [UserReply(UserResponse.CONFIRM, now, nid)]
            return []

        # Slash commands.
        msg = update.get("message")
        if not msg:
            return []
        chat = msg.get("chat", {}).get("id")
        if chat != self.chat_id:
            return []
        text = str(msg.get("text", "")).strip()
        if not text.startswith("/"):
            return []
        parts = text[1:].split(maxsplit=1)
        cmd = parts[0].lower().split("@", 1)[0]  # strip @botname suffix
        arg = parts[1] if len(parts) > 1 else ""

        if cmd in {"arm", "disarm", "status", "panic"}:
            return [UserCommand(kind=cmd, issued_at=now)]
        if cmd == "snooze":
            try:
                minutes = int(arg) if arg else 30
            except ValueError:
                minutes = 30
            return [UserCommand(kind="snooze", issued_at=now, payload={"minutes": minutes})]
        return []

    async def aclose(self) -> None:
        self._closed = True
        if self._client is not None:
            await self._client.aclose()  # type: ignore[attr-defined]
            self._client = None
