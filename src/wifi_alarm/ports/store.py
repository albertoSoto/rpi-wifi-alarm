"""Port: Store.

Append-only event log plus key/value for things like the saved
calibration baseline. Real impl: SQLite. Dev/test impl: in-memory.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime


class Store(ABC):
    @abstractmethod
    async def log(self, kind: str, detail: dict, at: datetime) -> None: ...

    @abstractmethod
    async def recent(self, limit: int = 50) -> list[dict]: ...

    @abstractmethod
    async def put(self, key: str, value: dict) -> None: ...

    @abstractmethod
    async def get(self, key: str) -> dict | None: ...

    @abstractmethod
    async def aclose(self) -> None: ...
