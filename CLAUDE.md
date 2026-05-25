# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

Build / test / lint use the Makefile. Both local-venv and container variants exist; they are equivalent.

- `make test` — full suite (`PYTHONPATH=src python -m pytest -v`)
- `make test-unit` — pure-domain only (`tests/unit`)
- `make test-int` — end-to-end with FakeClock + synthetic CSI (`tests/integration`)
- Single test: `PYTHONPATH=src python -m pytest tests/unit/test_state_machine.py::test_name -v`
- `make lint` — `ruff check` + `ruff format --check` on `src tests`
- `make type` — `mypy --strict` (configured for `src`)
- `make run` — runs locally with `WIFI_ALARM_PROFILE=dev`
- `make docker-build` / `make docker-test` / `make docker-run` — same flows inside the container (no Pi hardware needed)
- `./start.sh` — convenience wrapper: `docker compose build` then `docker compose up` (foreground)
- `make install` — `pip install -e ".[dev]"`. Pi deployment uses `pip install ".[pi]"` for `aiosqlite`, `gpiozero`, `lgpio`.

Python 3.11+. `pytest-asyncio` is in `auto` mode — do not decorate async tests.

## Architecture

Hexagonal / ports-and-adapters. The split is load-bearing — keep it intact.

- **`domain/`** is pure: a state machine and a variance detector. No IO, no third-party deps, no knowledge of Telegram / GPIO / SQLite. The state machine is a pure transition function that returns side-effects as data (`NotifyOwner`, `SirenOn`, `SirenOff`, `LogEvent`); the runtime dispatches them.
- **`ports/`** holds the abstract interfaces: `Clock`, `CsiSource`, `Notifier`, `Siren`, `Store`.
- **`adapters/`** has concrete implementations behind those ports: `csi/{synthetic,nexmon}`, `notifier/{console,telegram,email,composite}`, `siren/{mock,gpio}`, `clock/{system,fake}`, `store/{memory,sqlite}`. The `composite` notifier fans out to multiple notifiers.
- **`app/`** wires everything: `config` (env vars), composition root (selects adapters by profile), async `runtime`, and `main` entry.

Profiles: `dev` (synthetic CSI + console notifier + mock siren + memory store + system clock) and `pi` (nexmon + telegram/email composite + gpio siren + sqlite store). Selected via `WIFI_ALARM_PROFILE`.

### Runtime: three concurrent loops

- `capture_loop` — pulls CSI frames → variance detector → motion events → state machine.
- `inbound_loop` — reads Telegram replies/commands → state machine.
- `tick_loop` — drives the state-machine clock once per second so reply timeouts and snooze expiry fire on time.

Because the clock is a port, integration tests use `FakeClock` and advance time manually — no `asyncio.sleep` waits, full suite runs in seconds.

### State machine

```
DISARMED ── /arm ──▶ ARMED
ARMED    ── motion ──▶ ALERTING       (notify with Dismiss/Confirm buttons)
ALERTING ── dismiss ──▶ ARMED
ALERTING ── confirm ──▶ TRIGGERED     (siren on)
ALERTING ── timeout (REPLY_TIMEOUT_S) ──▶ TRIGGERED
TRIGGERED ── /disarm ──▶ DISARMED     (siren off)
*         ── /panic ──▶ TRIGGERED
*         ── /snooze N ──▶ DISARMED for N min, then auto-rearm
```

## Conventions

- Adapters with optional deps (`gpiozero`, `aiosqlite`, `aiosmtplib`) import lazily so dev/test on non-Pi machines never imports Pi-only modules.
- mypy is `strict` over `src`; `gpiozero`, `aiosqlite`, `aiosmtplib` are explicitly excused from `ignore_missing_imports`.
- Ruff selects `E,F,W,I,UP,B,SIM,ASYNC`, line length 100.
- The variance detector spends ~10 s on an empty-room baseline at startup; tests inject `DETECTOR_CAL_FRAMES`/`DETECTOR_THRESHOLD_MULT` to skip or tighten this.
- Telegram bot ignores any chat id other than the configured one — don't add multi-user support without revisiting the security model.

## Hardware notes (Pi)

Nexmon CSI on BCM43455c0 broadcasts CSI frames to UDP 5500 by default; `adapters/csi/nexmon.py` consumes that. The siren adapter assumes a **low-trigger** relay by default (`SIREN_ACTIVE_HIGH=false`); flip for high-trigger modules.

## References

- ScienceDaily background reading: <https://www.sciencedaily.com/releases/2026/05/260522023127.htm>
- KIT research record: <https://publikationen.bibliothek.kit.edu/1000185756>
- Paper PDF (local): `docs/3719027.3765062-1.pdf`