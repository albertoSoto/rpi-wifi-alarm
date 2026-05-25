"""Port: Clock.

Abstracted time source. Tests use a fake clock to advance time
deterministically (no sleeps).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime


class Clock(ABC):
    @abstractmethod
    def now(self) -> datetime: ...

    @abstractmethod
    async def sleep(self, seconds: float) -> None: ...
