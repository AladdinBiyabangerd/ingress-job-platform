"""Email preferences, unsubscribe tokens, and send log (plan §8 / §13.1)."""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

FREQUENCIES = ("weekly", "biweekly", "important_only", "none")
LOCALES = ("az", "en", "ru")
WEEKDAYS = frozenset(range(7))  # 0=Mon … 6=Sun

SCHEMA = """
CREATE TABLE IF NOT EXISTS email_prefs (
    user_id TEXT PRIMARY KEY,
    frequency TEXT NOT NULL DEFAULT 'none',
    digest INTEGER NOT NULL DEFAULT 1,
    high_match INTEGER NOT NULL DEFAULT 1,
    profile_nudge INTEGER NOT NULL DEFAULT 1,
    language TEXT NOT NULL DEFAULT 'az',
    send_weekday INTEGER NOT NULL DEFAULT 0,
    unsubscribed_at TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL,
    match_near INTEGER NOT NULL DEFAULT 1,
    coach_weekly INTEGER NOT NULL DEFAULT 1,
    push_enabled INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS email_log (
    id INTEGER PRIMARY KEY,
    user_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    period_key TEXT NOT NULL,
    to_email TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'sent',
    meta TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    UNIQUE (user_id, kind, period_key)
);

CREATE INDEX IF NOT EXISTS email_log_user_created ON email_log(user_id, created_at);
CREATE INDEX IF NOT EXISTS email_log_kind_period ON email_log(kind, period_key);
"""

_PREF_COLUMNS = {
    "match_near": "INTEGER NOT NULL DEFAULT 1",
    "coach_weekly": "INTEGER NOT NULL DEFAULT 1",
    "push_enabled": "INTEGER NOT NULL DEFAULT 0",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ensure_email_tables(conn) -> None:
    conn.executescript(SCHEMA)
    cols = {row[1] for row in conn.execute("PRAGMA table_info(email_prefs)")}
    for name, decl in _PREF_COLUMNS.items():
        if name not in cols:
            conn.execute(f"ALTER TABLE email_prefs ADD COLUMN {name} {decl}")
    from app.email_clicks import ensure_email_click_tables

    ensure_email_click_tables(conn)


def _secret() -> bytes:
    raw = (
        os.environ.get("EMAIL_UNSUBSCRIBE_SECRET")
        or os.environ.get("INTERNAL_JOB_TOKEN")
        or os.environ.get("OIDC_CLIENT_ID")
        or "ingress-job-dev-unsubscribe"
    ).strip()
    return raw.encode("utf-8")


def unsubscribe_token(user_id: str) -> str:
    subject = (user_id or "").strip()
    if not subject:
        return ""
    digest = hmac.new(_secret(), f"unsub:{subject}".encode("utf-8"), hashlib.sha256).hexdigest()
    # user_id may contain unsafe URL chars; encode as hex length-prefixed payload
    uid_hex = subject.encode("utf-8").hex()
    return f"{uid_hex}.{digest}"


def parse_unsubscribe_token(token: str) -> str | None:
    text = (token or "").strip()
    if not text or "." not in text or len(text) > 600:
        return None
    uid_hex, sig = text.rsplit(".", 1)
    if not uid_hex or not sig or len(sig) != 64:
        return None
    try:
        user_id = bytes.fromhex(uid_hex).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return None
    expected = unsubscribe_token(user_id)
    if not expected or not hmac.compare_digest(expected, text):
        return None
    return user_id


def app_base_url() -> str:
    raw = (
        os.environ.get("APP_URL")
        or os.environ.get("NEXT_PUBLIC_APP_URL")
        or "http://localhost:3010"
    ).strip().rstrip("/")
    return raw or "http://localhost:3010"


def unsubscribe_url(user_id: str, *, lang: str = "az") -> str:
    token = unsubscribe_token(user_id)
    if not token:
        return ""
    prefix = "" if lang == "az" else f"/{lang}"
    return f"{app_base_url()}{prefix}/unsubscribe/{quote(token, safe='')}"


def _normalize_frequency(value: Any) -> str:
    text = str(value or "").strip().lower()
    return text if text in FREQUENCIES else "none"


def _normalize_language(value: Any) -> str:
    text = str(value or "").strip().lower()[:2]
    return text if text in LOCALES else "az"


def _normalize_weekday(value: Any) -> int:
    try:
        day = int(value)
    except (TypeError, ValueError):
        return 0
    return day if day in WEEKDAYS else 0


def _bool_col(row, name: str, *, default: bool = True) -> bool:
    keys = row.keys()
    if name not in keys:
        return default
    try:
        return bool(int(row[name]))
    except (TypeError, ValueError):
        return default


def _row_prefs(row) -> dict:
    if row is None:
        return {
            "frequency": "none",
            "digest": True,
            "high_match": True,
            "profile_nudge": True,
            "match_near": True,
            "coach_weekly": True,
            "push_enabled": False,
            "language": "az",
            "send_weekday": 0,
            "unsubscribed_at": "",
            "updated_at": None,
        }
    return {
        "frequency": _normalize_frequency(row["frequency"] if "frequency" in row.keys() else row[1]),
        "digest": bool(int(row["digest"] if "digest" in row.keys() else row[2])),
        "high_match": bool(int(row["high_match"] if "high_match" in row.keys() else row[3])),
        "profile_nudge": _bool_col(row, "profile_nudge", default=True),
        "match_near": _bool_col(row, "match_near", default=True),
        "coach_weekly": _bool_col(row, "coach_weekly", default=True),
        "push_enabled": _bool_col(row, "push_enabled", default=False),
        "language": _normalize_language(row["language"] if "language" in row.keys() else row[5]),
        "send_weekday": _normalize_weekday(row["send_weekday"] if "send_weekday" in row.keys() else row[6]),
        "unsubscribed_at": str(
            row["unsubscribed_at"] if "unsubscribed_at" in row.keys() else row[7] or ""
        ),
        "updated_at": str(row["updated_at"] if "updated_at" in row.keys() else row[8] or "") or None,
    }


def _emails_consent(conn, user_id: str) -> bool:
    from app.consents import ensure_consent_tables

    ensure_consent_tables(conn)
    row = conn.execute(
        "SELECT granted FROM consent WHERE user_id = ? AND kind = 'emails'",
        (user_id,),
    ).fetchone()
    if row is None:
        return False
    granted = row["granted"] if "granted" in row.keys() else row[0]
    return bool(int(granted))


def get_prefs(conn, user_id: str) -> dict:
    ensure_email_tables(conn)
    subject = (user_id or "").strip()
    row = conn.execute(
        """
        SELECT user_id, frequency, digest, high_match, profile_nudge,
               language, send_weekday, unsubscribed_at, updated_at,
               match_near, coach_weekly, push_enabled
        FROM email_prefs
        WHERE user_id = ?
        """,
        (subject,),
    ).fetchone()
    prefs = _row_prefs(row)
    consent = _emails_consent(conn, subject)
    return {
        **prefs,
        "emails_consent": consent,
        "unsubscribe_url": unsubscribe_url(subject, lang=prefs["language"]) if subject else "",
    }


def save_prefs(
    conn,
    user_id: str,
    *,
    frequency: str | None = None,
    digest: bool | None = None,
    high_match: bool | None = None,
    profile_nudge: bool | None = None,
    match_near: bool | None = None,
    coach_weekly: bool | None = None,
    push_enabled: bool | None = None,
    language: str | None = None,
    send_weekday: int | None = None,
    clear_unsubscribe: bool = False,
) -> dict:
    ensure_email_tables(conn)
    subject = (user_id or "").strip()
    if not subject:
        raise ValueError("user_id_required")
    current = get_prefs(conn, subject)
    next_freq = _normalize_frequency(frequency if frequency is not None else current["frequency"])
    next_digest = bool(current["digest"] if digest is None else digest)
    next_high = bool(current["high_match"] if high_match is None else high_match)
    next_nudge = bool(current["profile_nudge"] if profile_nudge is None else profile_nudge)
    next_near = bool(current["match_near"] if match_near is None else match_near)
    next_coach = bool(current["coach_weekly"] if coach_weekly is None else coach_weekly)
    next_push = bool(current["push_enabled"] if push_enabled is None else push_enabled)
    next_lang = _normalize_language(language if language is not None else current["language"])
    next_day = _normalize_weekday(
        send_weekday if send_weekday is not None else current["send_weekday"]
    )
    unsub = "" if clear_unsubscribe else (current.get("unsubscribed_at") or "")
    if next_freq == "none":
        unsub = unsub or _now()
    elif clear_unsubscribe or frequency is not None:
        unsub = ""
    ts = _now()
    conn.execute(
        """
        INSERT INTO email_prefs (
            user_id, frequency, digest, high_match, profile_nudge,
            language, send_weekday, unsubscribed_at, updated_at,
            match_near, coach_weekly, push_enabled
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            frequency = excluded.frequency,
            digest = excluded.digest,
            high_match = excluded.high_match,
            profile_nudge = excluded.profile_nudge,
            language = excluded.language,
            send_weekday = excluded.send_weekday,
            unsubscribed_at = excluded.unsubscribed_at,
            updated_at = excluded.updated_at,
            match_near = excluded.match_near,
            coach_weekly = excluded.coach_weekly,
            push_enabled = excluded.push_enabled
        """,
        (
            subject,
            next_freq,
            1 if next_digest else 0,
            1 if next_high else 0,
            1 if next_nudge else 0,
            next_lang,
            next_day,
            unsub,
            ts,
            1 if next_near else 0,
            1 if next_coach else 0,
            1 if next_push else 0,
        ),
    )
    return get_prefs(conn, subject)


def apply_unsubscribe(conn, user_id: str) -> dict:
    """One-click unsubscribe: stop marketing mail and clear emails consent."""
    from app.consents import ensure_consent_tables

    ensure_consent_tables(conn)
    subject = (user_id or "").strip()
    if not subject:
        raise ValueError("user_id_required")
    prefs = save_prefs(
        conn,
        subject,
        frequency="none",
        digest=False,
        high_match=False,
        profile_nudge=False,
        match_near=False,
        coach_weekly=False,
        push_enabled=False,
    )
    version = "1.0"
    try:
        from app.consents import load_consent_copy

        version = str(load_consent_copy().get("version") or "1.0")
    except Exception:
        pass
    conn.execute(
        """
        INSERT INTO consent (user_id, kind, granted, version, ts, ip, ua)
        VALUES (?, 'emails', 0, ?, ?, '', 'unsubscribe')
        ON CONFLICT(user_id, kind) DO UPDATE SET
            granted = 0,
            version = excluded.version,
            ts = excluded.ts,
            ua = excluded.ua
        """,
        (subject, version, _now()),
    )
    return prefs


def marketing_allowed(prefs: dict) -> bool:
    if not prefs.get("emails_consent"):
        return False
    if (prefs.get("unsubscribed_at") or "").strip():
        return False
    if prefs.get("frequency") == "none":
        return False
    return True


def digest_enabled(prefs: dict) -> bool:
    if not marketing_allowed(prefs):
        return False
    if prefs.get("frequency") in {"important_only", "none"}:
        return False
    return bool(prefs.get("digest"))


def high_match_enabled(prefs: dict) -> bool:
    if not marketing_allowed(prefs):
        return False
    return bool(prefs.get("high_match"))


def match_near_enabled(prefs: dict) -> bool:
    if not marketing_allowed(prefs):
        return False
    return bool(prefs.get("match_near"))


def profile_nudge_enabled(prefs: dict) -> bool:
    if not marketing_allowed(prefs):
        return False
    return bool(prefs.get("profile_nudge"))


def coach_weekly_enabled(prefs: dict) -> bool:
    if not marketing_allowed(prefs):
        return False
    return bool(prefs.get("coach_weekly"))


def period_key_for_digest(*, when: datetime | None = None, frequency: str) -> str:
    moment = when or datetime.now(timezone.utc)
    iso = moment.isocalendar()
    if frequency == "biweekly":
        # Pair weeks: 1-2, 3-4, …
        pair = ((iso.week - 1) // 2) + 1
        return f"{iso.year}-B{pair:02d}"
    return f"{iso.year}-W{iso.week:02d}"


def day_key(*, when: datetime | None = None) -> str:
    moment = when or datetime.now(timezone.utc)
    return moment.date().isoformat()


def already_logged(conn, *, user_id: str, kind: str, period_key: str) -> bool:
    ensure_email_tables(conn)
    row = conn.execute(
        """
        SELECT 1 FROM email_log
        WHERE user_id = ? AND kind = ? AND period_key = ?
        """,
        (user_id, kind, period_key),
    ).fetchone()
    return row is not None


def marketing_sent_today(conn, *, user_id: str, day: str | None = None) -> bool:
    from app.engagement import MARKETING_EMAIL_KINDS

    ensure_email_tables(conn)
    key = day or day_key()
    kinds = tuple(sorted(MARKETING_EMAIL_KINDS))
    placeholders = ", ".join("?" for _ in kinds)
    row = conn.execute(
        f"""
        SELECT 1 FROM email_log
        WHERE user_id = ?
          AND status = 'sent'
          AND kind IN ({placeholders})
          AND substr(created_at, 1, 10) = ?
        LIMIT 1
        """,
        (user_id, *kinds, key),
    ).fetchone()
    return row is not None


def log_email(
    conn,
    *,
    user_id: str,
    kind: str,
    period_key: str,
    to_email: str = "",
    status: str = "sent",
    meta: str = "{}",
) -> bool:
    """Insert log row. Returns False if the unique key already exists."""
    ensure_email_tables(conn)
    try:
        conn.execute(
            """
            INSERT INTO email_log (
                user_id, kind, period_key, to_email, status, meta, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, kind, period_key, to_email or "", status, meta or "{}", _now()),
        )
        return True
    except Exception:
        return False


def list_candidate_user_ids(conn) -> list[str]:
    """Users who may receive digests: emails consent and/or prefs row."""
    ensure_email_tables(conn)
    from app.consents import ensure_consent_tables

    ensure_consent_tables(conn)
    rows = conn.execute(
        """
        SELECT DISTINCT user_id FROM (
            SELECT user_id FROM consent WHERE kind = 'emails' AND granted = 1
            UNION
            SELECT user_id FROM email_prefs
        )
        """
    ).fetchall()
    out: list[str] = []
    for row in rows:
        uid = row["user_id"] if "user_id" in row.keys() else row[0]
        text = str(uid or "").strip()
        if text:
            out.append(text)
    return out


def new_token_suffix() -> str:
    """Test helper / opaque random (not used for signed tokens)."""
    return secrets.token_hex(8)
