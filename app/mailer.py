"""Sends the login email through the university's SMTP server.

If no SMTP server is configured (e.g. during the hackathon demo), the link is
printed to the console and shown on the "check your inbox" page instead.
"""
import logging
import os
import smtplib
from email.message import EmailMessage

log = logging.getLogger("mahlzeit.mail")

SMTP_HOST = os.environ.get("SMTP_HOST")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")
MAIL_FROM = os.environ.get("MAIL_FROM", "mahlzeit@thws.de")


def smtp_configured() -> bool:
    return bool(SMTP_HOST)


def send_login_link(to: str, link: str) -> None:
    body = (
        "Hi!\n\n"
        "Click this link to sign in to Mahlzeit, the THWS lunch matching:\n\n"
        f"{link}\n\n"
        "The link works once and expires in 15 minutes.\n"
        "If you didn't request it, just ignore this email.\n\n"
        "Fit4Germany @ THWS"
    )
    if not smtp_configured():
        log.warning("DEMO MODE (no SMTP): login link for %s -> %s", to, link)
        return

    msg = EmailMessage()
    msg["Subject"] = "Your Mahlzeit sign-in link"
    msg["From"] = MAIL_FROM
    msg["To"] = to
    msg.set_content(body)
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as s:
        s.starttls()
        if SMTP_USER:
            s.login(SMTP_USER, SMTP_PASSWORD or "")
        s.send_message(msg)
