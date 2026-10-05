"""Weekly digests and high-match alerts (plan §8.1 / §8.4).

AI #4 optional personal intro via digest_intro (soft-fails to static copy).
Empty digests are not sent. At most one non-transactional email per user per UTC day.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from email.utils import formataddr
from typing import Any

from app.email_prefs import (
    already_logged,
    day_key,
    digest_enabled,
    ensure_email_tables,
    get_prefs,
    high_match_enabled,
    list_candidate_user_ids,
    log_email,
    marketing_sent_today,
    period_key_for_digest,
    unsubscribe_url,
)
logger = logging.getLogger("ingress-job.digests")

HIGH_MATCH_MIN_SCORE = float(os.environ.get("HIGH_MATCH_MIN_SCORE") or "0.75")
DIGEST_MATCH_LIMIT = 5
HIGH_MATCH_LOOKBACK_HOURS = int(os.environ.get("HIGH_MATCH_LOOKBACK_HOURS") or "26")
BATCH_PAUSE_EVERY = int(os.environ.get("DIGEST_BATCH_SIZE") or "30")

COPY = {
    "az": {
        "digest_subject": "Ingress Job: bu həftənin uyğun elanları",
        "digest_intro": "Profilinizə uyğun yeni elanlar:",
        "digest_trends": "Bacarıq trendləri:",
        "digest_gap": "Öyrənmə tövsiyəsi:",
        "digest_empty_skip": "empty",
        "high_subject": "Yüksək uyğunluq: {title}",
        "high_body": "Yeni elan «{title}» ({company}) profilinizə yaxşı uyğun gəlir (skor {score}%).\n{explanation}\n\nBaxın: {url}",
        "unsub": "Abunəlikdən çıxmaq: {url}",
        "footer": "Ingress Job",
    },
    "en": {
        "digest_subject": "Ingress Job: matches for you this period",
        "digest_intro": "New jobs that fit your profile:",
        "digest_trends": "Skill trends:",
        "digest_gap": "Learning tip:",
        "digest_empty_skip": "empty",
        "high_subject": "Strong match: {title}",
        "high_body": "New job «{title}» ({company}) looks like a strong match (score {score}%).\n{explanation}\n\nView: {url}",
        "unsub": "Unsubscribe: {url}",
        "footer": "Ingress Job",
    },
    "ru": {
        "digest_subject": "Ingress Job: подходящие вакансии за период",
        "digest_intro": "Новые вакансии под ваш профиль:",
        "digest_trends": "Тренды навыков:",
        "digest_gap": "Совет по обучению:",
        "digest_empty_skip": "empty",
        "high_subject": "Сильное совпадение: {title}",
        "high_body": "Новая вакансия «{title}» ({company}) хорошо совпадает с профилем (оценка {score}%).\n{explanation}\n\nСмотреть: {url}",
        "unsub": "Отписаться: {url}",
        "footer": "Ingress Job",
    },
}


def _lang(value: str) -> str:
    text = (value or "").strip().lower()[:2]
    return text if text in COPY else "az"


def _since_for_frequency(frequency: str, *, when: datetime) -> datetime:
    if frequency == "biweekly":
        return when - timedelta(days=14)
    return when - timedelta(days=7)


def _weekday_iso(when: datetime) -> int:
    return when.weekday()  # Mon=0


def _due_for_digest(prefs: dict, *, when: datetime) -> bool:
    if not digest_enabled(prefs):
        return False
    if int(prefs.get("send_weekday") or 0) != _weekday_iso(when):
        return False
    return True


def _recipient(user_id: str) -> str:
    from app.profiles import contact_email_for

    return (contact_email_for(user_id) or "").strip().lower()


def _matches_since(conn, *, user_id: str, since: datetime, limit: int, lang: str) -> list[dict]:
    from app.matching import matches_payload

    payload = matches_payload(conn, user_id=user_id, limit=max(limit, 20), lang=lang)
    if not payload.get("matching_consent"):
        return []
    items = payload.get("matches") or []
    since_key = since.date().isoformat()
    fresh: list[dict] = []
    for item in items:
        created = str(item.get("created_at") or "")[:10]
        if created and created >= since_key:
            fresh.append(item)
        if len(fresh) >= limit:
            break
    return fresh


def _trend_lines(conn, *, category: str, lang: str, limit: int = 2) -> list[str]:
    from app.trends import trends_payload

    payload = trends_payload(conn, category=category or "", limit=limit, lang=lang)
    lines: list[str] = []
    for item in payload.get("items") or []:
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        share = item.get("share")
        growth = item.get("growth_wow")
        bits = [name]
        if isinstance(share, (int, float)):
            bits.append(f"{round(share * 100)}%")
        if isinstance(growth, (int, float)):
            bits.append(f"{'+' if growth >= 0 else ''}{round(growth * 100)}%")
        lines.append(" · ".join(bits))
    return lines


def _gap_tip(conn, *, user_id: str, lang: str) -> str:
    from app.role_suggestions import suggest_roles_payload
    from app.skill_gap import skill_gap_payload

    roles = suggest_roles_payload(conn, user_id=user_id, limit=1, lang=lang)
    top = (roles.get("roles") or [None])[0]
    if not top:
        return ""
    role_name = str(top.get("canonical_name") or "").strip()
    if not role_name:
        return ""
    gap = skill_gap_payload(conn, user_id=user_id, role=role_name, top=3, lang=lang)
    missing = gap.get("missing") or []
    if not missing:
        return ""
    tip = missing[0]
    name = str(tip.get("name") or "").strip()
    if not name:
        return ""
    courses = tip.get("academy_courses") or []
    if courses:
        return f"{name} → {courses[0]}"
    return name


def _build_digest_body(
    *,
    user_id: str,
    lang: str,
    matches: list[dict],
    trends: list[str],
    gap: str,
    unsub: str,
    ai_intro: str | None = None,
) -> str:
    from app.email_clicks import tracked_job_url

    pack = COPY[_lang(lang)]
    intro = (ai_intro or "").strip() or pack["digest_intro"]
    lines = [intro, ""]
    for item in matches:
        title = item.get("title") or ""
        company = item.get("company") or ""
        score = item.get("score")
        score_pct = f"{round(float(score) * 100)}%" if isinstance(score, (int, float)) else ""
        url = tracked_job_url(
            user_id,
            job_id=int(item["job_id"]),
            kind="digest",
            lang=lang,
        )
        lines.append(f"- {title} ({company}) {score_pct}".rstrip())
        if item.get("explanation"):
            lines.append(f"  {item['explanation']}")
        lines.append(f"  {url}")
        lines.append("")
    if trends:
        lines.append(pack["digest_trends"])
        for row in trends:
            lines.append(f"- {row}")
        lines.append("")
    if gap:
        lines.append(f"{pack['digest_gap']} {gap}")
        lines.append("")
    lines.append(pack["unsub"].format(url=unsub))
    lines.append(pack["footer"])
    return "\n".join(lines).strip() + "\n"


def send_marketing_email(
    *,
    to: str,
    subject: str,
    body: str,
    unsubscribe_link: str,
) -> None:
    """Like notifications.send_email, plus List-Unsubscribe headers."""
    host = (os.environ.get("EMAIL_HOST") or "").strip()
    if not host or not to:
        return
    from app.notifications import _from_address, env_bool
    import smtplib

    address = _from_address()
    if not address:
        return
    try:
        port = int(os.environ.get("EMAIL_PORT") or "587")
        timeout = int(os.environ.get("EMAIL_TIMEOUT") or "20")
    except ValueError:
        logger.warning("digest email was not sent")
        return
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = formataddr(("Ingress Job", address))
    message["To"] = to
    if unsubscribe_link:
        message["List-Unsubscribe"] = f"<{unsubscribe_link}>"
        message["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
    message.set_content(body)
    user = os.environ.get("EMAIL_HOST_USER") or ""
    password = os.environ.get("EMAIL_HOST_PASSWORD") or ""
    use_ssl = env_bool("EMAIL_USE_SSL", False)
    use_tls = env_bool("EMAIL_USE_TLS", True)
    try:
        client = (
            smtplib.SMTP_SSL(host, port, timeout=timeout)
            if use_ssl
            else smtplib.SMTP(host, port, timeout=timeout)
        )
        try:
            if not use_ssl and use_tls:
                client.starttls()
            if user:
                client.login(user, password)
            client.send_message(message)
        finally:
            try:
                client.quit()
            except Exception:
                pass
    except Exception:
        logger.warning("digest email was not sent")


def send_digest_for_user(conn, *, user_id: str, when: datetime | None = None) -> dict[str, Any]:
    ensure_email_tables(conn)
    moment = when or datetime.now(timezone.utc)
    prefs = get_prefs(conn, user_id)
    result: dict[str, Any] = {"user_id": user_id, "kind": "digest", "status": "skipped"}
    if not _due_for_digest(prefs, when=moment):
        result["reason"] = "not_due"
        return result
    frequency = prefs["frequency"]
    period = period_key_for_digest(when=moment, frequency=frequency)
    if already_logged(conn, user_id=user_id, kind="digest", period_key=period):
        result["reason"] = "already_sent"
        return result
    if marketing_sent_today(conn, user_id=user_id, day=day_key(when=moment)):
        result["reason"] = "daily_limit"
        return result
    to = _recipient(user_id)
    if not to:
        result["reason"] = "no_email"
        return result
    lang = prefs["language"]
    since = _since_for_frequency(frequency, when=moment)
    matches = _matches_since(conn, user_id=user_id, since=since, limit=DIGEST_MATCH_LIMIT, lang=lang)
    if not matches:
        result["reason"] = "empty"
        return result
    category = ""
    try:
        from app.role_suggestions import suggest_roles_payload

        roles = suggest_roles_payload(conn, user_id=user_id, limit=1, lang=lang)
        top = (roles.get("roles") or [None])[0]
        if top:
            category = str(top.get("category") or "")
    except Exception:
        category = ""
    trends = _trend_lines(conn, category=category, lang=lang)
    gap = _gap_tip(conn, user_id=user_id, lang=lang)
    unsub = unsubscribe_url(user_id, lang=lang)
    pack = COPY[_lang(lang)]
    from app.digest_intro import maybe_digest_intro

    ai_intro, ai_status = maybe_digest_intro(
        conn,
        user_id=user_id,
        lang=lang,
        matches=matches,
        trends=trends,
        gap=gap,
    )
    body = _build_digest_body(
        user_id=user_id,
        lang=lang,
        matches=matches,
        trends=trends,
        gap=gap,
        unsub=unsub,
        ai_intro=ai_intro,
    )
    if not log_email(
        conn,
        user_id=user_id,
        kind="digest",
        period_key=period,
        to_email=to,
        status="sent",
        meta=json.dumps(
            {"match_count": len(matches), "ai_intro": ai_status},
            ensure_ascii=False,
        ),
    ):
        result["reason"] = "already_sent"
        return result
    send_marketing_email(
        to=to,
        subject=pack["digest_subject"],
        body=body,
        unsubscribe_link=unsub,
    )
    result["status"] = "sent"
    result["period_key"] = period
    result["match_count"] = len(matches)
    result["ai_intro"] = ai_status
    return result


def send_high_match_for_user(conn, *, user_id: str, when: datetime | None = None) -> dict[str, Any]:
    ensure_email_tables(conn)
    moment = when or datetime.now(timezone.utc)
    prefs = get_prefs(conn, user_id)
    result: dict[str, Any] = {"user_id": user_id, "kind": "high_match", "status": "skipped"}
    if not high_match_enabled(prefs):
        result["reason"] = "disabled"
        return result
    if marketing_sent_today(conn, user_id=user_id, day=day_key(when=moment)):
        result["reason"] = "daily_limit"
        return result
    to = _recipient(user_id)
    if not to:
        result["reason"] = "no_email"
        return result
    lang = prefs["language"]
    since = moment - timedelta(hours=HIGH_MATCH_LOOKBACK_HOURS)
    matches = _matches_since(conn, user_id=user_id, since=since, limit=10, lang=lang)
    best = None
    for item in matches:
        score = item.get("score")
        if not isinstance(score, (int, float)):
            continue
        if float(score) < HIGH_MATCH_MIN_SCORE:
            continue
        best = item
        break
    if best is None:
        result["reason"] = "none"
        return result
    job_id = int(best["job_id"])
    period = f"{day_key(when=moment)}:{job_id}"
    if already_logged(conn, user_id=user_id, kind="high_match", period_key=period):
        result["reason"] = "already_sent"
        return result
    # One high-match alert per UTC day.
    day = day_key(when=moment)
    row = conn.execute(
        """
        SELECT 1 FROM email_log
        WHERE user_id = ? AND kind = 'high_match' AND status = 'sent'
          AND period_key LIKE ?
        LIMIT 1
        """,
        (user_id, f"{day}:%"),
    ).fetchone()
    if row is not None:
        result["reason"] = "daily_alert_limit"
        return result
    from app.email_clicks import tracked_job_url

    pack = COPY[_lang(lang)]
    unsub = unsubscribe_url(user_id, lang=lang)
    score_pct = round(float(best["score"]) * 100)
    url = tracked_job_url(user_id, job_id=job_id, kind="high_match", lang=lang)
    subject = pack["high_subject"].format(title=best.get("title") or "")
    body = pack["high_body"].format(
        title=best.get("title") or "",
        company=best.get("company") or "",
        score=score_pct,
        explanation=best.get("explanation") or "",
        url=url,
    )
    body = body + "\n\n" + pack["unsub"].format(url=unsub) + "\n" + pack["footer"] + "\n"
    if not log_email(
        conn,
        user_id=user_id,
        kind="high_match",
        period_key=period,
        to_email=to,
        status="sent",
        meta=json.dumps({"job_id": job_id, "score": best.get("score")}, ensure_ascii=False),
    ):
        result["reason"] = "already_sent"
        return result
    send_marketing_email(to=to, subject=subject, body=body, unsubscribe_link=unsub)
    result["status"] = "sent"
    result["job_id"] = job_id
    result["period_key"] = period
    return result


def run_email_jobs(*, dry_run: bool = False) -> dict[str, Any]:
    """Process digests + high-match alerts for all eligible users."""
    from app.cabinet_store import _LOCK, _connect, ensure_schema

    ensure_schema(create=True)
    when = datetime.now(timezone.utc)
    stats = {
        "digest_sent": 0,
        "digest_skipped": 0,
        "high_match_sent": 0,
        "high_match_skipped": 0,
        "users": 0,
        "dry_run": dry_run,
    }
    with _LOCK:
        conn = _connect()
        try:
            ensure_email_tables(conn)
            users = list_candidate_user_ids(conn)
            stats["users"] = len(users)
            for index, user_id in enumerate(users):
                if dry_run:
                    prefs = get_prefs(conn, user_id)
                    if _due_for_digest(prefs, when=when):
                        stats["digest_skipped"] += 1
                    if high_match_enabled(prefs):
                        stats["high_match_skipped"] += 1
                    continue
                digest_result = send_digest_for_user(conn, user_id=user_id, when=when)
                if digest_result.get("status") == "sent":
                    stats["digest_sent"] += 1
                else:
                    stats["digest_skipped"] += 1
                # High-match only if digest did not already consume the daily slot.
                high_result = send_high_match_for_user(conn, user_id=user_id, when=when)
                if high_result.get("status") == "sent":
                    stats["high_match_sent"] += 1
                else:
                    stats["high_match_skipped"] += 1
                if BATCH_PAUSE_EVERY > 0 and (index + 1) % BATCH_PAUSE_EVERY == 0:
                    conn.commit()
            conn.commit()
        finally:
            conn.close()
    return stats
