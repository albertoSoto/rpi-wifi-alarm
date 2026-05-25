"""Nexmon CSI adapter (Pi 3B+ / Pi 4 with patched Broadcom firmware).

Listens on the UDP port that nexmon_csi sends to (default 5500) and
parses the binary CSI frames into CsiFrame domain objects.

This is a SCAFFOLD: the parser below handles the standard nexmon CSI
header layout for BCM43455c0 / 80 MHz HT/VHT captures. Verify against
your `makecsiparams` configuration before relying on it.

Setup (on Pi 3B+, Raspbian Bullseye/Bookworm 32-bit):
  1. Build & install nexmon_csi for BCM43455c0:
     https://github.com/seemoo-lab/nexmon_csi
  2. Activate the patched firmware on boot.
  3. Configure CSI extraction with `makecsiparams` + `nexutil -Iwlan0 -s500 -b -l34 -v<...>`.
  4. nexmon will UDP-broadcast CSI frames to port 5500 by default.

Run this adapter on the Pi; it binds 0.0.0.0:5500 and decodes frames.
"""

from __future__ import annotations

import asyncio
import socket
import struct
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

from ...domain.events import CsiFrame
from ...ports.clock import Clock
from ...ports.csi_source import CsiSource

# Nexmon CSI UDP packet format for BCM43455 (simplified, see nexmon_csi/utils/matlab/read_csi.m
# and src/csi_extractor.c for canonical layout).
#
# Bytes  Field
# 0-1    magic (0x1111)
# 2-3    rssi (int16, signed)
# 4      fctl
# 5      src MAC byte 0
# ...
# 18-19  seqnum
# 20-21  core/spatial
# 22-23  chanspec
# 24-27  chip version
# 28+    CSI payload: 2*n_sub int16 values (re, im), little-endian.
#
# For a 80 MHz HT capture on BCM43455 you typically get 256 subcarriers; on 20 MHz, 64.
# The user-visible "useful" subcarriers depend on the chan spec.

NEXMON_HEADER = struct.Struct("<HhBBBBBBBBBBBBBBHBBHII")  # 28 bytes


@dataclass
class NexmonCsiSource(CsiSource):
    """UDP listener for nexmon_csi output."""

    clock: Clock
    bind_host: str = "0.0.0.0"
    bind_port: int = 5500
    n_subcarriers: int = 256  # 80 MHz default; set to 64 for 20 MHz, 128 for 40 MHz

    _sock: socket.socket | None = field(default=None, init=False)
    _closed: bool = False

    async def stream(self) -> AsyncIterator[CsiFrame]:
        loop = asyncio.get_running_loop()
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setblocking(False)
        self._sock.bind((self.bind_host, self.bind_port))

        while not self._closed:
            try:
                data = await loop.sock_recv(self._sock, 4096)
            except (OSError, asyncio.CancelledError):
                break
            frame = self._parse(data)
            if frame is not None:
                yield frame

    def _parse(self, data: bytes) -> CsiFrame | None:
        if len(data) < NEXMON_HEADER.size + 4:
            return None
        header = NEXMON_HEADER.unpack_from(data, 0)
        magic = header[0]
        if magic != 0x1111:
            return None
        rssi = header[1]
        payload = data[NEXMON_HEADER.size :]
        # Each subcarrier is two int16: re, im. Compute amplitudes.
        expected = self.n_subcarriers * 4
        if len(payload) < expected:
            return None
        ints = struct.unpack_from(f"<{self.n_subcarriers * 2}h", payload, 0)
        amps = tuple(
            (ints[i] * ints[i] + ints[i + 1] * ints[i + 1]) ** 0.5
            for i in range(0, len(ints), 2)
        )
        return CsiFrame(timestamp=self.clock.now(), amplitudes=amps, rssi=rssi)

    async def aclose(self) -> None:
        self._closed = True
        if self._sock is not None:
            self._sock.close()
            self._sock = None
