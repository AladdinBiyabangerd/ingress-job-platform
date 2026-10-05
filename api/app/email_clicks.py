"""Email click tracking via /r/<token> (plan §8 / §13).

Stateless HMAC tokens encode user + job + mail kind + lang.
GET resolves to an on-site job URL only (no open redirects).
"""

from __future__ import annotations

import hashlib
import hmac
import os
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

KINDS = frozenset({"digest", "high_match"})
LOCALES = frozenset({"az", "en", "ru"})

SCHEMA = """
CREATE TABLE IF NOT EXISTS email_click (
    id INTEGER PRIMARY KEY,
    user_id TEXT NOT NULL,
    job_id INTEGER NOT NULL,
    kind TEXT NOT NULL,
    lang TEXT NOT NULL DEFAULT 'az',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS email_click_user_created ON email_click(user_id, created_at);
CREATE INDEX IF NOT EXISTS email_click_job ON email_click(job_id);
CREATE INDEX IF NOT EXISTS email_click_kind_created ON email_click(kind, created_at);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ensure_email_click_tables(conn) -> None:
    conn.executescript(SCHEMA)


def _secret() -> bytes:
    raw = (
        os.environ.get("EMAIL_UNSUBSCRIBE_SECRET")
        or os.environ.get("INTERNAL_JOB_TOKEN")
        or os.environ.get("OIDC_CLIENT_ID")
        or "ingress-job-dev-unsubscribe"
    ).strip()
    return raw.encode("utf-8")


def click_token(
    user_id: str,
    *,
    job_id: int,
    kind: str,
    lang: str = "az",
) -> str:
    subject = (user_id or "").strip()
    if not subject:
        return ""
    mail_kind = (kind or "").strip().lower()
    if mail_kind not in KINDS:
        return ""
    try:
        jid = int(job_id)
    except (TypeError, ValueError):
        return ""
    if jid <= 0:
        return ""
    locale = (lang or "az").strip().lower()[:2]
    if locale not in LOCALES:
        locale = "az"
    uid_hex = subject.encode("utf-8").hex()
    payload = f"{uid_hex}.{jid}.{mail_kind}.{locale}"
    sig = hmac.new(_secret(), f"click:{payload}".encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload}.{sig}"


def parse_click_token(token: str) -> dict[str, Any] | None:
    text = (token or "").strip()
    if not text or text.count(".") != 4 or len(text) > 700:
        return None
    uid_hex, job_s, kind, lang, sig = text.split(".", 4)
    if not uid_hex or not sig or len(sig) != 64:
        return None
    if kind not in KINDS or lang not in LOCALES:
        return None
    try:
        job_id = int(job_s)
        user_id = bytes.fromhex(uid_hex).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return None
    if job_id <= 0 or not user_id:
        return None
    expected = click_token(user_id, job_id=job_id, kind=kind, lang=lang)
    if not expected or not hmac.compare_digest(expected, text):
        return None
    return {"user_id": user_id, "job_id": job_id, "kind": kind, "lang": lang}


def tracked_job_url(
    user_id: str,
    *,
    job_id: int,
    kind: str,
    lang: str = "az",
) -> str:
    from app.email_prefs import app_base_url

    token = click_token(user_id, job_id=job_id, kind=kind, lang=lang)
    if not token:
        return ""
    return f"{app_base_url()}/r/{quote(token, safe='')}"


def site_job_url(job_id: int, lang: str) -> str:
    from app.email_prefs import app_base_url

    base = app_base_url()
    locale = (lang or "az").strip().lower()[:2]
    if locale not in LOCALES:
        locale = "az"
    prefix = "" if locale == "az" else f"/{locale}"
    return f"{base}{prefix}/jobs/{int(job_id)}"


def log_click(
    conn,
    *,
    user_id: str,
    job_id: int,
    kind: str,
    lang: str = "az",
) -> None:
    ensure_email_click_tables(conn)
    conn.execute(
        """
        INSERT INTO email_click (user_id, job_id, kind, lang, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            (user_id or "").strip(),
            int(job_id),
            (kind or "").strip().lower(),
            (lang or "az").strip().lower()[:2] or "az",
            _now(),
        ),
    )


def resolve_click(conn, token: str) -> dict[str, Any] | None:
    """Validate token, log click, return redirect target (on-site job URL)."""
    parsed = parse_click_token(token)
    if not parsed:
        return None
    log_click(
        conn,
        user_id=parsed["user_id"],
        job_id=parsed["job_id"],
        kind=parsed["kind"],
        lang=parsed["lang"],
    )
    redirect = site_job_url(parsed["job_id"], parsed["lang"])
    return {**parsed, "redirect": redirect}
