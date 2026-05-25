"""Console notifier — dev/test only.

Prints outbound alerts to stdout. Inbound replies are pushed onto an
asyncio.Queue by tests or by a tiny REPL helper.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

from ...domain.events import UserCommand, UserReply
from ...ports.notifier import AlertMessage, Notifier


@dataclass
class ConsoleNotifier(Notifier):
    _inbound: asyncio.Queue[UserReply | UserCommand] = field(default_factory=asyncio.Queue)
    _closed: bool = False

    async def send(self, msg: AlertMessage) -> str:
        nid = f"console-{uuid.uuid4().hex[:8]}"
        marker = "🔔 ALERT" if msg.awaiting_reply else "ℹ️  INFO"
        print(f"{marker} [{nid}] {msg.text}", flush=True)
        return nid

    async def push(self, item: UserReply | UserCommand) -> None:
        """Test helper: inject a reply or command into the inbound stream."""
        await self._inbound.put(item)

    async def inbound(self) -> AsyncIterator[UserReply | UserCommand]:
        while not self._closed:
            try:
                item = await asyncio.wait_for(self._inbound.get(), timeout=0.1)
            except asyncio.TimeoutError:
                continue
            yield item

    async def aclose(self) -> None:
        self._closed = True
