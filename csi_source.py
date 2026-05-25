"""Port: CSI source.

Anything that yields CsiFrames. Real impl: nexmon UDP listener.
Dev impl: synthetic generator. Test impl: replay from a file.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from ..domain.events import CsiFrame


class CsiSource(ABC):
    """Async-iterable source of CSI frames."""

    @abstractmethod
    def stream(self) -> AsyncIterator[CsiFrame]:
        """Return an async iterator yielding frames as they arrive.

        Must be safe to call once per process; the iterator owns any
        backing resources and releases them on aclose().
        """
        ...

    @abstractmethod
    async def aclose(self) -> None:
        """Release any resources (sockets, files, tasks)."""
        ...
