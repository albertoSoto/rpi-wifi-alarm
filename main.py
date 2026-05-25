"""Entrypoint: python -m wifi_alarm."""

from __future__ import annotations

import asyncio
import logging
import sys

from .composition import compose
from .config import AlarmConfig
from .runtime import run


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    config = AlarmConfig.from_env()
    wired = compose(config)
    logging.info("wifi-alarm starting in profile=%s", config.profile)
    try:
        asyncio.run(run(wired))
    except KeyboardInterrupt:
        logging.info("interrupted; shutting down")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
