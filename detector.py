"""Variance-based motion detector.

The core observation: when nothing in the environment is moving, the
per-subcarrier CSI amplitudes are stable. When a body moves through
the channel, multipath reflections shift and amplitudes wobble.

We track a rolling baseline of per-subcarrier variance during a
calibration phase, then watch for the live variance to exceed
`baseline * threshold_multiplier`. The detector emits at most one
MotionEvent per `refractory` interval to avoid spamming.

Pure: no IO, no clock of its own. Caller passes timestamps via frames.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from statistics import mean

from .events import CsiFrame, MotionEvent


@dataclass(slots=True)
class _Welford:
    """Running mean/variance via Welford's online algorithm."""

    n: int = 0
    mean: float = 0.0
    m2: float = 0.0

    def push(self, x: float) -> None:
        self.n += 1
        delta = x - self.mean
        self.mean += delta / self.n
        self.m2 += delta * (x - self.mean)

    @property
    def variance(self) -> float:
        return self.m2 / self.n if self.n > 1 else 0.0


@dataclass(slots=True)
class VarianceDetector:
    """Rolling-window variance detector with calibration phase.

    Parameters
    ----------
    window_size
        Number of recent frames to compute live variance over.
    calibration_frames
        Frames consumed during calibration to establish the baseline.
    threshold_multiplier
        Trigger when live variance > baseline * multiplier.
    refractory
        Minimum interval between emitted MotionEvents.
    """

    window_size: int = 100
    calibration_frames: int = 1000
    threshold_multiplier: float = 4.0
    refractory: timedelta = timedelta(seconds=2)

    # internal state
    _window: deque[tuple[float, ...]] = field(default_factory=deque)
    _baseline: _Welford = field(default_factory=_Welford)
    _last_emit: datetime | None = field(default=None)
    _calibrated: bool = False
    _cal_frames_seen: int = 0

    @property
    def calibrated(self) -> bool:
        return self._calibrated

    @property
    def baseline_variance(self) -> float:
        return self._baseline.variance

    def consume(self, frame: CsiFrame) -> MotionEvent | None:
        # Maintain the rolling window of recent amplitude vectors.
        self._window.append(frame.amplitudes)
        if len(self._window) > self.window_size:
            self._window.popleft()

        # During calibration we just learn the baseline.
        if not self._calibrated:
            self._cal_frames_seen += 1
            v = _vector_variance(self._window)
            if v > 0:
                self._baseline.push(v)
            if self._cal_frames_seen >= self.calibration_frames:
                self._calibrated = True
            return None

        # Live detection.
        if len(self._window) < self.window_size:
            return None
        live_var = _vector_variance(self._window)
        threshold = self._baseline.mean * self.threshold_multiplier
        if threshold <= 0 or live_var < threshold:
            return None

        # Refractory check.
        if self._last_emit is not None and frame.timestamp - self._last_emit < self.refractory:
            return None

        self._last_emit = frame.timestamp
        score = live_var / self._baseline.mean if self._baseline.mean > 0 else float("inf")
        return MotionEvent(timestamp=frame.timestamp, score=score)


def _vector_variance(window: deque[tuple[float, ...]]) -> float:
    """Mean across subcarriers of per-subcarrier variance over the window.

    A robust scalar summary that doesn't care about absolute amplitude.
    """
    if not window:
        return 0.0
    n_sub = len(window[0])
    n_frames = len(window)
    if n_frames < 2:
        return 0.0
    # Compute variance per subcarrier, then mean across subcarriers.
    per_sub_var = []
    for sub in range(n_sub):
        column = [w[sub] for w in window]
        mu = mean(column)
        var = sum((x - mu) ** 2 for x in column) / (n_frames - 1)
        per_sub_var.append(var)
    return mean(per_sub_var)
