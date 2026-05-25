"""Synthetic CSI source.

Generates plausible CSI amplitude vectors with a configurable rate.
By default emits stationary noise; on demand, inject_motion() raises
the variance for a window of frames to simulate someone walking by.

Used by the dev profile and by tests.
"""

from __future__ import annotations

import asyncio
import math
import random
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

from ...domain.events import CsiFrame
from ...ports.clock import Clock
from ...ports.csi_source import CsiSource


@dataclass
class SyntheticCsiSource(CsiSource):
    """Drives at ~rate_hz, emits CsiFrames with `n_subcarriers` amplitudes.

    inject_motion() raises the per-frame jitter for `frames` frames,
    simulating someone perturbing the channel.
    """

    clock: Clock
    n_subcarriers: int = 52
    rate_hz: float = 100.0
    seed: int | None = 42

    _rng: random.Random = field(init=False)
    _baseline: list[float] = field(init=False)
    _motion_frames_remaining: int = 0
    _motion_amplitude: float = 0.0
    _closed: bool = False

    def __post_init__(self) -> None:
        self._rng = random.Random(self.seed)
        # Static channel: each subcarrier has its own steady amplitude.
        self._baseline = [
            0.5 + 0.4 * math.sin(i / self.n_subcarriers * math.pi) + self._rng.uniform(-0.05, 0.05)
            for i in range(self.n_subcarriers)
        ]

    def inject_motion(self, frames: int = 200, amplitude: float = 0.4) -> None:
        """Cause the next `frames` frames to look like motion."""
        self._motion_frames_remaining = frames
        self._motion_amplitude = amplitude

    async def stream(self) -> AsyncIterator[CsiFrame]:
        period = 1.0 / self.rate_hz
        while not self._closed:
            now = self.clock.now()
            jitter = 0.02  # ambient noise
            if self._motion_frames_remaining > 0:
                jitter += self._motion_amplitude
                self._motion_frames_remaining -= 1
            amps = tuple(
                max(0.0, b + self._rng.gauss(0.0, jitter)) for b in self._baseline
            )
            yield CsiFrame(timestamp=now, amplitudes=amps, rssi=-55)
            await self.clock.sleep(period)

    async def aclose(self) -> None:
        self._closed = True
