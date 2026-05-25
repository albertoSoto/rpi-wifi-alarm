"""In-memory store — dev/test."""

from __future__ import annotations

from collections import deque
from datetime import datetime

from ...ports.store import Store


class MemoryStore(Store):
    def __init__(self, max_log: int = 10_000) -> None:
        self._log: deque[dict] = deque(maxlen=max_log)
        self._kv: dict[str, dict] = {}

    async def log(self, kind: str, detail: dict, at: datetime) -> None:
        self._log.append({"at": at.isoformat(), "kind": kind, "detail": detail})

    async def recent(self, limit: int = 50) -> list[dict]:
        return list(self._log)[-limit:]

    async def put(self, key: str, value: dict) -> None:
        self._kv[key] = value

    async def get(self, key: str) -> dict | None:
        return self._kv.get(key)

    async def aclose(self) -> None:
        return
