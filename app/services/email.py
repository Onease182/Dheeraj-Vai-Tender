"""Outbound email via SMTP. If no SMTP host is configured (e.g. local dev),
falls back to logging the message instead of failing — registration/admin
actions should never hard-fail just because email isn't set up yet."""

import logging
import smtplib
from email.message import EmailMessage

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def send_email(to: str, subject: str, body: str) -> None:
    if not settings.smtp_host:
        logger.warning("SMTP not configured — logging email instead of sending.\nTo: %s\nSubject: %s\n%s", to, subject, body)
        return

    msg = EmailMessage()
    msg["From"] = settings.smtp_from
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as server:
            if settings.smtp_use_tls:
                server.starttls()
            if settings.smtp_username:
                server.login(settings.smtp_username, settings.smtp_password)
            server.send_message(msg)
    except Exception:
        logger.exception("Failed to send email to %s", to)


def send_verification_email(to: str, token: str) -> None:
    link = f"{settings.frontend_base_url}/verify-email?token={token}"
    send_email(
        to=to,
        subject="Verify your TenderX Nepal account",
        body=(
            "Welcome to TenderX Nepal.\n\n"
            f"Please verify your email by opening this link:\n{link}\n\n"
            "If you didn't create this account, you can ignore this email."
        ),
    )


def send_password_reset_email(to: str, token: str) -> None:
    link = f"{settings.frontend_base_url}/reset-password?token={token}"
    send_email(
        to=to,
        subject="Reset your TenderX Nepal password",
        body=(
            "We received a request to reset your TenderX Nepal password.\n\n"
            f"Open this link to choose a new password (valid for 1 hour):\n{link}\n\n"
            "If you didn't request this, you can ignore this email — your password won't change."
        ),
    )


def send_password_reset_by_admin_email(to: str, new_password: str) -> None:
    send_email(
        to=to,
        subject="Your TenderX Nepal password was reset",
        body=(
            "An administrator has reset your TenderX Nepal password.\n\n"
            f"Your new temporary password is:\n{new_password}\n\n"
            "Please log in and change it as soon as possible."
        ),
    )
