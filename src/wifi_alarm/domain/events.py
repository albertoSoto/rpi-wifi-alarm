"""Domain events.

These types flow between the detector, state machine, and adapters.
Pure data; no IO, no behaviour.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class AlarmState(str, Enum):
    """The alarm's current state."""

    DISARMED = "disarmed"
    ARMED = "armed"
    ALERTING = "alerting"
    TRIGGERED = "triggered"


class UserResponse(str, Enum):
    """What the owner replied with from a notification."""

    DISMISS = "dismiss"  # "I'm home, false alarm"
    CONFIRM = "confirm"  # "Yes, trigger the siren now"


@dataclass(frozen=True, slots=True)
class CsiFrame:
    """One CSI measurement.

    Amplitudes are per-subcarrier magnitudes; we don't need phase
    for the variance-based presence detector. Adapters that produce
    phase as well can attach it later.
    """

    timestamp: datetime
    amplitudes: tuple[float, ...]  # per subcarrier
    rssi: int | None = None


@dataclass(frozen=True, slots=True)
class MotionEvent:
    """The detector said something moved."""

    timestamp: datetime
    score: float  # how strong (variance ratio vs baseline)


@dataclass(frozen=True, slots=True)
class UserCommand:
    """Something the owner asked the system to do."""

    kind: str  # "arm" | "disarm" | "snooze" | "status" | "panic"
    issued_at: datetime
    payload: dict = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class UserReply:
    """A reply to an outstanding alert notification."""

    response: UserResponse
    received_at: datetime
    notification_id: str


# Commands the state machine emits for adapters to execute.
# Kept as simple tagged dataclasses for explicit pattern matching.


@dataclass(frozen=True, slots=True)
class NotifyOwner:
    text: str
    awaiting_reply: bool


@dataclass(frozen=True, slots=True)
class SirenOn:
    pass


@dataclass(frozen=True, slots=True)
class SirenOff:
    pass


@dataclass(frozen=True, slots=True)
class LogEvent:
    """Append a record to persistent state."""

    kind: str
    detail: dict


SideEffect = NotifyOwner | SirenOn | SirenOff | LogEvent
