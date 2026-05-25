"""Email notifier — outbound only.

Sends alerts via SMTP. Inbound stream is permanently empty (we don't
parse IMAP — replies happen on Telegram).

Setup: provide SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, EMAIL_FROM,
EMAIL_TO. For Gmail, generate an app password and use smtp.gmail.com:587.

Dependencies: aiosmtplib.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from email.message import EmailMessage

from ...domain.events import UserCommand, UserReply
from ...ports.notifier import AlertMessage, Notifier


@dataclass
class EmailNotifier(Notifier):
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_pass: str
    sender: str
    recipient: str
    use_tls: bool = True
    subject_prefix: str = "[wifi-alarm]"

    async def send(self, msg: AlertMessage) -> str:
        import aiosmtplib

        nid = f"mail-{uuid.uuid4().hex[:8]}"
        em = EmailMessage()
        em["From"] = self.sender
        em["To"] = self.recipient
        em["Subject"] = f"{self.subject_prefix} {'alert' if msg.awaiting_reply else 'info'}"
        em.set_content(msg.text)
        await aiosmtplib.send(
            em,
            hostname=self.smtp_host,
            port=self.smtp_port,
            username=self.smtp_user,
            password=self.smtp_pass,
            start_tls=self.use_tls,
        )
        return nid

    async def inbound(self) -> AsyncIterator[UserReply | UserCommand]:
        # Outbound-only channel.
        if False:
            yield  # pragma: no cover

    async def aclose(self) -> None:
        return
