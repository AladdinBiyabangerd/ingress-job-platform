"""In-site notifications and a separate job-platform email.

Mail uses the same SMTP variable names as ingress-academy. When EMAIL_HOST is
unset, or the recipient has no address, the in-site row is still kept and the
request does not fail. The message is not a reply on an Academy thread.
"""

from __future__ import annotations

import logging
import os
import re
import smtplib
from email.message import EmailMessage
from email.utils import formataddr

from app.cabinet_store import _connect, _now
from app.engagement import dump_payload, parse_payload
from app.profiles import contact_email_for

logger = logging.getLogger("ingress-job.mail")

KINDS = {
    "application_new",
    "application_seen",
    "application_rejected",
    "ad_approved",
    "ad_rejected",
    "ad_review",
    "match_new",
    "match_near",
    "profile_nudge",
    "coach_weekly",
}
_REASON_KINDS = {"application_rejected", "ad_rejected"}
_ADDR = re.compile(r"<([^<>@\s]+@[^<>@\s]+)>")
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

_COPY = {
    "az": {
        "application_new": (
            "Yeni müraciət: {title}",
            "«{title}» elanına Ingress Job saytında yeni müraciət gəldi.",
        ),
        "application_seen": (
            "Müraciətinizə baxıldı: {title}",
            "«{title}» elanına Ingress Job saytında göndərdiyiniz müraciətə baxıldı.",
        ),
        "application_rejected": (
            "Müraciətiniz rədd edildi: {title}",
            "«{title}» elanına Ingress Job saytında göndərdiyiniz müraciət rədd edildi.",
        ),
        "ad_approved": (
            "Elanınız təsdiqləndi: {title}",
            "«{title}» elanınız Ingress Job saytında təsdiqləndi və dərc olundu.",
        ),
        "ad_rejected": (
            "Elanınız rədd edildi: {title}",
            "«{title}» elanınız Ingress Job saytında rədd edildi.",
        ),
        "ad_review": (
            "Elanınız yenidən moderasiyadadır: {title}",
            "«{title}» elanınız mühüm dəyişiklikdən sonra Ingress Job saytında yenidən moderasiyadadır.",
        ),
        "match_new": (
            "Sənə uyğun yeni elan: {title}",
            "«{title}» elanı profilinə uyğundur. Bax və müraciət et.",
        ),
        "match_near": (
            "Yaxın elan — skill artır: {title}",
            "«{title}» elanı yaxındır. Çatışmayan skill-ləri artırsan, bu elanı tövsiyə edirəm.",
        ),
        "profile_nudge": (
            "Profilini tamamla",
            "CV və skill-lərini doldur ki, sənə uyğun elanları tapa bilək.",
        ),
        "coach_weekly": (
            "Bu həftənin öyrənmə planı",
            "Rolun üçün qısa plan hazırdır — güclü tərəflər və öyrəniləcək skill-lər.",
        ),
        "reason": "Səbəb: {reason}",
    },
    "en": {
        "application_new": (
            "New application: {title}",
            "A new application arrived on Ingress Job for «{title}».",
        ),
        "application_seen": (
            "Your application was seen: {title}",
            "Your application on Ingress Job for «{title}» was marked as seen.",
        ),
        "application_rejected": (
            "Your application was rejected: {title}",
            "Your application on Ingress Job for «{title}» was rejected.",
        ),
        "ad_approved": (
            "Your ad was approved: {title}",
            "Your ad «{title}» was approved and published on Ingress Job.",
        ),
        "ad_rejected": (
            "Your ad was rejected: {title}",
            "Your ad «{title}» was rejected on Ingress Job.",
        ),
        "ad_review": (
            "Your ad is back in review: {title}",
            "Your published ad «{title}» went back to review on Ingress Job after a significant edit.",
        ),
        "match_new": (
            "New match for you: {title}",
            "«{title}» looks like a strong fit. Open it and apply.",
        ),
        "match_near": (
            "Almost a match — grow a skill: {title}",
            "«{title}» is close. Level up the missing skills and I will recommend this role.",
        ),
        "profile_nudge": (
            "Complete your profile",
            "Fill in your CV and skills so we can find matching jobs for you.",
        ),
        "coach_weekly": (
            "This week’s learning plan",
            "A short plan for your target role — strengths and skills to learn.",
        ),
        "reason": "Reason: {reason}",
    },
    "ru": {
        "application_new": (
            "Новый отклик: {title}",
            "На Ingress Job по объявлению «{title}» пришёл новый отклик.",
        ),
        "application_seen": (
            "Ваш отклик просмотрен: {title}",
            "Ваш отклик на Ingress Job по объявлению «{title}» отмечен как просмотренный.",
        ),
        "application_rejected": (
            "Ваш отклик отклонён: {title}",
            "Ваш отклик на Ingress Job по объявлению «{title}» отклонён.",
        ),
        "ad_approved": (
            "Ваше объявление одобрено: {title}",
            "Объявление «{title}» одобрено и опубликовано на Ingress Job.",
        ),
        "ad_rejected": (
            "Ваше объявление отклонено: {title}",
            "Объявление «{title}» отклонено на Ingress Job.",
        ),
        "ad_review": (
            "Ваше объявление снова на модерации: {title}",
            "Опубликованное объявление «{title}» снова на модерации Ingress Job после существенной правки.",
        ),
        "match_new": (
            "Новое совпадение: {title}",
            "«{title}» хорошо подходит под ваш профиль. Откройте и откликнитесь.",
        ),
        "match_near": (
            "Почти совпадение — прокачайте навык: {title}",
            "«{title}» близко. Подтяните недостающие навыки — и я порекомендую эту вакансию.",
        ),
        "profile_nudge": (
            "Заполните профиль",
            "Добавьте CV и навыки, чтобы мы могли находить подходящие вакансии.",
        ),
        "coach_weekly": (
            "План обучения на эту неделю",
            "Краткий план по вашей роли — сильные стороны и навыки для роста.",
        ),
        "reason": "Причина: {reason}",
    },
}


def env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or not str(raw).strip():
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _language(value: str) -> str:
    text = (value or "").strip().lower()
    return text if text in _COPY else "az"


def _reason(kind: str, reason: str) -> str:
    text = " ".join((reason or "").split())
    if kind not in _REASON_KINDS or not text:
        return ""
    return text[:400]


def insert_notification(
    conn,
    *,
    recipient: str,
    kind: str,
    job_id: int | None,
    job_title: str,
    application_id: int | None,
    status: str,
    reason: str,
    language: str,
    payload: dict | None = None,
) -> dict | None:
    subject = (recipient or "").strip()
    if not subject or kind not in KINDS:
        return None
    reason_text = _reason(kind, reason)
    lang = _language(language)
    title = (job_title or "").strip()
    payload_text = dump_payload(payload)
    cur = conn.execute(
        """
        INSERT INTO notifications (
            recipient_subject, kind, job_id, job_title, application_id,
            status, reason, language, read_at, created_at, payload
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, '', ?, ?)
        """,
        (
            subject,
            kind,
            job_id,
            title,
            application_id,
            (status or "").strip(),
            reason_text,
            lang,
            _now(),
            payload_text,
        ),
    )
    out = {
        "id": int(cur.lastrowid),
        "recipient": subject,
        "kind": kind,
        "job_id": job_id,
        "job_title": title,
        "application_id": application_id,
        "status": (status or "").strip(),
        "reason": reason_text,
        "language": lang,
    }
    parsed = parse_payload(payload_text)
    if parsed:
        out["payload"] = parsed
    return out


def _row_keys(row) -> set:
    try:
        return set(row.keys())
    except Exception:
        return set()


def _view(row) -> dict:
    payload = {
        "id": int(row["id"]),
        "kind": row["kind"] or "",
        "job_id": None if row["job_id"] is None else int(row["job_id"]),
        "job_title": row["job_title"] or "",
        "application_id": None if row["application_id"] is None else int(row["application_id"]),
        "status": row["status"] or "",
        "read": bool((row["read_at"] or "").strip()),
        "created_at": row["created_at"] or "",
    }
    reason = (row["reason"] or "").strip()
    if reason:
        payload["reason"] = reason
    keys = _row_keys(row)
    if "payload" in keys:
        parsed = parse_payload(row["payload"] if "payload" in keys else "")
        if parsed:
            payload["payload"] = parsed
    return payload


def unread_count_on(conn, subject: str) -> int:
    row = conn.execute(
        """
        SELECT COUNT(*) FROM notifications
        WHERE recipient_subject = ? AND read_at = ''
        """,
        (subject,),
    ).fetchone()
    return int((row[0] if row else 0) or 0)


def unread_count(subject: str) -> int:
    """Cheap badge count for /me; avoids loading the full notification list."""
    conn = _connect()
    try:
        return unread_count_on(conn, subject)
    finally:
        conn.close()


def list_for(subject: str) -> dict:
    conn = _connect()
    try:
        rows = conn.execute(
            """
            SELECT id, kind, job_id, job_title, application_id, status, reason,
                   read_at, created_at, payload
            FROM notifications
            WHERE recipient_subject = ?
            ORDER BY id DESC
            """,
            (subject,),
        ).fetchall()
        unread = sum(1 for row in rows if not (row["read_at"] or "").strip())
    finally:
        conn.close()
    return {"unread": unread, "items": [_view(row) for row in rows]}


def mark_read(subject: str, notification_id: int) -> dict | None:
    conn = _connect()
    try:
        row = conn.execute(
            """
            SELECT id, kind, job_id, job_title, application_id, status, reason,
                   read_at, created_at, payload
            FROM notifications
            WHERE id = ? AND recipient_subject = ?
            """,
            (notification_id, subject),
        ).fetchone()
        if row is None:
            return None
        if not (row["read_at"] or "").strip():
            conn.execute(
                "UPDATE notifications SET read_at = ? WHERE id = ? AND recipient_subject = ?",
                (_now(), notification_id, subject),
            )
            conn.commit()
            row = conn.execute(
                """
                SELECT id, kind, job_id, job_title, application_id, status, reason,
                       read_at, created_at, payload
                FROM notifications
                WHERE id = ? AND recipient_subject = ?
                """,
                (notification_id, subject),
            ).fetchone()
    finally:
        conn.close()
    return _view(row)


def mark_all_read(subject: str) -> dict:
    conn = _connect()
    try:
        conn.execute(
            """
            UPDATE notifications
            SET read_at = ?
            WHERE recipient_subject = ? AND read_at = ''
            """,
            (_now(), subject),
        )
        conn.commit()
    finally:
        conn.close()
    return {"unread": 0}


def _from_address() -> str:
    raw = (os.environ.get("DEFAULT_FROM_EMAIL") or os.environ.get("EMAIL_HOST_USER") or "").strip()
    wrapped = _ADDR.search(raw)
    if wrapped:
        raw = wrapped.group(1).strip()
    if not raw or " " in raw or not _EMAIL.fullmatch(raw):
        return ""
    return raw


def _recipient(note: dict, fallback: str) -> str:
    stored = contact_email_for(note.get("recipient") or "")
    chosen = stored or (fallback or "").strip().lower()
    if not chosen or len(chosen) > 120 or not _EMAIL.fullmatch(chosen):
        return ""
    return chosen


def render_email(note: dict) -> tuple[str, str]:
    lang = _language(note.get("language") or "")
    pack = _COPY[lang]
    kind = note.get("kind") or ""
    subject_t, body_t = pack[kind]
    title = note.get("job_title") or ""
    subject = subject_t.format(title=title)
    extra = note.get("payload") if isinstance(note.get("payload"), dict) else {}
    ai_title = str((extra or {}).get("ai_title") or "").strip()
    if ai_title:
        subject = ai_title
    ai_body = str((extra or {}).get("ai_body") or "").strip()
    body = ai_body if ai_body else body_t.format(title=title)
    reason = note.get("reason") or ""
    if reason:
        body = body + "\n\n" + pack["reason"].format(reason=reason)
    return subject, body


def send_email(*, to: str, subject: str, body: str) -> None:
    """Send one new message. Missing mail settings are a no-op, not an error."""
    host = (os.environ.get("EMAIL_HOST") or "").strip()
    if not host or not to:
        return
    address = _from_address()
    if not address:
        return
    try:
        port = int(os.environ.get("EMAIL_PORT") or "587")
        timeout = int(os.environ.get("EMAIL_TIMEOUT") or "20")
    except ValueError:
        logger.warning("notification email was not sent")
        return
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = formataddr(("Ingress Job", address))
    message["To"] = to
    message.set_content(body)
    user = os.environ.get("EMAIL_HOST_USER") or ""
    password = os.environ.get("EMAIL_HOST_PASSWORD") or ""
    use_ssl = env_bool("EMAIL_USE_SSL", False)
    use_tls = env_bool("EMAIL_USE_TLS", True)
    try:
        client = smtplib.SMTP_SSL(host, port, timeout=timeout) if use_ssl else smtplib.SMTP(host, port, timeout=timeout)
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
        logger.warning("notification email was not sent")


def deliver_email(note: dict | None, *, fallback_email: str = "") -> None:
    if not note:
        return
    try:
        to = _recipient(note, fallback_email)
        subject, body = render_email(note)
        send_email(to=to, subject=subject, body=body)
    except Exception:
        logger.warning("notification email was not sent")
