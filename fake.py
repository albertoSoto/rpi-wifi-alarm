"""Fake clock for tests.

advance() bumps virtual time and wakes any pending sleeps.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from ...ports.clock import Clock


class FakeClock(Clock):
    def __init__(self, start: datetime | None = None) -> None:
        self._t = start or datetime(2026, 1, 1, tzinfo=timezone.utc)
        self._waiters: list[tuple[datetime, asyncio.Future[None]]] = []

    def now(self) -> datetime:
        return self._t

    async def sleep(self, seconds: float) -> None:
        wake_at = self._t + timedelta(seconds=seconds)
        loop = asyncio.get_running_loop()
        fut: asyncio.Future[None] = loop.create_future()
        self._waiters.append((wake_at, fut))
        await fut

    def advance(self, seconds: float) -> None:
        self._t += timedelta(seconds=seconds)
        still_pending: list[tuple[datetime, asyncio.Future[None]]] = []
        for wake_at, fut in self._waiters:
            if wake_at <= self._t and not fut.done():
                fut.set_result(None)
            else:
                still_pending.append((wake_at, fut))
        self._waiters = still_pending
