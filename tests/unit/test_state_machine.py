"""State machine unit tests — pure, no async, no IO."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from wifi_alarm.domain.events import (
    AlarmState,
    LogEvent,
    MotionEvent,
    NotifyOwner,
    SirenOff,
    SirenOn,
    UserCommand,
    UserReply,
    UserResponse,
)
from wifi_alarm.domain.state_machine import StateMachine


def at(seconds: int = 0) -> datetime:
    return datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=seconds)


def test_starts_disarmed() -> None:
    sm = StateMachine()
    assert sm.snapshot.state is AlarmState.DISARMED


def test_arm_then_motion_alerts() -> None:
    sm = StateMachine()
    sm.on_command(UserCommand("arm", at(0)))
    effects = sm.on_motion(MotionEvent(at(1), score=5.0))
    assert sm.snapshot.state is AlarmState.ALERTING
    assert any(isinstance(e, NotifyOwner) and e.awaiting_reply for e in effects)


def test_motion_while_disarmed_is_logged_but_ignored() -> None:
    sm = StateMachine()
    effects = sm.on_motion(MotionEvent(at(0), score=10.0))
    assert sm.snapshot.state is AlarmState.DISARMED
    assert all(not isinstance(e, NotifyOwner) for e in effects)
    assert any(isinstance(e, LogEvent) and e.kind == "motion_ignored" for e in effects)


def test_dismiss_reply_returns_to_armed() -> None:
    sm = StateMachine()
    sm.on_command(UserCommand("arm", at(0)))
    sm.on_motion(MotionEvent(at(1), score=5.0))
    effects = sm.on_reply(UserReply(UserResponse.DISMISS, at(2), "nid"))
    assert sm.snapshot.state is AlarmState.ARMED
    assert all(not isinstance(e, SirenOn) for e in effects)


def test_confirm_reply_triggers_siren() -> None:
    sm = StateMachine()
    sm.on_command(UserCommand("arm", at(0)))
    sm.on_motion(MotionEvent(at(1), score=5.0))
    effects = sm.on_reply(UserReply(UserResponse.CONFIRM, at(2), "nid"))
    assert sm.snapshot.state is AlarmState.TRIGGERED
    assert any(isinstance(e, SirenOn) for e in effects)


def test_timeout_auto_triggers_siren() -> None:
    sm = StateMachine(reply_timeout=timedelta(seconds=30))
    sm.on_command(UserCommand("arm", at(0)))
    sm.on_motion(MotionEvent(at(1), score=5.0))
    # Tick before timeout: no trigger.
    assert sm.on_tick(at(20)) == []
    assert sm.snapshot.state is AlarmState.ALERTING
    # Tick after timeout: trigger.
    effects = sm.on_tick(at(35))
    assert sm.snapshot.state is AlarmState.TRIGGERED
    assert any(isinstance(e, SirenOn) for e in effects)


def test_disarm_from_triggered_turns_siren_off() -> None:
    sm = StateMachine()
    sm.on_command(UserCommand("arm", at(0)))
    sm.on_motion(MotionEvent(at(1), score=5.0))
    sm.on_reply(UserReply(UserResponse.CONFIRM, at(2), "nid"))
    assert sm.snapshot.state is AlarmState.TRIGGERED
    effects = sm.on_command(UserCommand("disarm", at(3)))
    assert sm.snapshot.state is AlarmState.DISARMED
    assert any(isinstance(e, SirenOff) for e in effects)


def test_snooze_then_rearm_via_tick() -> None:
    sm = StateMachine()
    sm.on_command(UserCommand("arm", at(0)))
    sm.on_command(UserCommand("snooze", at(0), payload={"minutes": 5}))
    assert sm.snapshot.state is AlarmState.DISARMED
    # Motion during snooze is ignored.
    sm.on_motion(MotionEvent(at(60), score=10.0))
    assert sm.snapshot.state is AlarmState.DISARMED
    # Tick past snooze: re-armed.
    effects = sm.on_tick(at(5 * 60 + 1))
    assert sm.snapshot.state is AlarmState.ARMED
    assert any(isinstance(e, LogEvent) and e.kind == "snooze_expired_rearmed" for e in effects)


def test_panic_triggers_from_any_state() -> None:
    sm = StateMachine()
    # From disarmed:
    effects = sm.on_command(UserCommand("panic", at(0)))
    assert sm.snapshot.state is AlarmState.TRIGGERED
    assert any(isinstance(e, SirenOn) for e in effects)
