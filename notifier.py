"""Port: Notifier.

A bidirectional channel for alerts. Outbound: send a message.
Inbound: stream of replies + commands from the owner.

Telegram implements both directions. Email implements outbound only
(replies() yields nothing). A CompositeNotifier fans out to several.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass

from ..domain.events import UserCommand, UserReply


@dataclass(frozen=True, slots=True)
class AlertMessage:
    text: str
    awaiting_reply: bool
    correlation_id: str  # to match replies back to the alerting episode


class Notifier(ABC):
    @abstractmethod
    async def send(self, msg: AlertMessage) -> str:
        """Send the message; return a notification id used to correlate replies."""
        ...

    @abstractmethod
    def inbound(self) -> AsyncIterator[UserReply | UserCommand]:
        """Async iterator of replies and commands from the owner."""
        ...

    @abstractmethod
    async def aclose(self) -> None: ...
