# Dev container — runs the dev profile (synthetic CSI, mock siren).
# Use this on your Mac to develop and test without a Pi.
# The Pi runs natively under systemd, not in Docker, because nexmon_csi
# needs the patched broadcom firmware loaded by the host kernel.

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    WIFI_ALARM_PROFILE=dev

WORKDIR /app

# Install runtime + dev deps. Hardware deps (gpiozero, aiosqlite) are
# in the [pi] extra and intentionally NOT installed here.
COPY pyproject.toml ./
RUN pip install --upgrade pip && \
    pip install "httpx>=0.27" "aiosmtplib>=0.20" "pytest>=8" "pytest-asyncio>=0.23" "ruff>=0.6"

COPY src/ ./src/
COPY tests/ ./tests/
COPY pytest.ini ./

ENV PYTHONPATH=/app/src

CMD ["python", "-m", "wifi_alarm"]
