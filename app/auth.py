"""Passwordless login: the student types their university email and gets a
one-time link. No passwords to store, reset or leak (data minimization)."""
import hashlib
import os
import re
import secrets
from datetime import datetime, timedelta, timezone

from .db import connect, new_lunch_id

TOKEN_TTL_MINUTES = 15
RESEND_COOLDOWN_SECONDS = 30

# Comma-separated list. A domain also allows its subdomains, so "thws.de"
# accepts both name@thws.de and name@study.thws.de.
# TODO: confirm the exact THWS student email domain with university IT.
ALLOWED_DOMAINS = [
    d.strip().lower()
    for d in os.environ.get("MAHLZEIT_ALLOWED_DOMAINS", "thws.de").split(",")
    if d.strip()
]

EMAIL_RE = re.compile(r"^[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}$")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def normalize_email(raw: str) -> str:
    return raw.strip().lower()


def validate_email(email: str) -> str | None:
    """Return an error message, or None if the email is acceptable."""
    if not EMAIL_RE.match(email):
        return "That doesn't look like an email address."
    domain = email.rsplit("@", 1)[1]
    if not any(domain == d or domain.endswith("." + d) for d in ALLOWED_DOMAINS):
        shown = " or ".join("@" + d for d in ALLOWED_DOMAINS)
        return f"Please use your university email ({shown})."
    return None


def recently_requested(email: str) -> bool:
    """Simple per-email throttle so the form can't be used to spam an inbox."""
    cutoff = (_now() - timedelta(seconds=RESEND_COOLDOWN_SECONDS)).isoformat()
    with connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM login_tokens WHERE email = ? AND created_at > ? LIMIT 1",
            (email, cutoff),
        ).fetchone()
    return row is not None


def create_login_token(email: str) -> str:
    token = secrets.token_urlsafe(32)
    now = _now()
    with connect() as conn:
        # Housekeeping: drop expired or used tokens so the table stays small.
        conn.execute(
            "DELETE FROM login_tokens WHERE used = 1 OR expires_at < ?", (now.isoformat(),)
        )
        conn.execute(
            "INSERT INTO login_tokens (token_hash, email, created_at, expires_at) VALUES (?, ?, ?, ?)",
            (_hash(token), email, now.isoformat(),
             (now + timedelta(minutes=TOKEN_TTL_MINUTES)).isoformat()),
        )
    return token


def consume_login_token(token: str) -> dict | None:
    """Validate a magic-link token (single use). Returns the user row or None."""
    now = _now().isoformat()
    with connect() as conn:
        row = conn.execute(
            "SELECT email FROM login_tokens WHERE token_hash = ? AND used = 0 AND expires_at > ?",
            (_hash(token), now),
        ).fetchone()
        if row is None:
            return None
        email = row["email"]
        conn.execute("UPDATE login_tokens SET used = 1 WHERE token_hash = ?", (_hash(token),))
        # First successful login creates the account: registration == login.
        if not conn.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone():
            conn.execute("INSERT INTO users (email, lunch_id) VALUES (?, ?)", (email, new_lunch_id(conn)))
        conn.execute("UPDATE users SET last_login = ? WHERE email = ?", (now, email))
        user = conn.execute("SELECT id, email, lunch_id FROM users WHERE email = ?", (email,)).fetchone()
    return dict(user)


def get_user(user_id: int) -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT id, email, lunch_id, created_at FROM users WHERE id = ?", (user_id,)).fetchone()
    return dict(row) if row else None
