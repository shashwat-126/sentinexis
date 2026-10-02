"""
Notification channel senders.

Each function is independent and best-effort: a failure sending to one
channel must never block the others, so every function catches its own
exceptions and returns a result dict rather than raising.
"""
from __future__ import annotations

import os
import smtplib
from email.mime.text import MIMEText

import requests

from shared.logger import setup_logger

logger = setup_logger("notification-service.channels")

SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")
TEAMS_WEBHOOK_URL = os.getenv("TEAMS_WEBHOOK_URL", "")

SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
NOTIFY_EMAIL_FROM = os.getenv("NOTIFY_EMAIL_FROM", "aiops-platform@example.com")
NOTIFY_EMAIL_TO = os.getenv("NOTIFY_EMAIL_TO", "")


def send_slack(title: str, message: str) -> dict:
    if not SLACK_WEBHOOK_URL:
        return {"channel": "slack", "sent": False, "reason": "not_configured"}
    try:
        resp = requests.post(SLACK_WEBHOOK_URL, json={"text": f"*{title}*\n{message}"}, timeout=5)
        resp.raise_for_status()
        return {"channel": "slack", "sent": True}
    except Exception as e:
        logger.error(f"Slack notification failed: {e}")
        return {"channel": "slack", "sent": False, "reason": str(e)}


def send_discord(title: str, message: str) -> dict:
    if not DISCORD_WEBHOOK_URL:
        return {"channel": "discord", "sent": False, "reason": "not_configured"}
    try:
        resp = requests.post(DISCORD_WEBHOOK_URL, json={"content": f"**{title}**\n{message}"}, timeout=5)
        resp.raise_for_status()
        return {"channel": "discord", "sent": True}
    except Exception as e:
        logger.error(f"Discord notification failed: {e}")
        return {"channel": "discord", "sent": False, "reason": str(e)}


def send_teams(title: str, message: str) -> dict:
    if not TEAMS_WEBHOOK_URL:
        return {"channel": "teams", "sent": False, "reason": "not_configured"}
    try:
        card = {
            "@type": "MessageCard",
            "@context": "http://schema.org/extensions",
            "summary": title,
            "title": title,
            "text": message,
        }
        resp = requests.post(TEAMS_WEBHOOK_URL, json=card, timeout=5)
        resp.raise_for_status()
        return {"channel": "teams", "sent": True}
    except Exception as e:
        logger.error(f"Teams notification failed: {e}")
        return {"channel": "teams", "sent": False, "reason": str(e)}


def send_email(title: str, message: str) -> dict:
    if not (SMTP_HOST and NOTIFY_EMAIL_TO):
        return {"channel": "email", "sent": False, "reason": "not_configured"}
    try:
        msg = MIMEText(message)
        msg["Subject"] = title
        msg["From"] = NOTIFY_EMAIL_FROM
        msg["To"] = NOTIFY_EMAIL_TO

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            server.starttls()
            if SMTP_USER:
                server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(NOTIFY_EMAIL_FROM, [NOTIFY_EMAIL_TO], msg.as_string())
        return {"channel": "email", "sent": True}
    except Exception as e:
        logger.error(f"Email notification failed: {e}")
        return {"channel": "email", "sent": False, "reason": str(e)}


SENDERS = {
    "slack": send_slack,
    "discord": send_discord,
    "teams": send_teams,
    "email": send_email,
}
