"""Staff view of per-user notification delivery (email_log / engagement_log / skips).

Read-only. Used by GET /api/v1/admin/notification-log so staff can answer
"why did this user get only N emails?" without database access.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

MAX_ROWS = 300


def mask_email(value: str) -> str:
    text = (value or "").strip()
    if "@" not in text:
        return "" if not text else "***"
    local, _, domain = text.partition("@")
    head = local[:1] if local else ""
    return f"{head}***@{domain}"


def _echo_query(value: str) -> str:
    text = (value or "").strip()
    return mask_email(text) if "@" in text else text


def _rows(conn, sql: str, params: tuple) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in conn.execute(sql, params).fetchall():
        out.append({key: row[key] for key in row.keys()})
    return out


def _channels(raw: object) -> list[str]:
    try:
        data = json.loads(str(raw or "[]"))
    except (TypeError, ValueError):
        return []
    return [str(x) for x in data] if isinstance(data, list) else []


def _prefs_summary(conn, user_id: str) -> dict[str, Any]:
    from app.email_prefs import get_prefs

    prefs = get_prefs(conn, user_id)
    keys = (
        "frequency",
        "send_weekday",
        "language",
        "digest",
        "high_match",
        "match_near",
        "profile_nudge",
        "coach_weekly",
        "push_enabled",
        "emails_consent",
    )
    summary = {key: prefs.get(key) for key in keys}
    summary["unsubscribed"] = bool((prefs.get("unsubscribed_at") or "").strip())
    return summary


def _profile_status(conn, user_id: str) -> str:
    try:
        from app.cv_profile import _profile_payload

        return str(_profile_payload(conn, user_id=user_id).get("status") or "empty")
    except Exception:
        return ""


def _push_count(conn, user_id: str) -> int:
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM push_subscriptions WHERE user_id = ?", (user_id,)
        ).fetchone()
        return int(row[0] if row else 0)
    except Exception:
        return 0


def resolve_user(query: str) -> tuple[str, str]:
    """(user_id, contact email) from a subject or an email address."""
    from app.profiles import contact_email_for, subject_for_contact_email

    text = (query or "").strip()
    if not text:
        return "", ""
    if "@" in text:
        subject = subject_for_contact_email(text)
        return subject, (text.lower() if subject else "")
    return text, contact_email_for(text)


def build_notification_log(
    conn,
    *,
    user: str = "",
    days: int = 30,
    limit: int = 200,
) -> dict[str, Any]:
    from app.email_prefs import EMAIL_SEND_MAX_ATTEMPTS, ensure_email_tables
    from app.engagement import ensure_engagement_tables

    ensure_email_tables(conn)
    ensure_engagement_tables(conn)
    days = max(1, min(int(days or 30), 90))
    limit = max(1, min(int(limit or 200), MAX_ROWS))
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(timespec="seconds")
    since_day = since[:10]
    payload: dict[str, Any] = {
        "days": days,
        "query": _echo_query(user),
        "user": None,
        "max_attempts": EMAIL_SEND_MAX_ATTEMPTS,
        "emails": [],
        "engagement": [],
        "skips": [],
        "totals": {"sent": 0, "failed": 0, "sending": 0, "skipped": 0},
    }
    user_id, email = resolve_user(user)
    if (user or "").strip() and not user_id:
        payload["not_found"] = True
        return payload

    where = "created_at >= ?"
    params: tuple = (since,)
    skip_where = "day >= ?"
    skip_params: tuple = (since_day,)
    if user_id:
        where = "user_id = ? AND " + where
        params = (user_id, since)
        skip_where = "user_id = ? AND " + skip_where
        skip_params = (user_id, since_day)
        payload["user"] = {
            "user_id": user_id,
            "email": mask_email(email),
            "profile_status": _profile_status(conn, user_id),
            "push_subscriptions": _push_count(conn, user_id),
            "prefs": _prefs_summary(conn, user_id),
        }

    emails = _rows(
        conn,
        f"""
        SELECT user_id, kind, period_key, to_email, status, attempts, reason, created_at
        FROM email_log WHERE {where}
        ORDER BY created_at DESC LIMIT {limit}
        """,
        params,
    )
    for row in emails:
        row["to_email"] = mask_email(str(row.get("to_email") or ""))
        status = str(row.get("status") or "")
        if status in payload["totals"]:
            payload["totals"][status] += 1
    payload["emails"] = emails

    engagement = _rows(
        conn,
        f"""
        SELECT user_id, kind, period_key, job_id, channels, created_at
        FROM engagement_log WHERE {where}
        ORDER BY created_at DESC LIMIT {limit}
        """,
        params,
    )
    for row in engagement:
        row["channels"] = _channels(row.get("channels"))
    payload["engagement"] = engagement

    skips = _rows(
        conn,
        f"""
        SELECT user_id, kind, day, reason, hits, last_at
        FROM notification_skip_log WHERE {skip_where}
        ORDER BY day DESC, last_at DESC LIMIT {limit}
        """,
        skip_params,
    )
    payload["skips"] = skips
    payload["totals"]["skipped"] = len(skips)
    return payload
