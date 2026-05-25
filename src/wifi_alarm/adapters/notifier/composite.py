"""Composite notifier — fan-out send, merge inbound.

Wraps several notifiers. Sending broadcasts to all of them (gathering
the first non-empty id). Inbound merges all of their reply streams.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass

from ...domain.events import UserCommand, UserReply
from ...ports.notifier import AlertMessage, Notifier


@dataclass
class CompositeNotifier(Notifier):
    members: list[Notifier]

    async def send(self, msg: AlertMessage) -> str:
        results = await asyncio.gather(
            *(m.send(msg) for m in self.members), return_exceptions=True
        )
        # Prefer the first successful id; log failures.
        for r in results:
            if isinstance(r, str):
                return r
        raise RuntimeError(f"all notifiers failed: {results}")

    async def inbound(self) -> AsyncIterator[UserReply | UserCommand]:
        queue: asyncio.Queue[UserReply | UserCommand] = asyncio.Queue()

        async def pump(notifier: Notifier) -> None:
            async for item in notifier.inbound():
                await queue.put(item)

        tasks = [asyncio.create_task(pump(m)) for m in self.members]
        try:
            while True:
                item = await queue.get()
                yield item
        finally:
            for t in tasks:
                t.cancel()

    async def aclose(self) -> None:
        await asyncio.gather(*(m.aclose() for m in self.members), return_exceptions=True)
