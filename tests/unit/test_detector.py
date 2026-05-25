"""Detector unit tests."""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from wifi_alarm.domain.detector import VarianceDetector
from wifi_alarm.domain.events import CsiFrame


def make_frame(amps: list[float], t: float) -> CsiFrame:
    ts = datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=t)
    return CsiFrame(timestamp=ts, amplitudes=tuple(amps), rssi=-50)


def test_calibration_phase_silent() -> None:
    det = VarianceDetector(window_size=20, calibration_frames=50, threshold_multiplier=3.0)
    rng = random.Random(0)
    for i in range(50):
        amps = [0.5 + rng.gauss(0, 0.01) for _ in range(8)]
        assert det.consume(make_frame(amps, i * 0.01)) is None
    assert det.calibrated


def test_motion_triggers_after_calibration() -> None:
    det = VarianceDetector(
        window_size=20,
        calibration_frames=200,
        threshold_multiplier=3.0,
        refractory=timedelta(milliseconds=10),
    )
    rng = random.Random(0)
    # Calibrate on quiet noise.
    for i in range(300):
        amps = [0.5 + rng.gauss(0, 0.01) for _ in range(8)]
        det.consume(make_frame(amps, i * 0.01))
    assert det.calibrated

    # Inject loud frames.
    triggered = False
    for i in range(60):
        amps = [0.5 + rng.gauss(0, 0.3) for _ in range(8)]
        ev = det.consume(make_frame(amps, 3.0 + i * 0.01))
        if ev is not None:
            triggered = True
            assert ev.score > 3.0
            break
    assert triggered, "detector should have fired on loud frames"


def test_quiet_after_calibration_does_not_trigger() -> None:
    det = VarianceDetector(window_size=20, calibration_frames=100, threshold_multiplier=3.0)
    rng = random.Random(0)
    for i in range(400):
        amps = [0.5 + rng.gauss(0, 0.01) for _ in range(8)]
        ev = det.consume(make_frame(amps, i * 0.01))
        assert ev is None
