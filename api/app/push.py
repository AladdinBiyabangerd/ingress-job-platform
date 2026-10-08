"""Web Push subscriptions + VAPID send (engagement Phase 5)."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("ingress-job.push")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def vapid_public_key() -> str:
    return (os.environ.get("VAPID_PUBLIC_KEY") or "").strip()


def vapid_private_key() -> str:
    return (os.environ.get("VAPID_PRIVATE_KEY") or "").strip()


def vapid_subject() -> str:
    raw = (os.environ.get("VAPID_SUBJECT") or "").strip()
    if not raw:
        return ""
    if raw.startswith("mailto:") or raw.startswith("https://"):
        return raw
    return f"mailto:{raw}"


def vapid_configured() -> bool:
    return bool(vapid_public_key() and vapid_private_key() and vapid_subject())


def _ensure_tables(conn) -> None:
    from app.engagement import ensure_engagement_tables

    ensure_engagement_tables(conn)


def upsert_subscription(
    conn,
    *,
    user_id: str,
    endpoint: str,
    p256dh: str,
    auth: str,
    user_agent: str = "",
) -> dict[str, Any]:
    """Insert or replace a push subscription for the endpoint."""
    _ensure_tables(conn)
    subject = (user_id or "").strip()
    ep = (endpoint or "").strip()
    key = (p256dh or "").strip()
    secret = (auth or "").strip()
    ua = (user_agent or "").strip()[:500]
    if not subject or not ep or not key or not secret:
        raise ValueError("endpoint, keys.p256dh, and keys.auth are required")
    if len(ep) > 2048 or len(key) > 256 or len(secret) > 256:
        raise ValueError("subscription fields too long")
    conn.execute(
        """
        INSERT INTO push_subscriptions (
            user_id, endpoint, p256dh, auth, user_agent, created_at
        ) VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(endpoint) DO UPDATE SET
            user_id = excluded.user_id,
            p256dh = excluded.p256dh,
            auth = excluded.auth,
            user_agent = excluded.user_agent
        """,
        (subject, ep, key, secret, ua, _now()),
    )
    return {
        "endpoint": ep,
        "user_id": subject,
        "created_at": _now(),
    }


def delete_subscription(conn, *, user_id: str, endpoint: str) -> bool:
    """Delete a subscription owned by the user. Returns True if a row was removed."""
    _ensure_tables(conn)
    subject = (user_id or "").strip()
    ep = (endpoint or "").strip()
    if not subject or not ep:
        return False
    cur = conn.execute(
        "DELETE FROM push_subscriptions WHERE user_id = ? AND endpoint = ?",
        (subject, ep),
    )
    return int(cur.rowcount or 0) > 0


def delete_endpoint(conn, *, endpoint: str) -> None:
    """Remove a subscription by endpoint (410/404 cleanup; any owner)."""
    _ensure_tables(conn)
    ep = (endpoint or "").strip()
    if not ep:
        return
    conn.execute("DELETE FROM push_subscriptions WHERE endpoint = ?", (ep,))


def list_subscriptions(conn, *, user_id: str) -> list[dict[str, Any]]:
    _ensure_tables(conn)
    subject = (user_id or "").strip()
    if not subject:
        return []
    rows = conn.execute(
        """
        SELECT endpoint, p256dh, auth, user_agent, created_at
        FROM push_subscriptions
        WHERE user_id = ?
        ORDER BY created_at DESC
        """,
        (subject,),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        out.append(
            {
                "endpoint": row[0],
                "p256dh": row[1],
                "auth": row[2],
                "user_agent": row[3] or "",
                "created_at": row[4] or "",
            }
        )
    return out


def _response_status(exc: BaseException) -> int | None:
    response = getattr(exc, "response", None)
    if response is None:
        return None
    for attr in ("status_code", "status"):
        value = getattr(response, attr, None)
        if value is None:
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return None


def send_web_push(
    conn,
    *,
    user_id: str,
    title: str,
    body: str,
    url: str = "",
    tag: str = "",
) -> dict[str, Any]:
    """Fan out a notification to all subscriptions for the user.

    HTTP 404/410 responses delete the subscription row. Other errors are logged;
    in-app/email success is independent.
    """
    result: dict[str, Any] = {"sent": 0, "failed": 0, "cleaned": 0}
    if not vapid_configured():
        result["skipped_reason"] = "vapid_not_configured"
        return result

    subs = list_subscriptions(conn, user_id=user_id)
    if not subs:
        result["skipped_reason"] = "no_subscriptions"
        return result

    try:
        from pywebpush import WebPushException, webpush
    except ImportError:
        logger.warning("pywebpush not installed; skipping web push")
        result["skipped_reason"] = "pywebpush_missing"
        return result

    payload = json.dumps(
        {
            "title": (title or "").strip() or "Ingress Job",
            "body": (body or "").strip(),
            "url": (url or "").strip() or "/",
            "tag": (tag or "").strip() or "ingress-job",
        },
        ensure_ascii=False,
    )
    claims = {"sub": vapid_subject()}
    private_key = vapid_private_key()

    for sub in subs:
        endpoint = sub["endpoint"]
        info = {
            "endpoint": endpoint,
            "keys": {"p256dh": sub["p256dh"], "auth": sub["auth"]},
        }
        try:
            webpush(
                subscription_info=info,
                data=payload,
                vapid_private_key=private_key,
                vapid_claims=claims,
            )
            result["sent"] += 1
        except Exception as exc:
            status = _response_status(exc)
            gone = status in (404, 410)
            if not gone and isinstance(exc, WebPushException):
                # Some pywebpush versions encode status in the message only.
                msg = str(exc)
                gone = "410" in msg or "404" in msg
            if gone:
                delete_endpoint(conn, endpoint=endpoint)
                result["cleaned"] += 1
                logger.info(
                    "push subscription gone (%s); removed %s",
                    status or "?",
                    endpoint[:80],
                )
            else:
                result["failed"] += 1
                logger.warning(
                    "web push failed for %s: %s",
                    endpoint[:80],
                    exc,
                )

    return result
