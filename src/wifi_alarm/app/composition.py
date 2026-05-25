"""Composition root.

The ONLY place where concrete adapter classes are imported and wired.
Tests and main entrypoint both go through here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from ..adapters.clock.system import SystemClock
from ..adapters.csi.synthetic import SyntheticCsiSource
from ..adapters.notifier.composite import CompositeNotifier
from ..adapters.notifier.console import ConsoleNotifier
from ..adapters.siren.mock import MockSiren
from ..adapters.store.memory import MemoryStore
from ..domain.detector import VarianceDetector
from ..domain.state_machine import StateMachine
from ..ports.clock import Clock
from ..ports.csi_source import CsiSource
from ..ports.notifier import Notifier
from ..ports.siren import Siren
from ..ports.store import Store
from .config import AlarmConfig


@dataclass
class Wired:
    config: AlarmConfig
    clock: Clock
    csi: CsiSource
    notifier: Notifier
    siren: Siren
    store: Store
    detector: VarianceDetector
    state_machine: StateMachine


def compose(config: AlarmConfig) -> Wired:
    """Return the fully wired graph for the given profile.

    For tests, prefer compose_test() which lets you inject fakes explicitly.
    """
    clock: Clock = SystemClock()

    csi: CsiSource
    siren: Siren
    store: Store
    notifiers: list[Notifier] = []

    if config.profile == "dev":
        csi = SyntheticCsiSource(clock=clock)
        siren = MockSiren()
        store = MemoryStore()
        notifiers.append(ConsoleNotifier())
        # Optional: real telegram/email if creds present, even in dev.
        notifiers.extend(_optional_real_notifiers(config, clock))

    elif config.profile == "pi":
        from ..adapters.csi.nexmon import NexmonCsiSource
        from ..adapters.siren.gpio import GpioSiren
        from ..adapters.store.sqlite import SqliteStore

        csi = NexmonCsiSource(
            clock=clock,
            bind_port=config.nexmon_udp_port,
            n_subcarriers=config.nexmon_n_subcarriers,
        )
        siren = GpioSiren(pin=config.siren_gpio_pin, active_high=config.siren_active_high)
        store = SqliteStore(path=config.sqlite_path)
        notifiers.extend(_optional_real_notifiers(config, clock))
        if not notifiers:
            # Last-resort fallback so the system isn't silent if config is incomplete.
            notifiers.append(ConsoleNotifier())

    else:  # pragma: no cover
        raise ValueError(f"unknown profile: {config.profile}")

    notifier: Notifier = (
        notifiers[0] if len(notifiers) == 1 else CompositeNotifier(members=notifiers)
    )

    detector = VarianceDetector(
        window_size=config.detector_window,
        calibration_frames=config.detector_calibration_frames,
        threshold_multiplier=config.detector_threshold_mult,
    )
    state_machine = StateMachine(reply_timeout=timedelta(seconds=config.reply_timeout_s))

    return Wired(
        config=config,
        clock=clock,
        csi=csi,
        notifier=notifier,
        siren=siren,
        store=store,
        detector=detector,
        state_machine=state_machine,
    )


def _optional_real_notifiers(config: AlarmConfig, clock: Clock) -> list[Notifier]:
    out: list[Notifier] = []
    if config.telegram is not None:
        from ..adapters.notifier.telegram import TelegramNotifier

        out.append(
            TelegramNotifier(
                bot_token=config.telegram.bot_token,
                chat_id=config.telegram.chat_id,
                clock=clock,
            )
        )
    if config.email is not None:
        from ..adapters.notifier.email import EmailNotifier

        out.append(
            EmailNotifier(
                smtp_host=config.email.host,
                smtp_port=config.email.port,
                smtp_user=config.email.user,
                smtp_pass=config.email.password,
                sender=config.email.sender,
                recipient=config.email.recipient,
            )
        )
    return out
