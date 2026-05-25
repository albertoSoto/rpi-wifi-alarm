"""SQLite store — durable event log + kv on the Pi.

Schema:
  events(id INTEGER PK, at TEXT, kind TEXT, detail TEXT)
  kv(key TEXT PK, value TEXT)

Uses aiosqlite for non-blocking IO.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime

from ...ports.store import Store


@dataclass
class SqliteStore(Store):
    path: str
    _db: object | None = None  # aiosqlite.Connection

    async def _open(self):  # type: ignore[no-untyped-def]
        import aiosqlite

        if self._db is None:
            self._db = await aiosqlite.connect(self.path)
            await self._db.executescript(  # type: ignore[attr-defined]
                """
                CREATE TABLE IF NOT EXISTS events(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    at TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    detail TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS kv(
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_events_at ON events(at);
                """
            )
            await self._db.commit()  # type: ignore[attr-defined]
        return self._db

    async def log(self, kind: str, detail: dict, at: datetime) -> None:
        db = await self._open()
        await db.execute(  # type: ignore[attr-defined]
            "INSERT INTO events(at, kind, detail) VALUES (?, ?, ?)",
            (at.isoformat(), kind, json.dumps(detail)),
        )
        await db.commit()  # type: ignore[attr-defined]

    async def recent(self, limit: int = 50) -> list[dict]:
        db = await self._open()
        cur = await db.execute(  # type: ignore[attr-defined]
            "SELECT at, kind, detail FROM events ORDER BY id DESC LIMIT ?", (limit,)
        )
        rows = await cur.fetchall()
        await cur.close()
        return [{"at": r[0], "kind": r[1], "detail": json.loads(r[2])} for r in reversed(rows)]

    async def put(self, key: str, value: dict) -> None:
        db = await self._open()
        await db.execute(  # type: ignore[attr-defined]
            "INSERT INTO kv(key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, json.dumps(value)),
        )
        await db.commit()  # type: ignore[attr-defined]

    async def get(self, key: str) -> dict | None:
        db = await self._open()
        cur = await db.execute("SELECT value FROM kv WHERE key=?", (key,))  # type: ignore[attr-defined]
        row = await cur.fetchone()
        await cur.close()
        return json.loads(row[0]) if row else None

    async def aclose(self) -> None:
        if self._db is not None:
            await self._db.close()  # type: ignore[attr-defined]
            self._db = None
