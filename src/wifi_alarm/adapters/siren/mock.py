"""Mock siren — logs on/off, holds last state for assertions."""

from __future__ import annotations

from dataclasses import dataclass, field

from ...ports.siren import Siren


@dataclass
class MockSiren(Siren):
    is_on: bool = False
    log: list[str] = field(default_factory=list)

    async def on(self) -> None:
        self.is_on = True
        self.log.append("on")
        print("🚨 SIREN ON", flush=True)

    async def off(self) -> None:
        self.is_on = False
        self.log.append("off")
        print("🔕 siren off", flush=True)

    async def aclose(self) -> None:
        await self.off()
