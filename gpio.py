"""GPIO siren — Pi 3B+ relay driver.

Wiring (typical low-trigger 5V relay module):
  Pi 5V       → relay VCC
  Pi GND      → relay GND
  Pi GPIO 17  → relay IN     (BCM numbering; physical pin 11)
  Relay COM/NO→ siren + power (12V/whatever the siren needs, SEPARATE supply)

Note: low-trigger relays close when IN is pulled LOW, so we invert.
The active_high flag handles either polarity.

Uses gpiozero, which on Pi 5 prefers the lgpio backend (set via the
GPIOZERO_PIN_FACTORY env var if needed).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ...ports.siren import Siren


@dataclass
class GpioSiren(Siren):
    pin: int = 17
    active_high: bool = False  # low-trigger relays are common
    _device: object | None = field(default=None, init=False)

    def _ensure(self) -> None:
        if self._device is None:
            from gpiozero import OutputDevice  # imported lazily so dev container doesn't need it

            self._device = OutputDevice(
                self.pin, active_high=self.active_high, initial_value=False
            )

    async def on(self) -> None:
        self._ensure()
        self._device.on()  # type: ignore[union-attr]

    async def off(self) -> None:
        self._ensure()
        self._device.off()  # type: ignore[union-attr]

    async def aclose(self) -> None:
        if self._device is not None:
            self._device.off()  # type: ignore[union-attr]
            self._device.close()  # type: ignore[union-attr]
            self._device = None
