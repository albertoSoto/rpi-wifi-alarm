"""Configuration.

Loaded from environment variables. Profile picks which adapters get wired.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

Profile = Literal["dev", "pi"]


def _env(name: str, default: str | None = None) -> str | None:
    v = os.environ.get(name, default)
    return v if v not in (None, "") else None


def _env_int(name: str, default: int) -> int:
    raw = _env(name)
    return int(raw) if raw is not None else default


def _env_float(name: str, default: float) -> float:
    raw = _env(name)
    return float(raw) if raw is not None else default


@dataclass(frozen=True, slots=True)
class TelegramConfig:
    bot_token: str
    chat_id: int


@dataclass(frozen=True, slots=True)
class EmailConfig:
    host: str
    port: int
    user: str
    password: str
    sender: str
    recipient: str


@dataclass(frozen=True, slots=True)
class AlarmConfig:
    profile: Profile
    reply_timeout_s: int
    detector_window: int
    detector_calibration_frames: int
    detector_threshold_mult: float
    siren_gpio_pin: int
    siren_active_high: bool
    nexmon_udp_port: int
    nexmon_n_subcarriers: int
    sqlite_path: str
    telegram: TelegramConfig | None
    email: EmailConfig | None

    @staticmethod
    def from_env() -> "AlarmConfig":
        profile: Profile = _env("WIFI_ALARM_PROFILE", "dev")  # type: ignore[assignment]
        if profile not in ("dev", "pi"):
            raise ValueError(f"WIFI_ALARM_PROFILE must be dev|pi, got {profile!r}")

        tg = None
        tok = _env("TELEGRAM_BOT_TOKEN")
        cid = _env("TELEGRAM_CHAT_ID")
        if tok and cid:
            tg = TelegramConfig(bot_token=tok, chat_id=int(cid))

        em = None
        if all(_env(k) for k in ("SMTP_HOST", "SMTP_USER", "SMTP_PASS", "EMAIL_FROM", "EMAIL_TO")):
            em = EmailConfig(
                host=_env("SMTP_HOST"),  # type: ignore[arg-type]
                port=_env_int("SMTP_PORT", 587),
                user=_env("SMTP_USER"),  # type: ignore[arg-type]
                password=_env("SMTP_PASS"),  # type: ignore[arg-type]
                sender=_env("EMAIL_FROM"),  # type: ignore[arg-type]
                recipient=_env("EMAIL_TO"),  # type: ignore[arg-type]
            )

        return AlarmConfig(
            profile=profile,
            reply_timeout_s=_env_int("REPLY_TIMEOUT_S", 60),
            detector_window=_env_int("DETECTOR_WINDOW", 100),
            detector_calibration_frames=_env_int("DETECTOR_CAL_FRAMES", 1000),
            detector_threshold_mult=_env_float("DETECTOR_THRESHOLD_MULT", 4.0),
            siren_gpio_pin=_env_int("SIREN_GPIO_PIN", 17),
            siren_active_high=_env("SIREN_ACTIVE_HIGH", "false").lower() == "true",
            nexmon_udp_port=_env_int("NEXMON_UDP_PORT", 5500),
            nexmon_n_subcarriers=_env_int("NEXMON_N_SUBCARRIERS", 256),
            sqlite_path=_env("SQLITE_PATH", "/var/lib/wifi-alarm/state.db"),
            telegram=tg,
            email=em,
        )
