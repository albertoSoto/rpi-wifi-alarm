"""System clock — real wall time."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from ...ports.clock import Clock


class SystemClock(Clock):
    def now(self) -> datetime:
        return datetime.now(tz=timezone.utc)

    async def sleep(self, seconds: float) -> None:
        await asyncio.sleep(seconds)
