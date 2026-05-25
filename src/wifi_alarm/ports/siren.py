"""Port: Siren.

A boolean actuator. Real impl: GPIO pin → relay → 12V siren.
Mock impl: logs on/off events.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class Siren(ABC):
    @abstractmethod
    async def on(self) -> None: ...

    @abstractmethod
    async def off(self) -> None: ...

    @abstractmethod
    async def aclose(self) -> None: ...
