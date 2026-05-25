"""Runtime: the async tasks that drive the wired system.

Three concurrent tasks:
  - capture_loop: pulls CSI, runs the detector, hands MotionEvents to the SM.
  - inbound_loop: reads notifier replies/commands, hands them to the SM.
  - tick_loop:    drives the SM clock periodically (for reply timeout / snooze).

All three feed side-effects to dispatch(), which is the ONLY place that
calls adapters. The state machine itself stays pure.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime

from ..domain.events import (
    LogEvent,
    MotionEvent,
    NotifyOwner,
    SideEffect,
    SirenOff,
    SirenOn,
    UserCommand,
    UserReply,
)
from ..ports.notifier import AlertMessage
from .composition import Wired

log = logging.getLogger("wifi_alarm.runtime")


async def run(w: Wired, *, stop_after: float | None = None) -> None:
    """Run the wired system until cancelled or until stop_after seconds.

    stop_after is for tests and demos; production calls with None.
    """
    stop = asyncio.Event()

    async def stopper() -> None:
        if stop_after is not None:
            await asyncio.sleep(stop_after)
            stop.set()

    tasks = [
        asyncio.create_task(_capture_loop(w, stop), name="capture"),
        asyncio.create_task(_inbound_loop(w, stop), name="inbound"),
        asyncio.create_task(_tick_loop(w, stop), name="tick"),
        asyncio.create_task(stopper(), name="stopper"),
    ]
    try:
        await stop.wait()
    finally:
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await _close_all(w)


async def _capture_loop(w: Wired, stop: asyncio.Event) -> None:
    try:
        async for frame in w.csi.stream():
            if stop.is_set():
                return
            motion = w.detector.consume(frame)
            if motion is not None:
                log.info("motion detected score=%.2f", motion.score)
                effects = w.state_machine.on_motion(motion)
                await _dispatch(w, effects, at=motion.timestamp)
    except asyncio.CancelledError:
        return


async def _inbound_loop(w: Wired, stop: asyncio.Event) -> None:
    try:
        async for item in w.notifier.inbound():
            if stop.is_set():
                return
            if isinstance(item, UserReply):
                effects = w.state_machine.on_reply(item)
                await _dispatch(w, effects, at=item.received_at)
            elif isinstance(item, UserCommand):
                effects = w.state_machine.on_command(item)
                await _dispatch(w, effects, at=item.issued_at)
    except asyncio.CancelledError:
        return


async def _tick_loop(w: Wired, stop: asyncio.Event) -> None:
    try:
        while not stop.is_set():
            await w.clock.sleep(1.0)
            now = w.clock.now()
            effects = w.state_machine.on_tick(now)
            if effects:
                await _dispatch(w, effects, at=now)
    except asyncio.CancelledError:
        return


async def _dispatch(w: Wired, effects: list[SideEffect], *, at: datetime) -> None:
    for eff in effects:
        if isinstance(eff, NotifyOwner):
            msg = AlertMessage(
                text=eff.text,
                awaiting_reply=eff.awaiting_reply,
                correlation_id=uuid.uuid4().hex,
            )
            try:
                await w.notifier.send(msg)
            except Exception:
                log.exception("notifier send failed")
        elif isinstance(eff, SirenOn):
            try:
                await w.siren.on()
            except Exception:
                log.exception("siren on failed")
        elif isinstance(eff, SirenOff):
            try:
                await w.siren.off()
            except Exception:
                log.exception("siren off failed")
        elif isinstance(eff, LogEvent):
            try:
                await w.store.log(eff.kind, eff.detail, at)
            except Exception:
                log.exception("store log failed")


async def _close_all(w: Wired) -> None:
    for closeable in (w.csi, w.notifier, w.siren, w.store):
        try:
            await closeable.aclose()
        except Exception:
            log.exception("close failed for %s", type(closeable).__name__)
