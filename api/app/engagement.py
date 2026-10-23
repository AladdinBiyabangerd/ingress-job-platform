"""Engagement notifications: match + nudge + coach selection + fanout.

Phase 1 owned DDL + dedup. Phase 2 adds hourly match_new/near selection, Academy/roadmap CTA,
in-app + email fanout (high_match email merged into match_new), and run_engagement_jobs.
Phase 3 resolves title/body via engagement_copy (AI or soft-fail templates) into payload.
Phase 4 adds profile_nudge + coach_weekly senders and /me/insights payload helper.
Phase 5 fans out Web Push when push_enabled + subscriptions (VAPID / pywebpush).

Match selection prefers ads created within ENGAGEMENT_LOOKBACK_HOURS (default 72).
When none qualify, falls back to best current catalog matches not yet logged for that
kind (in-app + push only — email stays fresh-only) so confirmed users are not silent.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger("ingress-job.engagement")

ENGAGEMENT_KINDS = frozenset(
    {
        "match_new",
        "match_near",
        "profile_nudge",
        "coach_weekly",
    }
)

MARKETING_EMAIL_KINDS = frozenset(
    {
        "digest",
        "high_match",
        "profile_nudge",
        "match_near",
        "coach_weekly",
    }
)

MATCH_ENGINE_KINDS = frozenset({"match_new", "match_near"})

NEAR_MISS_MIN_SCORE = float(os.environ.get("NEAR_MISS_MIN_SCORE") or "0.45")
NEAR_MISS_MAX_MISSING = int(os.environ.get("NEAR_MISS_MAX_MISSING") or "3")
ENGAGEMENT_INAPP_DAILY_MAX = int(os.environ.get("ENGAGEMENT_INAPP_DAILY_MAX") or "3")
ENGAGEMENT_LOOKBACK_HOURS = int(
    os.environ.get("ENGAGEMENT_LOOKBACK_HOURS")
    or os.environ.get("HIGH_MATCH_LOOKBACK_HOURS")
    or "72"
)
PROFILE_NUDGE_STALE_DAYS = int(os.environ.get("PROFILE_NUDGE_STALE_DAYS") or "14")
PROFILE_NUDGE_MIN_SKILLS = int(os.environ.get("PROFILE_NUDGE_MIN_SKILLS") or "3")

SCHEMA = """
CREATE TABLE IF NOT EXISTS engagement_log (
    id INTEGER PRIMARY KEY,
    user_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    period_key TEXT NOT NULL,
    job_id INTEGER NOT NULL DEFAULT 0,
    channels TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    UNIQUE (user_id, kind, period_key, job_id)
);

CREATE INDEX IF NOT EXISTS engagement_log_user_created
    ON engagement_log(user_id, created_at);

CREATE TABLE IF NOT EXISTS push_subscriptions (
    id INTEGER PRIMARY KEY,
    user_id TEXT NOT NULL,
    endpoint TEXT NOT NULL UNIQUE,
    p256dh TEXT NOT NULL,
    auth TEXT NOT NULL,
    user_agent TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS push_sub_user ON push_subscriptions(user_id);
"""

# Kept for locale validation + email fallback; rich steps live in learning_roadmap.
ROADMAP_STEPS = {
    "az": (
        "Əsas anlayışları və rəsmi sənədləri öyrən",
        "Kiçik layihədə və ya lab-da tətbiq et",
        "Nəticəni CV və müraciətdə göstər",
    ),
    "en": (
        "Learn the core concepts and official docs",
        "Practice in a small project or lab",
        "Show the result on your CV and applications",
    ),
    "ru": (
        "Изучите основы и официальную документацию",
        "Закрепите на небольшом проекте или в лаборатории",
        "Покажите результат в CV и откликах",
    ),
}

NEAR_EMAIL_COPY = {
    "az": {
        "subject": "Yaxın elan — skill artır: {title}",
        "body": (
            "«{title}» ({company}) profilinizə yaxındır (skor {score}%).\n"
            "{explanation}\n"
            "{growth}\n\n"
            "Elanı görüntüləmək üçün məktubdakı düyməyə klikləyin."
        ),
        "growth_academy": "Öyrən: {skills}",
        "growth_roadmap": "Öyrənmə yolu: {skills}",
    },
    "en": {
        "subject": "Almost a match — grow a skill: {title}",
        "body": (
            "«{title}» ({company}) is close to your profile (score {score}%).\n"
            "{explanation}\n"
            "{growth}\n\n"
            "Open the job with the button in this email."
        ),
        "growth_academy": "Learn: {skills}",
        "growth_roadmap": "Learning path: {skills}",
    },
    "ru": {
        "subject": "Почти совпадение — подтяните навык: {title}",
        "body": (
            "«{title}» ({company}) близко к вашему профилю (оценка {score}%).\n"
            "{explanation}\n"
            "{growth}\n\n"
            "Откройте вакансию кнопкой в этом письме."
        ),
        "growth_academy": "Учить: {skills}",
        "growth_roadmap": "План обучения: {skills}",
    },
}

NUDGE_EMAIL_COPY = {
    "az": {
        "subject": "Profilini tamamla — uyğun elanlar üçün",
        "body": (
            "Profiliniz natamamdır ({reason}).\n"
            "CV və skill-ləri doldurun ki, sənə uyğun elanları tapa bilək.\n\n"
            "Profilə keçid üçün məktubdakı düyməyə klikləyin."
        ),
    },
    "en": {
        "subject": "Complete your profile for better matches",
        "body": (
            "Your profile needs attention ({reason}).\n"
            "Add your CV and skills so we can find matching jobs.\n\n"
            "Open your profile with the button in this email."
        ),
    },
    "ru": {
        "subject": "Заполните профиль — для подходящих вакансий",
        "body": (
            "Профиль неполный ({reason}).\n"
            "Добавьте CV и навыки, чтобы мы могли находить совпадения.\n\n"
            "Откройте профиль кнопкой в этом письме."
        ),
    },
}

COACH_EMAIL_COPY = {
    "az": {
        "subject": "Bu həftənin planı: {role}",
        "body": (
            "Rol: {role}\n"
            "Öyrən: {must_learn}\n"
            "Güclü: {strong}\n"
            "{growth}\n\n"
            "Plana baxmaq üçün məktubdakı düyməyə klikləyin."
        ),
    },
    "en": {
        "subject": "This week’s plan: {role}",
        "body": (
            "Role: {role}\n"
            "Learn: {must_learn}\n"
            "Strong: {strong}\n"
            "{growth}\n\n"
            "Open the weekly plan with the button in this email."
        ),
    },
    "ru": {
        "subject": "План на неделю: {role}",
        "body": (
            "Роль: {role}\n"
            "Учить: {must_learn}\n"
            "Сильные: {strong}\n"
            "{growth}\n\n"
            "Откройте план кнопкой в этом письме."
        ),
    },
}

NUDGE_REASON_LABELS = {
    "az": {
        "draft": "qaralama",
        "empty_skills": "bacarıq yoxdur",
        "few_skills": "3-dən az bacarıq",
        "stale": "14 gündən çox yenilənməyib",
    },
    "en": {
        "draft": "still a draft",
        "empty_skills": "no skills yet",
        "few_skills": "fewer than 3 skills",
        "stale": "not updated in 14+ days",
    },
    "ru": {
        "draft": "ещё черновик",
        "empty_skills": "нет навыков",
        "few_skills": "меньше 3 навыков",
        "stale": "не обновлялся 14+ дней",
    },
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _lang(value: str | None) -> str:
    text = (value or "").strip().lower()[:2]
    return text if text in ROADMAP_STEPS else "az"


def ensure_engagement_tables(conn) -> None:
    conn.executescript(SCHEMA)


def job_key(job_id: int | None) -> int:
    try:
        value = int(job_id or 0)
    except (TypeError, ValueError):
        return 0
    return value if value > 0 else 0


def already_logged(
    conn,
    *,
    user_id: str,
    kind: str,
    period_key: str,
    job_id: int | None = None,
) -> bool:
    ensure_engagement_tables(conn)
    row = conn.execute(
        """
        SELECT 1 FROM engagement_log
        WHERE user_id = ? AND kind = ? AND period_key = ? AND job_id = ?
        """,
        ((user_id or "").strip(), kind, period_key, job_key(job_id)),
    ).fetchone()
    return row is not None


def job_ever_logged(
    conn,
    *,
    user_id: str,
    kind: str,
    job_id: int | None,
) -> bool:
    """True if this user already got this kind for this job (any period)."""
    ensure_engagement_tables(conn)
    jid = job_key(job_id)
    if jid <= 0:
        return False
    row = conn.execute(
        """
        SELECT 1 FROM engagement_log
        WHERE user_id = ? AND kind = ? AND job_id = ?
        LIMIT 1
        """,
        ((user_id or "").strip(), kind, jid),
    ).fetchone()
    return row is not None


def log_engagement(
    conn,
    *,
    user_id: str,
    kind: str,
    period_key: str,
    job_id: int | None = None,
    channels: list[str] | None = None,
) -> bool:
    """Insert dedup row. Returns False if the unique key already exists."""
    ensure_engagement_tables(conn)
    subject = (user_id or "").strip()
    if not subject or kind not in ENGAGEMENT_KINDS:
        return False
    payload = json.dumps(list(channels or []), ensure_ascii=False)
    try:
        conn.execute(
            """
            INSERT INTO engagement_log (
                user_id, kind, period_key, job_id, channels, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (subject, kind, period_key, job_key(job_id), payload, _now()),
        )
        return True
    except Exception:
        return False


def logged_channels(
    conn,
    *,
    user_id: str,
    kind: str,
    period_key: str,
    job_id: int | None = None,
) -> list[str] | None:
    """Channels already delivered for this engagement key, or None if no row."""
    ensure_engagement_tables(conn)
    row = conn.execute(
        """
        SELECT channels FROM engagement_log
        WHERE user_id = ? AND kind = ? AND period_key = ? AND job_id = ?
        """,
        ((user_id or "").strip(), kind, period_key, job_key(job_id)),
    ).fetchone()
    if row is None:
        return None
    raw = row["channels"] if hasattr(row, "keys") and "channels" in row.keys() else row[0]
    try:
        data = json.loads(raw or "[]")
    except (TypeError, ValueError):
        data = []
    return [str(x) for x in data] if isinstance(data, list) else []


def add_logged_channel(
    conn,
    *,
    user_id: str,
    kind: str,
    period_key: str,
    channel: str,
    job_id: int | None = None,
) -> None:
    current = logged_channels(
        conn, user_id=user_id, kind=kind, period_key=period_key, job_id=job_id
    )
    if current is None or channel in current:
        return
    conn.execute(
        """
        UPDATE engagement_log SET channels = ?
        WHERE user_id = ? AND kind = ? AND period_key = ? AND job_id = ?
        """,
        (
            json.dumps(current + [channel], ensure_ascii=False),
            (user_id or "").strip(),
            kind,
            period_key,
            job_key(job_id),
        ),
    )


# Engagement kind -> email_log kind (match_new mails are logged as high_match).
EMAIL_KIND_FOR = {
    "match_new": "high_match",
    "match_near": "match_near",
    "profile_nudge": "profile_nudge",
    "coach_weekly": "coach_weekly",
}


def _record_email_skip(conn, *, user_id: str, kind: str, reason: str, when: datetime) -> None:
    from app.email_prefs import record_skip

    record_skip(
        conn,
        user_id=user_id,
        kind=f"{EMAIL_KIND_FOR.get(kind, kind)}_email",
        reason=reason or "not_sent",
        when=when,
    )


def job_email_done(conn, *, user_id: str, job_id: int | None) -> bool:
    """True once this ad was emailed (high_match or match_near) — any day.

    Also true when the send failed EMAIL_SEND_MAX_ATTEMPTS times, so a broken
    address does not keep the same ad at the head of the queue forever.
    """
    from app.email_prefs import EMAIL_SEND_MAX_ATTEMPTS, ensure_email_tables

    jid = job_key(job_id)
    if jid <= 0:
        return False
    ensure_email_tables(conn)
    row = conn.execute(
        """
        SELECT 1 FROM email_log
        WHERE user_id = ? AND kind IN ('high_match', 'match_near')
          AND period_key LIKE ?
          AND (status = 'sent' OR (status = 'failed' AND attempts >= ?))
        LIMIT 1
        """,
        ((user_id or "").strip(), f"%:{jid}", EMAIL_SEND_MAX_ATTEMPTS),
    ).fetchone()
    return row is not None


def match_email_possible(
    conn,
    *,
    user_id: str,
    kind: str,
    prefs: dict[str, Any],
    when: datetime,
) -> bool:
    """Could a match email go out right now (prefs, daily cap, address)?"""
    from app.email_prefs import (
        day_key,
        high_match_enabled,
        marketing_sent_today,
        match_near_enabled,
    )

    enabled = high_match_enabled(prefs) if kind == "match_new" else match_near_enabled(prefs)
    if not enabled:
        return False
    if marketing_sent_today(conn, user_id=user_id, day=day_key(when=when)):
        return False
    return bool(_recipient(user_id))


def dump_payload(data: dict[str, Any] | None) -> str:
    if not data:
        return ""
    try:
        return json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    except (TypeError, ValueError):
        return ""


def parse_payload(raw: str | None) -> dict[str, Any]:
    text = (raw or "").strip()
    if not text:
        return {}
    try:
        data = json.loads(text)
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def period_key_for_job(*, when: datetime, job_id: int) -> str:
    from app.email_prefs import day_key

    return f"{day_key(when=when)}:{int(job_id)}"


def kind_sent_today(conn, *, user_id: str, kind: str, when: datetime) -> bool:
    """True if any engagement_log row for this kind exists for the UTC day."""
    from app.email_prefs import day_key

    ensure_engagement_tables(conn)
    day = day_key(when=when)
    row = conn.execute(
        """
        SELECT 1 FROM engagement_log
        WHERE user_id = ? AND kind = ? AND period_key LIKE ?
        LIMIT 1
        """,
        ((user_id or "").strip(), kind, f"{day}:%"),
    ).fetchone()
    return row is not None


def inapp_count_today(conn, *, user_id: str, when: datetime) -> int:
    from app.email_prefs import day_key

    ensure_engagement_tables(conn)
    day = day_key(when=when)
    kinds = tuple(sorted(ENGAGEMENT_KINDS))
    placeholders = ", ".join("?" for _ in kinds)
    row = conn.execute(
        f"""
        SELECT COUNT(*) FROM engagement_log
        WHERE user_id = ?
          AND kind IN ({placeholders})
          AND substr(created_at, 1, 10) = ?
          AND channels LIKE ?
        """,
        ((user_id or "").strip(), *kinds, day, "%in_app%"),
    ).fetchone()
    try:
        return int(row[0] if row else 0)
    except (TypeError, ValueError, IndexError):
        return 0


def list_engagement_user_ids(conn) -> list[str]:
    """Matching-consent candidates plus profile owners (nudge may not need matching)."""
    from app.consents import ensure_consent_tables
    from app.cv_profile import ensure_profile_tables

    ensure_consent_tables(conn)
    ensure_profile_tables(conn)
    try:
        rows = conn.execute(
            """
            SELECT DISTINCT user_id FROM (
                SELECT user_id FROM consent
                WHERE kind = 'matching' AND granted = 1
                UNION
                SELECT user_id FROM candidate_profile
            )
            """
        ).fetchall()
    except Exception:
        try:
            rows = conn.execute(
                """
                SELECT DISTINCT user_id FROM consent
                WHERE kind = 'matching' AND granted = 1
                """
            ).fetchall()
        except Exception:
            return []
    out: list[str] = []
    for row in rows:
        try:
            uid = row["user_id"] if "user_id" in row.keys() else row[0]
        except Exception:
            uid = row[0] if row else ""
        text = str(uid or "").strip()
        if text:
            out.append(text)
    return out


def week_period_key(*, when: datetime | None = None) -> str:
    moment = when or datetime.now(timezone.utc)
    iso = moment.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def _skill_count(profile_payload: dict[str, Any]) -> int:
    profile = profile_payload.get("profile") if isinstance(profile_payload.get("profile"), dict) else {}
    skills = profile.get("skills") if isinstance(profile.get("skills"), list) else []
    count = 0
    for item in skills:
        if isinstance(item, dict):
            name = str(item.get("name") or "").strip()
        else:
            name = str(item or "").strip()
        if name:
            count += 1
    return count


def _parse_updated_at(raw: object) -> datetime | None:
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        moment = datetime.fromisoformat(text)
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)


def profile_nudge_reasons(
    profile_payload: dict[str, Any],
    *,
    when: datetime | None = None,
) -> list[str]:
    """Return nudge reason codes; empty means profile is fine this week."""
    moment = when or datetime.now(timezone.utc)
    status = str(profile_payload.get("status") or "empty")
    exists = bool(profile_payload.get("exists"))
    skills_n = _skill_count(profile_payload) if exists else 0
    reasons: list[str] = []
    if not exists or status in {"draft", "empty"}:
        reasons.append("draft")
    if skills_n <= 0:
        reasons.append("empty_skills")
    elif skills_n < PROFILE_NUDGE_MIN_SKILLS:
        reasons.append("few_skills")
    updated = _parse_updated_at(profile_payload.get("updated_at"))
    if exists and status == "confirmed" and updated is not None:
        age = moment - updated
        if age >= timedelta(days=PROFILE_NUDGE_STALE_DAYS):
            reasons.append("stale")
    elif exists and status == "confirmed" and updated is None and skills_n < PROFILE_NUDGE_MIN_SKILLS:
        pass  # few_skills already covered
    return reasons


def needs_profile_nudge(profile_payload: dict[str, Any], *, when: datetime | None = None) -> bool:
    return bool(profile_nudge_reasons(profile_payload, when=when))


def _parse_course_ids(raw: object) -> list[str]:
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    text = str(raw or "").strip()
    if not text:
        return []
    try:
        data = json.loads(text)
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    if not isinstance(data, list):
        return []
    return [str(x).strip() for x in data if str(x).strip()]


def _academy_courses_for_skills(conn, skill_names: list[str]) -> list[dict[str, str]]:
    """Map missing skill names → first academy course slug/url (utm notification)."""
    from app.digests import academy_course_url

    names = [str(n or "").strip() for n in skill_names if str(n or "").strip()]
    if not names:
        return []
    lower_map = {n.lower(): n for n in names}
    try:
        rows = conn.execute(
            """
            SELECT canonical_name, academy_course_ids
            FROM skill_dictionary
            """
        ).fetchall()
    except Exception:
        return []
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in rows:
        try:
            cname = str(row["canonical_name"] if "canonical_name" in row.keys() else row[0] or "")
            raw_ids = row["academy_course_ids"] if "academy_course_ids" in row.keys() else row[1]
        except Exception:
            cname = str(row[0] or "") if row else ""
            raw_ids = row[1] if row and len(row) > 1 else "[]"
        key = cname.strip().lower()
        if key not in lower_map or key in seen:
            continue
        courses = _parse_course_ids(raw_ids)
        if not courses:
            continue
        slug = courses[0]
        href = academy_course_url(slug, utm_medium="notification")
        if not href:
            continue
        seen.add(key)
        out.append({"slug": slug, "url": href, "skill": lower_map[key]})
    # Preserve missing-skill order.
    ordered: list[dict[str, str]] = []
    for name in names:
        for item in out:
            if item["skill"].lower() == name.lower():
                ordered.append(item)
                break
    return ordered


def _career_path_for_user(conn, *, user_id: str, lang: str) -> dict[str, str]:
    from app.academy_paths import academy_career_path_url
    from app.role_suggestions import suggest_roles_payload

    roles = suggest_roles_payload(conn, user_id=user_id, limit=1, lang=lang)
    top = (roles.get("roles") or [None])[0]
    if not isinstance(top, dict):
        return {}
    path_id = str(
        top.get("academy_career_path") or top.get("academy_career_path_id") or ""
    ).strip()
    role_name = str(top.get("canonical_name") or "").strip()
    if not path_id and role_name:
        from app.skill_gap import skill_gap_payload

        gap = skill_gap_payload(conn, user_id=user_id, role=role_name, top=1, lang=lang)
        path_id = str(gap.get("academy_career_path") or "").strip()
    if not path_id:
        return {}
    href = academy_career_path_url(path_id, utm_medium="notification")
    if not href:
        return {}
    return {"path_id": path_id, "url": href, "role": role_name}


def build_growth_cta(
    conn,
    *,
    user_id: str,
    missing_skills: list[str] | list[dict[str, Any]],
    lang: str | None = None,
    have_skills: list[str] | list[dict[str, Any]] | None = None,
    role: str = "",
    near_titles: list[str] | None = None,
    allow_ai_provider: bool = True,
    week_key: str = "",
) -> dict[str, Any]:
    """Academy course + career-path together, then AI/template roadmap fill."""
    from app.learning_roadmap import build_learning_roadmap, legacy_roadmap_steps
    from app.product_features import roadmap_enabled

    if not roadmap_enabled():
        return {
            "academy_courses": [],
            "career_path": None,
            "roadmap": [],
            "learning_roadmap": None,
            "cta_secondary_href": "",
            "missing_names": [],
        }

    locale = _lang(lang)
    names: list[str] = []
    for item in missing_skills or []:
        if isinstance(item, dict):
            name = str(item.get("name") or "").strip()
        else:
            name = str(item or "").strip()
        if name and name not in names:
            names.append(name)
    rich = build_learning_roadmap(
        conn,
        user_id=user_id,
        missing_skills=names,
        have_skills=have_skills or [],
        role=role,
        lang=locale,
        near_titles=near_titles,
        week_key=week_key or week_period_key(),
        allow_ai_provider=allow_ai_provider,
        utm_medium="notification",
    )
    courses = list(rich.get("academy_courses") or [])
    career = rich.get("career_path") if isinstance(rich.get("career_path"), dict) else {}
    # Course + path together (no longer mutually exclusive).
    if not career:
        career = _career_path_for_user(conn, user_id=user_id, lang=locale)
    roadmap = legacy_roadmap_steps(
        list(rich.get("milestones") or []),
        locale=locale,
        missing=names,
    )
    secondary = ""
    if courses:
        secondary = courses[0]["url"]
    elif isinstance(career, dict) and career.get("url"):
        secondary = career["url"]
    elif rich.get("cta_primary"):
        secondary = str(rich["cta_primary"])
    return {
        "academy_courses": courses,
        "career_path": career or None,
        "roadmap": roadmap,
        "learning_roadmap": rich,
        "cta_secondary_href": secondary or "/me/recommendations",
        "missing_names": names or list(rich.get("missing_names") or []),
    }


def _normalize_match_item(item: dict[str, Any]) -> dict[str, Any] | None:
    try:
        job_id = int(item.get("job_id") or 0)
    except (TypeError, ValueError):
        return None
    if job_id <= 0:
        return None
    score = item.get("score")
    if not isinstance(score, (int, float)):
        return None
    have = [str(x).strip() for x in (item.get("have") or []) if str(x).strip()]
    missing_raw = item.get("missing") or []
    missing_names: list[str] = []
    for entry in missing_raw:
        if isinstance(entry, dict):
            name = str(entry.get("name") or "").strip()
        else:
            name = str(entry or "").strip()
        if name:
            missing_names.append(name)
    return {
        "job_id": job_id,
        "title": str(item.get("title") or "").strip(),
        "company": str(item.get("company") or "").strip(),
        "city": str(item.get("city") or "").strip(),
        "remote": bool(item.get("remote")),
        "score": float(score),
        "have": have,
        "missing": missing_names,
        "explanation": str(item.get("explanation") or "").strip(),
        "created_at": str(item.get("created_at") or ""),
    }


def select_match_new(matches: list[dict[str, Any]]) -> dict[str, Any] | None:
    from app.digests import HIGH_MATCH_MIN_SCORE

    best: dict[str, Any] | None = None
    for raw in matches:
        item = _normalize_match_item(raw)
        if item is None:
            continue
        if item["score"] < HIGH_MATCH_MIN_SCORE:
            continue
        # skill overlap > 0 when the ad listed skills (have non-empty, or no missing-only zero)
        if not item["have"] and item["missing"]:
            continue
        if best is None or item["score"] > best["score"]:
            best = item
    return best


def select_match_near(matches: list[dict[str, Any]]) -> dict[str, Any] | None:
    from app.digests import HIGH_MATCH_MIN_SCORE

    best: dict[str, Any] | None = None
    for raw in matches:
        item = _normalize_match_item(raw)
        if item is None:
            continue
        score = item["score"]
        if score < NEAR_MISS_MIN_SCORE or score >= HIGH_MATCH_MIN_SCORE:
            continue
        missing_n = len(item["missing"])
        if missing_n < 1 or missing_n > NEAR_MISS_MAX_MISSING:
            continue
        if best is None or score > best["score"]:
            best = item
    return best


def resolve_match_candidate(
    conn,
    *,
    user_id: str,
    kind: str,
    fresh: list[dict[str, Any]],
    catalog: list[dict[str, Any]],
    email_possible: bool = True,
) -> tuple[dict[str, Any] | None, str]:
    """Pick match_new/near: prefer lookback-fresh jobs, else unseen catalog.

    Returns (match, source) where source is ``fresh``, ``fresh_email`` (seen
    in-app before, only the email is still owed), ``catalog``, or ``""``.

    Per-user per-ad dedupe: a fresh ad that was already emailed is never
    picked again. One already shown in-app is re-picked only while an email
    could actually go out now (``email_possible``) — then just the email is
    sent. Catalog picks skip jobs already logged for this kind (lifetime).
    """
    if kind not in MATCH_ENGINE_KINDS:
        return None, ""
    selector = select_match_new if kind == "match_new" else select_match_near
    unseen_fresh: list[dict[str, Any]] = []
    email_owed: list[dict[str, Any]] = []
    for raw in fresh:
        item = _normalize_match_item(raw)
        if item is None:
            continue
        if job_email_done(conn, user_id=user_id, job_id=item["job_id"]):
            continue
        if job_ever_logged(conn, user_id=user_id, kind=kind, job_id=item["job_id"]):
            if email_possible:
                email_owed.append(raw)
            continue
        unseen_fresh.append(raw)
    picked = selector(unseen_fresh)
    if picked is not None:
        return picked, "fresh"
    picked = selector(email_owed)
    if picked is not None:
        return picked, "fresh_email"

    unseen: list[dict[str, Any]] = []
    fresh_ids = {
        item["job_id"] for item in (_normalize_match_item(r) for r in fresh) if item is not None
    }
    for raw in catalog:
        item = _normalize_match_item(raw)
        if item is None:
            continue
        if item["job_id"] in fresh_ids:
            continue  # fresh ads were handled above (deduped there)
        if job_ever_logged(conn, user_id=user_id, kind=kind, job_id=item["job_id"]):
            continue
        unseen.append(raw)
    picked = selector(unseen)
    if picked is None:
        return None, ""
    return picked, "catalog"


def _event_payload(
    *,
    kind: str,
    match: dict[str, Any],
    growth: dict[str, Any] | None,
) -> dict[str, Any]:
    missing_objs = [{"name": name} for name in match.get("missing") or []]
    payload: dict[str, Any] = {
        "score": match["score"],
        "job_id": match["job_id"],
        "job_title": match.get("title") or "",
        "have": list(match.get("have") or []),
        "missing": missing_objs,
        "cta_href": f"/jobs/{match['job_id']}",
    }
    if growth:
        if growth.get("academy_courses"):
            payload["academy_courses"] = growth["academy_courses"]
        if growth.get("roadmap"):
            payload["roadmap"] = growth["roadmap"]
        if growth.get("learning_roadmap"):
            payload["learning_roadmap"] = growth["learning_roadmap"]
        secondary = str(growth.get("cta_secondary_href") or "").strip()
        if secondary:
            payload["cta_secondary_href"] = secondary
        role = ""
        career = growth.get("career_path") or {}
        if isinstance(career, dict):
            role = str(career.get("role") or "").strip()
        if role:
            payload["role"] = role
    elif kind == "match_near":
        from app.product_features import recommendations_enabled

        if recommendations_enabled():
            payload["cta_secondary_href"] = "/me/recommendations"
    return payload


def _growth_email_line(growth: dict[str, Any], *, lang: str) -> str:
    """Plaintext growth tip without raw URLs (links live in HTML)."""
    pack = NEAR_EMAIL_COPY[_lang(lang)]
    names = growth.get("missing_names") or []
    skills = ", ".join(names[:3]) if names else ""
    courses = growth.get("academy_courses") or []
    if courses:
        return pack["growth_academy"].format(skills=skills or courses[0].get("skill", ""))
    career = growth.get("career_path") or {}
    if isinstance(career, dict) and career.get("url"):
        return pack["growth_academy"].format(skills=skills or career.get("role") or "")
    if growth.get("roadmap"):
        return pack["growth_roadmap"].format(skills=skills)
    return ""


def _recipient(user_id: str) -> str:
    from app.profiles import contact_email_for

    return (contact_email_for(user_id) or "").strip().lower()


def _send_match_new_email(
    conn,
    *,
    user_id: str,
    match: dict[str, Any],
    prefs: dict[str, Any],
    when: datetime,
    growth_line: str = "",
) -> str:
    """Email channel for match_new — logs as high_match (merged prefs/cap)."""
    from app.digests import COPY, deliver_logged_email
    from app.email_clicks import tracked_job_url
    from app.email_prefs import (
        already_logged as email_already_logged,
        day_key,
        high_match_enabled,
        marketing_sent_today,
        unsubscribe_url,
    )

    if not high_match_enabled(prefs):
        return "disabled"
    if marketing_sent_today(conn, user_id=user_id, day=day_key(when=when)):
        return "daily_limit"
    to = _recipient(user_id)
    if not to:
        return "no_email"
    job_id = int(match["job_id"])
    period = period_key_for_job(when=when, job_id=job_id)
    if email_already_logged(conn, user_id=user_id, kind="high_match", period_key=period):
        return "already_sent"
    # One high-match alert per UTC day (legacy digests rule).
    day = day_key(when=when)
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
        return "daily_alert_limit"

    lang = _lang(prefs.get("language"))
    pack = COPY[lang]
    unsub = unsubscribe_url(user_id, lang=lang)
    score_pct = round(float(match["score"]) * 100)
    url = tracked_job_url(user_id, job_id=job_id, kind="high_match", lang=lang)
    if not url or not unsub:
        return "no_app_url"
    subject = pack["high_subject"].format(title=match.get("title") or "")
    body = pack["high_body"].format(
        title=match.get("title") or "",
        company=match.get("company") or "",
        score=score_pct,
        explanation=match.get("explanation") or "",
    )
    tip = (growth_line or "").strip()
    if tip:
        body = body.rstrip() + "\n" + tip + "\n"
    body = body + "\n\n" + pack["unsub"] + "\n" + pack["footer"] + "\n"
    from app.email_templates import render_match_job_html

    html_tip = tip or str(match.get("explanation") or "")
    html_body = render_match_job_html(
        kind="high_match",
        lang=lang,
        match=match,
        job_url=url,
        unsubscribe_url=unsub,
        tip=html_tip,
    )
    return deliver_logged_email(
        conn,
        user_id=user_id,
        kind="high_match",
        period_key=period,
        to=to,
        meta=json.dumps({"job_id": job_id, "score": match.get("score"), "via": "match_new"}, ensure_ascii=False),
        subject=subject,
        body=body,
        html_body=html_body,
        unsubscribe_link=unsub,
    )


def _send_match_near_email(
    conn,
    *,
    user_id: str,
    match: dict[str, Any],
    prefs: dict[str, Any],
    when: datetime,
    growth: dict[str, Any],
) -> str:
    from app.digests import COPY, deliver_logged_email
    from app.email_clicks import tracked_job_url
    from app.email_prefs import (
        already_logged as email_already_logged,
        day_key,
        marketing_sent_today,
        match_near_enabled,
        unsubscribe_url,
    )

    if not match_near_enabled(prefs):
        return "disabled"
    if marketing_sent_today(conn, user_id=user_id, day=day_key(when=when)):
        return "daily_limit"
    to = _recipient(user_id)
    if not to:
        return "no_email"
    job_id = int(match["job_id"])
    period = period_key_for_job(when=when, job_id=job_id)
    if email_already_logged(conn, user_id=user_id, kind="match_near", period_key=period):
        return "already_sent"

    lang = _lang(prefs.get("language"))
    pack = NEAR_EMAIL_COPY[lang]
    footer = COPY[lang]
    unsub = unsubscribe_url(user_id, lang=lang)
    score_pct = round(float(match["score"]) * 100)
    url = tracked_job_url(user_id, job_id=job_id, kind="match_near", lang=lang)
    if not url or not unsub:
        return "no_app_url"
    growth_line = _growth_email_line(growth, lang=lang)
    subject = pack["subject"].format(title=match.get("title") or "")
    body = pack["body"].format(
        title=match.get("title") or "",
        company=match.get("company") or "",
        score=score_pct,
        explanation=match.get("explanation") or "",
        growth=growth_line,
    )
    body = body + "\n\n" + footer["unsub"] + "\n" + footer["footer"] + "\n"
    from app.email_templates import render_match_job_html

    tip = growth_line or str(match.get("explanation") or "")
    html_body = render_match_job_html(
        kind="match_near",
        lang=lang,
        match=match,
        job_url=url,
        unsubscribe_url=unsub,
        tip=tip,
    )
    return deliver_logged_email(
        conn,
        user_id=user_id,
        kind="match_near",
        period_key=period,
        to=to,
        meta=json.dumps({"job_id": job_id, "score": match.get("score")}, ensure_ascii=False),
        subject=subject,
        body=body,
        html_body=html_body,
        unsubscribe_link=unsub,
    )


def fanout_match_event(
    conn,
    *,
    user_id: str,
    kind: str,
    match: dict[str, Any],
    prefs: dict[str, Any],
    when: datetime,
    allow_inapp: bool = True,
    allow_email: bool = True,
    email_only: bool = False,
) -> dict[str, Any]:
    """Insert in-app notification + optional email; always attempt engagement_log dedup.

    ``email_only``: the user already saw this ad in-app/push on an earlier day
    (the email was blocked then) — send just the email, no second in-app note,
    no push and no AI copy call.
    """
    result: dict[str, Any] = {
        "user_id": user_id,
        "kind": kind,
        "status": "skipped",
        "channels": [],
        "ai_applied": False,
    }
    if kind not in MATCH_ENGINE_KINDS:
        result["reason"] = "unsupported_kind"
        return result
    job_id = int(match["job_id"])
    period = period_key_for_job(when=when, job_id=job_id)
    if already_logged(conn, user_id=user_id, kind=kind, period_key=period, job_id=job_id):
        result["reason"] = "already_logged"
        return result

    lang = _lang(prefs.get("language"))
    # Growth CTA always (near-miss payload + optional tip on match_new email).
    growth = build_growth_cta(
        conn,
        user_id=user_id,
        missing_skills=match.get("missing") or [],
        lang=lang,
    )
    payload = _event_payload(
        kind=kind,
        match=match,
        growth=growth if kind == "match_near" else None,
    )

    from app.engagement_copy import maybe_engagement_copy

    has_academy = bool((growth or {}).get("academy_courses") or (growth or {}).get("career_path"))
    role = ""
    career = (growth or {}).get("career_path") or {}
    if isinstance(career, dict):
        role = str(career.get("role") or "").strip()
    if not role:
        role = str(payload.get("role") or "").strip()
    if email_only:
        copy, ai_status = {"title": "", "body": ""}, "skipped_email_only"
    else:
        copy, ai_status = maybe_engagement_copy(
            conn,
            kind=kind,
            locale=lang,
            job_id=job_id,
            job_title=match.get("title") or "",
            score=match.get("score"),
            have=match.get("have") or [],
            missing=match.get("missing") or [],
            has_academy=has_academy,
            role=role,
            when=when,
        )
    payload["ai_title"] = copy["title"]
    payload["ai_body"] = copy["body"]
    result["ai_status"] = ai_status
    result["ai_applied"] = ai_status == "applied"
    result["title"] = copy["title"]
    result["body"] = copy["body"]

    channels: list[str] = []

    if allow_inapp and not email_only:
        from app.notifications import insert_notification

        note = insert_notification(
            conn,
            recipient=user_id,
            kind=kind,
            job_id=job_id,
            job_title=match.get("title") or "",
            application_id=None,
            status="",
            reason="",
            language=lang,
            payload=payload,
        )
        if note is not None:
            channels.append("in_app")

    email_status = ""
    if allow_email:
        if kind == "match_new":
            tip = _growth_email_line(growth or {}, lang=lang) if growth else ""
            email_status = _send_match_new_email(
                conn,
                user_id=user_id,
                match=match,
                prefs=prefs,
                when=when,
                growth_line=tip,
            )
        elif kind == "match_near":
            email_status = _send_match_near_email(
                conn,
                user_id=user_id,
                match=match,
                prefs=prefs,
                when=when,
                growth=growth or {"missing_names": match.get("missing") or []},
            )
        if email_status == "sent":
            channels.append("email")
        else:
            _record_email_skip(conn, user_id=user_id, kind=kind, reason=email_status, when=when)
    result["email"] = email_status

    cta = str(payload.get("cta_href") or f"/jobs/{job_id}")
    if not email_only and _maybe_send_push(
        conn,
        user_id=user_id,
        prefs=prefs,
        title=copy["title"],
        body=copy["body"],
        url_path=cta,
        tag=f"{kind}:{job_id}",
        lang=lang,
    ):
        channels.append("push")

    if not channels:
        result["reason"] = "no_channels"
        return result

    if not log_engagement(
        conn,
        user_id=user_id,
        kind=kind,
        period_key=period,
        job_id=job_id,
        channels=channels,
    ):
        result["reason"] = "already_logged"
        return result

    result["status"] = "sent"
    result["channels"] = channels
    result["job_id"] = job_id
    result["period_key"] = period
    return result


def _user_eligible(conn, *, user_id: str) -> tuple[bool, str, dict[str, Any]]:
    """Matching + confirmed profile — required for match_* and coach_weekly."""
    from app.cv_profile import _profile_payload
    from app.role_suggestions import _matching_granted

    if not _matching_granted(conn, user_id):
        return False, "no_matching_consent", {}
    profile_payload = _profile_payload(conn, user_id=user_id)
    status = str(profile_payload.get("status") or "")
    if status != "confirmed":
        return False, "profile_not_confirmed", profile_payload
    return True, "", profile_payload


def _app_url(path: str, *, lang: str) -> str:
    from app.email_prefs import app_base_url

    base = app_base_url()
    if not base:
        return ""
    prefix = "" if lang == "az" else f"/{lang}"
    rel = path if path.startswith("/") else f"/{path}"
    return f"{base}{prefix}{rel}"


def _maybe_send_push(
    conn,
    *,
    user_id: str,
    prefs: dict[str, Any],
    title: str,
    body: str,
    url_path: str,
    tag: str,
    lang: str,
) -> bool:
    """Send browser push when prefs allow. Soft-fails; returns True if ≥1 delivery."""
    if not prefs.get("push_enabled"):
        return False
    from app.push import send_web_push

    result = send_web_push(
        conn,
        user_id=user_id,
        title=title or "",
        body=body or "",
        url=_app_url(url_path or "/", lang=lang),
        tag=tag or "ingress-job",
    )
    return int(result.get("sent") or 0) > 0


def _nudge_reason_text(reasons: list[str], *, lang: str) -> str:
    pack = NUDGE_REASON_LABELS[_lang(lang)]
    labels = [pack.get(code, code) for code in reasons if code]
    return ", ".join(labels) if labels else pack.get("draft", "draft")


def build_coach_weekly_context(
    conn,
    *,
    user_id: str,
    lang: str | None = None,
    allow_ai_provider: bool = True,
) -> dict[str, Any] | None:
    """Top role + skill gap (+ optional coach) for coach_weekly / insights."""
    from app.role_suggestions import suggest_roles_payload
    from app.skill_gap import DEFAULT_TOP, skill_gap_payload

    locale = _lang(lang)
    roles = suggest_roles_payload(conn, user_id=user_id, limit=1, lang=locale)
    top = (roles.get("roles") or [None])[0]
    if not isinstance(top, dict):
        return None
    role_name = str(top.get("canonical_name") or "").strip()
    if not role_name:
        return None
    # Use DEFAULT_TOP (not a tiny top=N): OR-groups like Backend "lang" can
    # consume the first few weighted skills, leaving complementary gaps
    # (SQL/Docker/Kafka) outside a top=5 window and emptying must_learn.
    gap = skill_gap_payload(
        conn,
        user_id=user_id,
        role=role_name,
        top=DEFAULT_TOP,
        lang=locale,
        allow_ai_provider=allow_ai_provider,
    )
    must_learn = [
        str(item.get("name") or "").strip()
        for item in (gap.get("missing") or [])
        if isinstance(item, dict) and str(item.get("name") or "").strip()
    ]
    already_strong = [
        str(item.get("name") or "").strip()
        for item in (gap.get("have") or [])
        if isinstance(item, dict) and str(item.get("name") or "").strip()
    ]
    growth = build_growth_cta(
        conn,
        user_id=user_id,
        missing_skills=must_learn,
        have_skills=already_strong,
        role=role_name,
        lang=locale,
        allow_ai_provider=allow_ai_provider,
        week_key=week_period_key(),
    )
    coach = gap.get("coach") if isinstance(gap.get("coach"), dict) else None
    return {
        "role": role_name,
        "must_learn": must_learn,
        "already_strong": already_strong,
        "growth": growth,
        "coach": coach,
        "gap": gap,
        "academy_career_path": str(gap.get("academy_career_path") or "").strip(),
    }


def _coach_event_payload(ctx: dict[str, Any]) -> dict[str, Any]:
    growth = ctx.get("growth") or {}
    missing_objs = [{"name": name} for name in (ctx.get("must_learn") or [])]
    have_objs = list(ctx.get("already_strong") or [])
    payload: dict[str, Any] = {
        "role": ctx.get("role") or "",
        "must_learn": list(ctx.get("must_learn") or []),
        "already_strong": have_objs,
        "have": have_objs,
        "missing": missing_objs,
        "cta_href": "/me/insights/roadmap",
        "cta_secondary_href": "/me/recommendations",
    }
    if growth.get("academy_courses"):
        payload["academy_courses"] = growth["academy_courses"]
    if growth.get("roadmap"):
        payload["roadmap"] = growth["roadmap"]
    if growth.get("learning_roadmap"):
        payload["learning_roadmap"] = growth["learning_roadmap"]
    secondary = str(growth.get("cta_secondary_href") or "").strip()
    if secondary and secondary != "/me/recommendations":
        payload["cta_secondary_href"] = secondary
    path_id = str(ctx.get("academy_career_path") or "").strip()
    if not path_id:
        career = growth.get("career_path") or {}
        if isinstance(career, dict):
            path_id = str(career.get("path_id") or "").strip()
    if path_id:
        payload["academy_career_path"] = path_id
    coach = ctx.get("coach")
    if isinstance(coach, dict):
        payload["coach_summary"] = {
            "must_learn": coach.get("must_learn") or [],
            "already_strong": coach.get("already_strong") or [],
        }
    return payload


def _send_profile_nudge_email(
    conn,
    *,
    user_id: str,
    prefs: dict[str, Any],
    when: datetime,
    reasons: list[str],
    period: str,
) -> str:
    from app.digests import COPY, deliver_logged_email
    from app.email_prefs import (
        already_logged as email_already_logged,
        day_key,
        marketing_sent_today,
        profile_nudge_enabled,
        unsubscribe_url,
    )

    if not profile_nudge_enabled(prefs):
        return "disabled"
    if marketing_sent_today(conn, user_id=user_id, day=day_key(when=when)):
        return "daily_limit"
    to = _recipient(user_id)
    if not to:
        return "no_email"
    if email_already_logged(conn, user_id=user_id, kind="profile_nudge", period_key=period):
        return "already_sent"

    lang = _lang(prefs.get("language"))
    pack = NUDGE_EMAIL_COPY[lang]
    footer = COPY[lang]
    unsub = unsubscribe_url(user_id, lang=lang)
    url = _app_url("/profile/review", lang=lang)
    if not url or not unsub:
        return "no_app_url"
    reason = _nudge_reason_text(reasons, lang=lang)
    subject = pack["subject"]
    body = pack["body"].format(reason=reason)
    body = body + "\n\n" + footer["unsub"] + "\n" + footer["footer"] + "\n"
    from app.email_templates import render_profile_nudge_html

    html_body = render_profile_nudge_html(
        lang=lang,
        reason=reason,
        profile_url=url,
        unsubscribe_url=unsub,
    )
    return deliver_logged_email(
        conn,
        user_id=user_id,
        kind="profile_nudge",
        period_key=period,
        to=to,
        meta=json.dumps({"reasons": reasons}, ensure_ascii=False),
        subject=subject,
        body=body,
        html_body=html_body,
        unsubscribe_link=unsub,
    )


def _send_coach_weekly_email(
    conn,
    *,
    user_id: str,
    prefs: dict[str, Any],
    when: datetime,
    ctx: dict[str, Any],
    period: str,
) -> str:
    from app.digests import COPY, deliver_logged_email
    from app.email_prefs import (
        already_logged as email_already_logged,
        coach_weekly_enabled,
        day_key,
        marketing_sent_today,
        unsubscribe_url,
    )

    if not coach_weekly_enabled(prefs):
        return "disabled"
    if marketing_sent_today(conn, user_id=user_id, day=day_key(when=when)):
        return "daily_limit"
    to = _recipient(user_id)
    if not to:
        return "no_email"
    if email_already_logged(conn, user_id=user_id, kind="coach_weekly", period_key=period):
        return "already_sent"

    lang = _lang(prefs.get("language"))
    pack = COACH_EMAIL_COPY[lang]
    footer = COPY[lang]
    unsub = unsubscribe_url(user_id, lang=lang)
    url = _app_url("/me/insights/roadmap", lang=lang)
    if not url or not unsub:
        return "no_app_url"
    role = str(ctx.get("role") or "").strip() or "—"
    must_list = [str(x).strip() for x in (ctx.get("must_learn") or []) if str(x).strip()]
    strong_list = [str(x).strip() for x in (ctx.get("already_strong") or []) if str(x).strip()]
    must = ", ".join(must_list[:5]) or "—"
    strong = ", ".join(strong_list[:5]) or "—"
    growth_line = _growth_email_line(ctx.get("growth") or {}, lang=lang)
    subject = pack["subject"].format(role=role)
    body = pack["body"].format(
        role=role,
        must_learn=must,
        strong=strong,
        growth=growth_line,
    )
    body = body + "\n\n" + footer["unsub"] + "\n" + footer["footer"] + "\n"
    from app.email_templates import render_coach_weekly_html

    html_body = render_coach_weekly_html(
        lang=lang,
        role=role,
        must_learn=must_list,
        already_strong=strong_list,
        tip=growth_line,
        insights_url=url,
        unsubscribe_url=unsub,
    )
    return deliver_logged_email(
        conn,
        user_id=user_id,
        kind="coach_weekly",
        period_key=period,
        to=to,
        meta=json.dumps({"role": role}, ensure_ascii=False),
        subject=subject,
        body=body,
        html_body=html_body,
        unsubscribe_link=unsub,
    )


def fanout_profile_nudge(
    conn,
    *,
    user_id: str,
    prefs: dict[str, Any],
    when: datetime,
    reasons: list[str],
    allow_inapp: bool = True,
    allow_email: bool = True,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "user_id": user_id,
        "kind": "profile_nudge",
        "status": "skipped",
        "channels": [],
        "ai_applied": False,
    }
    period = week_period_key(when=when)
    if already_logged(conn, user_id=user_id, kind="profile_nudge", period_key=period, job_id=0):
        result["reason"] = "already_logged"
        return result

    lang = _lang(prefs.get("language"))
    skill_n = 0
    try:
        from app.cv_profile import _profile_payload

        skill_n = _skill_count(_profile_payload(conn, user_id=user_id))
    except Exception:
        skill_n = 0
    payload: dict[str, Any] = {
        "cta_href": "/profile/review",
        "nudge_reasons": list(reasons),
        "skill_count": skill_n,
    }
    from app.engagement_copy import maybe_engagement_copy

    copy, ai_status = maybe_engagement_copy(
        conn,
        kind="profile_nudge",
        locale=lang,
        when=when,
    )
    payload["ai_title"] = copy["title"]
    payload["ai_body"] = copy["body"]
    result["ai_status"] = ai_status
    result["ai_applied"] = ai_status == "applied"
    result["title"] = copy["title"]
    result["body"] = copy["body"]

    channels: list[str] = []
    if allow_inapp:
        from app.notifications import insert_notification

        note = insert_notification(
            conn,
            recipient=user_id,
            kind="profile_nudge",
            job_id=None,
            job_title="",
            application_id=None,
            status="",
            reason="",
            language=lang,
            payload=payload,
        )
        if note is not None:
            channels.append("in_app")

    if allow_email:
        email_status = _send_profile_nudge_email(
            conn,
            user_id=user_id,
            prefs=prefs,
            when=when,
            reasons=reasons,
            period=period,
        )
        result["email"] = email_status
        if email_status == "sent":
            channels.append("email")
        else:
            _record_email_skip(
                conn, user_id=user_id, kind="profile_nudge", reason=email_status, when=when
            )

    if _maybe_send_push(
        conn,
        user_id=user_id,
        prefs=prefs,
        title=copy["title"],
        body=copy["body"],
        url_path=str(payload.get("cta_href") or "/profile/review"),
        tag=f"profile_nudge:{period}",
        lang=lang,
    ):
        channels.append("push")

    if not channels:
        result["reason"] = "no_channels"
        return result

    if not log_engagement(
        conn,
        user_id=user_id,
        kind="profile_nudge",
        period_key=period,
        job_id=0,
        channels=channels,
    ):
        result["reason"] = "already_logged"
        return result

    result["status"] = "sent"
    result["channels"] = channels
    result["period_key"] = period
    return result


def fanout_coach_weekly(
    conn,
    *,
    user_id: str,
    prefs: dict[str, Any],
    when: datetime,
    ctx: dict[str, Any],
    allow_inapp: bool = True,
    allow_email: bool = True,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "user_id": user_id,
        "kind": "coach_weekly",
        "status": "skipped",
        "channels": [],
        "ai_applied": False,
    }
    period = week_period_key(when=when)
    if already_logged(conn, user_id=user_id, kind="coach_weekly", period_key=period, job_id=0):
        result["reason"] = "already_logged"
        return result

    lang = _lang(prefs.get("language"))
    payload = _coach_event_payload(ctx)
    growth = ctx.get("growth") or {}
    has_academy = bool(growth.get("academy_courses") or growth.get("career_path"))
    from app.engagement_copy import maybe_engagement_copy

    copy, ai_status = maybe_engagement_copy(
        conn,
        kind="coach_weekly",
        locale=lang,
        role=str(ctx.get("role") or ""),
        have=ctx.get("already_strong") or [],
        missing=ctx.get("must_learn") or [],
        has_academy=has_academy,
        when=when,
    )
    payload["ai_title"] = copy["title"]
    payload["ai_body"] = copy["body"]
    result["ai_status"] = ai_status
    result["ai_applied"] = ai_status == "applied"
    result["title"] = copy["title"]
    result["body"] = copy["body"]

    channels: list[str] = []
    if allow_inapp:
        from app.notifications import insert_notification

        note = insert_notification(
            conn,
            recipient=user_id,
            kind="coach_weekly",
            job_id=None,
            job_title=str(ctx.get("role") or ""),
            application_id=None,
            status="",
            reason="",
            language=lang,
            payload=payload,
        )
        if note is not None:
            channels.append("in_app")

    if allow_email:
        email_status = _send_coach_weekly_email(
            conn,
            user_id=user_id,
            prefs=prefs,
            when=when,
            ctx=ctx,
            period=period,
        )
        result["email"] = email_status
        if email_status == "sent":
            channels.append("email")
        else:
            _record_email_skip(
                conn, user_id=user_id, kind="coach_weekly", reason=email_status, when=when
            )

    if _maybe_send_push(
        conn,
        user_id=user_id,
        prefs=prefs,
        title=copy["title"],
        body=copy["body"],
        url_path=str(payload.get("cta_href") or "/me/insights/roadmap"),
        tag=f"coach_weekly:{period}",
        lang=lang,
    ):
        channels.append("push")

    if not channels:
        result["reason"] = "no_channels"
        return result

    if not log_engagement(
        conn,
        user_id=user_id,
        kind="coach_weekly",
        period_key=period,
        job_id=0,
        channels=channels,
    ):
        result["reason"] = "already_logged"
        return result

    result["status"] = "sent"
    result["channels"] = channels
    result["period_key"] = period
    return result


def _latest_notification_payload(conn, *, user_id: str, kind: str) -> dict[str, Any] | None:
    try:
        row = conn.execute(
            """
            SELECT payload FROM notifications
            WHERE recipient_subject = ? AND kind = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            ((user_id or "").strip(), kind),
        ).fetchone()
    except Exception:
        return None
    if row is None:
        return None
    try:
        raw = row["payload"] if "payload" in row.keys() else row[0]
    except Exception:
        raw = row[0] if row else ""
    parsed = parse_payload(raw)
    return parsed or None


def _recent_near_notifications(conn, *, user_id: str, limit: int = 5) -> list[dict[str, Any]]:
    try:
        rows = conn.execute(
            """
            SELECT id, job_id, job_title, payload, created_at
            FROM notifications
            WHERE recipient_subject = ? AND kind = 'match_near'
            ORDER BY id DESC
            LIMIT ?
            """,
            ((user_id or "").strip(), max(1, min(int(limit), 20))),
        ).fetchall()
    except Exception:
        return []
    out: list[dict[str, Any]] = []
    for row in rows:
        try:
            payload = parse_payload(row["payload"] if "payload" in row.keys() else "")
            item = {
                "id": int(row["id"]),
                "job_id": None if row["job_id"] is None else int(row["job_id"]),
                "job_title": str(row["job_title"] or ""),
                "created_at": str(row["created_at"] or ""),
                "payload": payload,
            }
        except Exception:
            continue
        out.append(item)
    return out


def insights_payload(
    conn,
    *,
    user_id: str,
    lang: str | None = None,
) -> dict[str, Any]:
    """Candidate growth hub: coach summary, near-misses, academy/roadmap."""
    from app.cv_profile import _profile_payload
    from app.role_suggestions import _matching_granted

    locale = _lang(lang)
    matching = _matching_granted(conn, user_id)
    profile = _profile_payload(conn, user_id=user_id)
    base: dict[str, Any] = {
        "matching_consent": matching,
        "profile_status": str(profile.get("status") or "empty"),
        "week_key": week_period_key(),
        "coach": None,
        "near_misses": [],
        "academy_courses": [],
        "roadmap": [],
        "learning_roadmap": None,
        "cta_href": "/me/insights/roadmap",
    }
    if not matching:
        return base

    stored_coach = _latest_notification_payload(conn, user_id=user_id, kind="coach_weekly")
    stored_lr = stored_coach.get("learning_roadmap") if isinstance(stored_coach, dict) else None
    has_week_lr = (
        isinstance(stored_lr, dict)
        and str(stored_lr.get("week_key") or "") == base["week_key"]
    )

    # Avoid rebuilding coach+roadmap on every refresh when this week's snapshot exists.
    live_ctx = None
    need_live = str(profile.get("status") or "") == "confirmed" and (
        not stored_coach or not has_week_lr
    )
    if need_live:
        try:
            live_ctx = build_coach_weekly_context(
                conn,
                user_id=user_id,
                lang=locale,
                allow_ai_provider=False,
            )
        except Exception:
            live_ctx = None

    if stored_coach:
        base["coach"] = {
            "source": "notification",
            "role": stored_coach.get("role") or "",
            "must_learn": stored_coach.get("must_learn") or [],
            "already_strong": stored_coach.get("already_strong") or [],
            "ai_title": stored_coach.get("ai_title") or "",
            "ai_body": stored_coach.get("ai_body") or "",
            "academy_courses": stored_coach.get("academy_courses") or [],
            "roadmap": stored_coach.get("roadmap") or [],
            "learning_roadmap": stored_coach.get("learning_roadmap"),
            "academy_career_path": stored_coach.get("academy_career_path") or "",
            "cta_href": stored_coach.get("cta_href") or "/me/insights/roadmap",
        }
        for course in stored_coach.get("academy_courses") or []:
            if isinstance(course, dict) and course not in base["academy_courses"]:
                base["academy_courses"].append(course)
        for step in stored_coach.get("roadmap") or []:
            if isinstance(step, dict):
                base["roadmap"].append(step)
        if has_week_lr:
            base["learning_roadmap"] = stored_lr
    elif live_ctx:
        live_payload = _coach_event_payload(live_ctx)
        base["coach"] = {
            "source": "live",
            "role": live_ctx.get("role") or "",
            "must_learn": live_ctx.get("must_learn") or [],
            "already_strong": live_ctx.get("already_strong") or [],
            "ai_title": "",
            "ai_body": "",
            "academy_courses": live_payload.get("academy_courses") or [],
            "roadmap": live_payload.get("roadmap") or [],
            "learning_roadmap": live_payload.get("learning_roadmap"),
            "academy_career_path": live_payload.get("academy_career_path") or "",
            "cta_href": "/me/insights/roadmap",
            "coach_detail": live_ctx.get("coach"),
        }
        base["academy_courses"] = list(live_payload.get("academy_courses") or [])
        base["roadmap"] = list(live_payload.get("roadmap") or [])
        if isinstance(live_payload.get("learning_roadmap"), dict):
            base["learning_roadmap"] = live_payload["learning_roadmap"]

    # Near-misses: notifications only. Live matches_payload is too heavy for Insights SSR
    # (often multi-second) and was the main cause of 5–10s roadmap waits.
    near_notes = _recent_near_notifications(conn, user_id=user_id, limit=5)
    near_titles: list[str] = []
    for note in near_notes:
        pl = note.get("payload") or {}
        title = str(note.get("job_title") or pl.get("job_title") or "").strip()
        if title:
            near_titles.append(title)
        base["near_misses"].append(
            {
                "job_id": note.get("job_id") or pl.get("job_id"),
                "job_title": title,
                "score": pl.get("score"),
                "have": pl.get("have") or [],
                "missing": pl.get("missing") or [],
                "cta_href": pl.get("cta_href") or (
                    f"/jobs/{note['job_id']}" if note.get("job_id") else "/me/recommendations"
                ),
                "academy_courses": pl.get("academy_courses") or [],
                "roadmap": pl.get("roadmap") or [],
                "created_at": note.get("created_at") or "",
                "source": "notification",
            }
        )

    # Fresh rich roadmap when coach snapshot lacked one for this week.
    if not base["learning_roadmap"] and str(profile.get("status") or "") == "confirmed":
        try:
            role = ""
            must: list[str] = []
            have: list[str] = []
            if live_ctx:
                role = str(live_ctx.get("role") or "")
                must = list(live_ctx.get("must_learn") or [])
                have = list(live_ctx.get("already_strong") or [])
            elif base.get("coach"):
                role = str(base["coach"].get("role") or "")
                must = [
                    str(x.get("name") if isinstance(x, dict) else x).strip()
                    for x in (base["coach"].get("must_learn") or [])
                ]
                have = [
                    str(x.get("name") if isinstance(x, dict) else x).strip()
                    for x in (base["coach"].get("already_strong") or [])
                ]
            if must or have or role:
                growth = build_growth_cta(
                    conn,
                    user_id=user_id,
                    missing_skills=[n for n in must if n],
                    have_skills=[n for n in have if n],
                    role=role,
                    lang=locale,
                    near_titles=near_titles,
                    allow_ai_provider=False,
                    week_key=base["week_key"],
                )
                base["learning_roadmap"] = growth.get("learning_roadmap")
                if not base["academy_courses"] and growth.get("academy_courses"):
                    base["academy_courses"] = list(growth["academy_courses"])
                if not base["roadmap"] and growth.get("roadmap"):
                    base["roadmap"] = list(growth["roadmap"])
        except Exception:
            pass

    return base


def _retry_weekly_email(
    conn,
    *,
    user_id: str,
    kind: str,
    prefs: dict[str, Any],
    when: datetime,
    week: str,
    done: list[str],
    dry_run: bool,
    ctx: dict[str, Any] | None = None,
    reasons: list[str] | None = None,
) -> tuple[str, str]:
    """Weekly kinds (profile_nudge / coach_weekly) already shown this week.

    The week counts as done only for the channels that were delivered. If the
    email was blocked (e.g. Monday's digest used the daily email slot) it is
    retried on later days of the same ISO week — email only, no second in-app
    note, no push, no AI call. Returns (status, reason).
    """
    if "email" in done:
        return "skipped", "already_logged"
    if dry_run:
        return "would_send", "email_retry"
    if kind == "coach_weekly":
        status = _send_coach_weekly_email(
            conn, user_id=user_id, prefs=prefs, when=when, ctx=ctx or {}, period=week
        )
    else:
        status = _send_profile_nudge_email(
            conn,
            user_id=user_id,
            prefs=prefs,
            when=when,
            reasons=list(reasons or []),
            period=week,
        )
    if status == "sent":
        add_logged_channel(
            conn, user_id=user_id, kind=kind, period_key=week, channel="email", job_id=0
        )
        return "sent", "email_retry"
    _record_email_skip(conn, user_id=user_id, kind=kind, reason=status, when=when)
    if status in {"disabled", "already_sent"}:
        return "skipped", "already_logged"
    return "skipped", f"email_{status}"


def process_user_engagement(
    conn,
    *,
    user_id: str,
    when: datetime | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    from app.cv_profile import _profile_payload
    from app.email_prefs import ensure_email_tables, get_prefs

    moment = when or datetime.now(timezone.utc)
    ensure_engagement_tables(conn)
    ensure_email_tables(conn)
    out: dict[str, Any] = {
        "user_id": user_id,
        "match_new": "skipped",
        "match_near": "skipped",
        "profile_nudge": "skipped",
        "coach_weekly": "skipped",
        "ai_applied": 0,
        "reasons": {},
    }
    prefs = get_prefs(conn, user_id)
    lang = _lang(prefs.get("language"))
    profile = _profile_payload(conn, user_id=user_id)
    inapp_left = max(0, ENGAGEMENT_INAPP_DAILY_MAX - inapp_count_today(conn, user_id=user_id, when=moment))
    week = week_period_key(when=moment)

    ok, reason, _confirmed = _user_eligible(conn, user_id=user_id)
    if ok:
        from app.digests import _top_matches

        since = moment - timedelta(hours=ENGAGEMENT_LOOKBACK_HOURS)
        # Top 20 for the catalog fallback + every fresh ad in the whole scored
        # list (not only those that happen to rank in the top 20).
        catalog = _top_matches(conn, user_id=user_id, limit=20, lang=lang, fresh_since=since)
        since_key = since.date().isoformat()
        fresh: list[dict[str, Any]] = []
        for item in catalog:
            created = str(item.get("created_at") or "")[:10]
            if created and created >= since_key:
                fresh.append(item)

        for kind in ("match_new", "match_near"):
            match, source = resolve_match_candidate(
                conn,
                user_id=user_id,
                kind=kind,
                fresh=fresh,
                catalog=catalog,
                email_possible=match_email_possible(
                    conn, user_id=user_id, kind=kind, prefs=prefs, when=moment
                ),
            )
            if match is None:
                out["reasons"][kind] = "none"
                continue
            if kind_sent_today(conn, user_id=user_id, kind=kind, when=moment):
                out["reasons"][kind] = "daily_kind_limit"
                continue
            if dry_run:
                out[kind] = "would_send"
                out["reasons"][kind] = source
                continue
            # Catalog fallback = in-app + push only (email stays for truly fresh ads).
            result = fanout_match_event(
                conn,
                user_id=user_id,
                kind=kind,
                match=match,
                prefs=prefs,
                when=moment,
                allow_inapp=inapp_left > 0,
                allow_email=source in {"fresh", "fresh_email"},
                email_only=source == "fresh_email",
            )
            out[kind] = result.get("status") or "skipped"
            out["reasons"][kind] = result.get("reason") or source
            if result.get("ai_applied"):
                out["ai_applied"] = int(out["ai_applied"]) + 1
            if "in_app" in (result.get("channels") or []):
                inapp_left = max(0, inapp_left - 1)

        coach_ctx = None
        from app.product_features import roadmap_enabled

        if not roadmap_enabled():
            out["reasons"]["coach_weekly"] = "product_off"
        else:
            try:
                coach_ctx = build_coach_weekly_context(conn, user_id=user_id, lang=lang)
            except Exception as exc:
                logger.exception("coach_weekly context failed for %s: %s", user_id, exc)
                out["reasons"]["coach_weekly"] = "context_error"
        if coach_ctx is None and "coach_weekly" not in out["reasons"]:
            out["reasons"]["coach_weekly"] = "no_role"
        elif coach_ctx is not None:
            coach_done = logged_channels(
                conn, user_id=user_id, kind="coach_weekly", period_key=week, job_id=0
            )
            if coach_done is not None:
                out["coach_weekly"], out["reasons"]["coach_weekly"] = _retry_weekly_email(
                    conn,
                    user_id=user_id,
                    kind="coach_weekly",
                    prefs=prefs,
                    when=moment,
                    week=week,
                    done=coach_done,
                    dry_run=dry_run,
                    ctx=coach_ctx,
                )
            elif dry_run:
                out["coach_weekly"] = "would_send"
            else:
                result = fanout_coach_weekly(
                    conn,
                    user_id=user_id,
                    prefs=prefs,
                    when=moment,
                    ctx=coach_ctx,
                    allow_inapp=inapp_left > 0,
                    allow_email=True,
                )
                out["coach_weekly"] = result.get("status") or "skipped"
                if result.get("reason"):
                    out["reasons"]["coach_weekly"] = result["reason"]
                if result.get("ai_applied"):
                    out["ai_applied"] = int(out["ai_applied"]) + 1
                if "in_app" in (result.get("channels") or []):
                    inapp_left = max(0, inapp_left - 1)
    else:
        out["reasons"]["eligible"] = reason
        out["reasons"]["match_new"] = reason
        out["reasons"]["match_near"] = reason
        out["reasons"]["coach_weekly"] = reason

    nudge_reasons = profile_nudge_reasons(profile, when=moment)
    nudge_done = (
        logged_channels(conn, user_id=user_id, kind="profile_nudge", period_key=week, job_id=0)
        if nudge_reasons
        else None
    )
    if not nudge_reasons:
        out["reasons"]["profile_nudge"] = "not_needed"
    elif nudge_done is not None:
        out["profile_nudge"], out["reasons"]["profile_nudge"] = _retry_weekly_email(
            conn,
            user_id=user_id,
            kind="profile_nudge",
            prefs=prefs,
            when=moment,
            week=week,
            done=nudge_done,
            dry_run=dry_run,
            reasons=nudge_reasons,
        )
    elif dry_run:
        out["profile_nudge"] = "would_send"
    else:
        result = fanout_profile_nudge(
            conn,
            user_id=user_id,
            prefs=prefs,
            when=moment,
            reasons=nudge_reasons,
            allow_inapp=inapp_left > 0,
            allow_email=True,
        )
        out["profile_nudge"] = result.get("status") or "skipped"
        if result.get("reason"):
            out["reasons"]["profile_nudge"] = result["reason"]
        if result.get("ai_applied"):
            out["ai_applied"] = int(out["ai_applied"]) + 1

    return out


def run_engagement_jobs(*, dry_run: bool = False) -> dict[str, Any]:
    """Hourly engagement fanout: match_new/near + profile_nudge + coach_weekly."""
    from app.cabinet_store import _LOCK, _connect, ensure_schema

    ensure_schema(create=True)
    when = datetime.now(timezone.utc)
    stats: dict[str, Any] = {
        "match_new": 0,
        "match_near": 0,
        "profile_nudge": 0,
        "coach_weekly": 0,
        "skipped_dedup": 0,
        "skipped": 0,
        "users": 0,
        "dry_run": dry_run,
        "ai_applied": 0,
    }
    kinds = ("match_new", "match_near", "profile_nudge", "coach_weekly")
    with _LOCK:
        conn = _connect()
        try:
            ensure_engagement_tables(conn)
            users = list_engagement_user_ids(conn)
            stats["users"] = len(users)
            from app.email_prefs import record_skip

            for user_id in users:
                try:
                    result = process_user_engagement(
                        conn,
                        user_id=user_id,
                        when=when,
                        dry_run=dry_run,
                    )
                except Exception:
                    # One broken profile must not stop everyone else's alerts.
                    logger.exception("engagement failed for one user")
                    result = {"reasons": {kind: "error" for kind in kinds}}
                for kind in kinds:
                    status = result.get(kind)
                    reason = str(result.get("reasons", {}).get(kind) or "")
                    if status in {"sent", "would_send"}:
                        stats[kind] = int(stats.get(kind) or 0) + 1
                    elif reason == "already_logged":
                        stats["skipped_dedup"] = int(stats["skipped_dedup"]) + 1
                    else:
                        stats["skipped"] = int(stats["skipped"]) + 1
                        if not dry_run:
                            record_skip(conn, user_id=user_id, kind=kind, reason=reason, when=when)
                stats["ai_applied"] = int(stats["ai_applied"]) + int(result.get("ai_applied") or 0)
            conn.commit()
        finally:
            conn.close()
    return stats
