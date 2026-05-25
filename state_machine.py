"""Alarm state machine.

Pure transition function: (state, event, now) -> (new_state, side_effects).
No IO, no clocks of its own — the caller passes `now`. Trivial to unit-test.

State transitions:

    DISARMED   --arm-->         ARMED
    ARMED      --motion-->      ALERTING (start timer, notify owner)
    ALERTING   --reply dismiss--> ARMED
    ALERTING   --reply confirm-->TRIGGERED (siren on)
    ALERTING   --timeout-->     TRIGGERED (siren on)
    ALERTING   --disarm-->      DISARMED
    TRIGGERED  --disarm-->      DISARMED (siren off)
    *          --panic-->       TRIGGERED (siren on)
    *          --snooze N-->    DISARMED for N minutes, then ARMED
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta

from .events import (
    AlarmState,
    LogEvent,
    MotionEvent,
    NotifyOwner,
    SideEffect,
    SirenOff,
    SirenOn,
    UserCommand,
    UserReply,
    UserResponse,
)


@dataclass(frozen=True, slots=True)
class StateSnapshot:
    """Immutable view of the state machine at a moment in time."""

    state: AlarmState = AlarmState.DISARMED
    alerting_since: datetime | None = None
    snooze_until: datetime | None = None
    last_motion_score: float = 0.0
    pending_notification_id: str | None = None


@dataclass(slots=True)
class StateMachine:
    """Mutable wrapper holding a StateSnapshot and applying transitions."""

    reply_timeout: timedelta = timedelta(seconds=60)
    snapshot: StateSnapshot = field(default_factory=StateSnapshot)

    # ── transitions ───────────────────────────────────────────────────────

    def on_motion(self, event: MotionEvent) -> list[SideEffect]:
        s = self.snapshot
        # If snoozed and the snooze elapsed, auto-rearm.
        if s.snooze_until and event.timestamp >= s.snooze_until:
            self.snapshot = replace(s, state=AlarmState.ARMED, snooze_until=None)
            s = self.snapshot

        if s.state is not AlarmState.ARMED:
            return [LogEvent("motion_ignored", {"state": s.state.value, "score": event.score})]

        self.snapshot = replace(
            s,
            state=AlarmState.ALERTING,
            alerting_since=event.timestamp,
            last_motion_score=event.score,
        )
        text = (
            f"⚠️ Motion detected (score {event.score:.2f}). "
            "Reply 'dismiss' if it's you, 'confirm' to trigger the siren now. "
            f"Auto-trigger in {int(self.reply_timeout.total_seconds())}s."
        )
        return [
            LogEvent("alerting", {"score": event.score}),
            NotifyOwner(text=text, awaiting_reply=True),
        ]

    def on_reply(self, reply: UserReply) -> list[SideEffect]:
        s = self.snapshot
        if s.state is not AlarmState.ALERTING:
            return [LogEvent("reply_ignored", {"state": s.state.value})]

        if reply.response is UserResponse.DISMISS:
            self.snapshot = replace(s, state=AlarmState.ARMED, alerting_since=None)
            return [LogEvent("dismissed", {})]

        # CONFIRM
        self.snapshot = replace(s, state=AlarmState.TRIGGERED, alerting_since=None)
        return [LogEvent("triggered_by_owner", {}), SirenOn()]

    def on_tick(self, now: datetime) -> list[SideEffect]:
        """Time-based check. Caller drives this periodically."""
        s = self.snapshot
        effects: list[SideEffect] = []

        # Snooze expired? Re-arm.
        if s.state is AlarmState.DISARMED and s.snooze_until and now >= s.snooze_until:
            self.snapshot = replace(s, state=AlarmState.ARMED, snooze_until=None)
            effects.append(LogEvent("snooze_expired_rearmed", {}))
            return effects

        # Reply timeout while alerting? Auto-trigger.
        if (
            s.state is AlarmState.ALERTING
            and s.alerting_since is not None
            and now - s.alerting_since >= self.reply_timeout
        ):
            self.snapshot = replace(s, state=AlarmState.TRIGGERED, alerting_since=None)
            effects.append(LogEvent("triggered_by_timeout", {}))
            effects.append(SirenOn())

        return effects

    def on_command(self, cmd: UserCommand) -> list[SideEffect]:
        s = self.snapshot

        if cmd.kind == "arm":
            self.snapshot = replace(s, state=AlarmState.ARMED, snooze_until=None)
            return [LogEvent("armed", {})]

        if cmd.kind == "disarm":
            effects: list[SideEffect] = [LogEvent("disarmed", {})]
            if s.state is AlarmState.TRIGGERED:
                effects.append(SirenOff())
            self.snapshot = replace(
                s, state=AlarmState.DISARMED, alerting_since=None, snooze_until=None
            )
            return effects

        if cmd.kind == "snooze":
            minutes = int(cmd.payload.get("minutes", 30))
            until = cmd.issued_at + timedelta(minutes=minutes)
            self.snapshot = replace(s, state=AlarmState.DISARMED, snooze_until=until)
            return [LogEvent("snoozed", {"until": until.isoformat()})]

        if cmd.kind == "panic":
            self.snapshot = replace(s, state=AlarmState.TRIGGERED, alerting_since=None)
            return [LogEvent("panic", {}), SirenOn()]

        if cmd.kind == "status":
            return [LogEvent("status_requested", {"state": s.state.value})]

        return [LogEvent("unknown_command", {"kind": cmd.kind})]
