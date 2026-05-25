"""End-to-end integration test.

Wires the dev profile with a FakeClock so we can advance time
deterministically and observe the whole flow:
  arm → synthetic motion injected → notifier sent → confirm reply →
  siren on.
"""

from __future__ import annotations

import asyncio
from datetime import timedelta

import pytest

from wifi_alarm.adapters.clock.fake import FakeClock
from wifi_alarm.adapters.csi.synthetic import SyntheticCsiSource
from wifi_alarm.adapters.notifier.console import ConsoleNotifier
from wifi_alarm.adapters.siren.mock import MockSiren
from wifi_alarm.adapters.store.memory import MemoryStore
from wifi_alarm.app.composition import Wired
from wifi_alarm.app.config import AlarmConfig
from wifi_alarm.app.runtime import run
from wifi_alarm.domain.detector import VarianceDetector
from wifi_alarm.domain.events import UserCommand, UserReply, UserResponse
from wifi_alarm.domain.state_machine import StateMachine


def _wire_with_fakes() -> tuple[Wired, FakeClock, ConsoleNotifier, MockSiren, SyntheticCsiSource]:
    """Build a Wired graph entirely from fakes, with hooks we can poke."""
    clock = FakeClock()
    csi = SyntheticCsiSource(clock=clock, n_subcarriers=16, rate_hz=200.0, seed=1)
    notifier = ConsoleNotifier()
    siren = MockSiren()
    store = MemoryStore()
    detector = VarianceDetector(
        window_size=20,
        calibration_frames=100,
        threshold_multiplier=3.0,
        refractory=timedelta(seconds=0),
    )
    sm = StateMachine(reply_timeout=timedelta(seconds=30))
    cfg = AlarmConfig(
        profile="dev",
        reply_timeout_s=30,
        detector_window=20,
        detector_calibration_frames=100,
        detector_threshold_mult=3.0,
        siren_gpio_pin=17,
        siren_active_high=False,
        nexmon_udp_port=5500,
        nexmon_n_subcarriers=64,
        sqlite_path=":memory:",
        telegram=None,
        email=None,
    )
    wired = Wired(
        config=cfg,
        clock=clock,
        csi=csi,
        notifier=notifier,
        siren=siren,
        store=store,
        detector=detector,
        state_machine=sm,
    )
    return wired, clock, notifier, siren, csi


@pytest.mark.asyncio
async def test_full_flow_motion_to_siren_via_confirm() -> None:
    wired, clock, notifier, siren, csi = _wire_with_fakes()

    async def drive_clock() -> None:
        # Advance time in 10ms steps so the synthetic source's sleeps fire.
        for _ in range(2000):
            await asyncio.sleep(0)  # let other tasks run
            clock.advance(0.005)
            await asyncio.sleep(0)

    async def script() -> None:
        # Arm the system.
        await notifier.push(UserCommand("arm", clock.now()))
        # Give the capture loop a tick to calibrate.
        await asyncio.sleep(0)
        # Force motion in the synthetic source after a moment.
        await asyncio.sleep(0.05)
        csi.inject_motion(frames=400, amplitude=0.5)
        # Wait long enough for detector to fire and SM to alert.
        await asyncio.sleep(0.3)
        # Confirm the alert.
        await notifier.push(UserReply(UserResponse.CONFIRM, clock.now(), "any"))
        await asyncio.sleep(0.2)

    runner = asyncio.create_task(run(wired, stop_after=2.0))
    driver = asyncio.create_task(drive_clock())
    scripter = asyncio.create_task(script())
    await asyncio.wait_for(runner, timeout=3.0)
    driver.cancel()
    scripter.cancel()
    await asyncio.gather(driver, scripter, return_exceptions=True)

    assert "on" in siren.log, f"siren should have been ON at some point; log={siren.log}"


@pytest.mark.asyncio
async def test_dismiss_keeps_siren_silent() -> None:
    wired, clock, notifier, siren, csi = _wire_with_fakes()

    async def drive_clock() -> None:
        for _ in range(2000):
            await asyncio.sleep(0)
            clock.advance(0.005)
            await asyncio.sleep(0)

    async def script() -> None:
        await notifier.push(UserCommand("arm", clock.now()))
        await asyncio.sleep(0.05)
        csi.inject_motion(frames=400, amplitude=0.5)
        await asyncio.sleep(0.3)
        await notifier.push(UserReply(UserResponse.DISMISS, clock.now(), "any"))
        await asyncio.sleep(0.2)

    runner = asyncio.create_task(run(wired, stop_after=2.0))
    driver = asyncio.create_task(drive_clock())
    scripter = asyncio.create_task(script())
    await asyncio.wait_for(runner, timeout=3.0)
    driver.cancel()
    scripter.cancel()
    await asyncio.gather(driver, scripter, return_exceptions=True)

    assert not siren.is_on
    assert "on" not in siren.log
