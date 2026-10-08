"""AI engagement notification title/body (plan Phase 3).

Soft-fails to locale templates when the flag is off, budget is exhausted,
or the provider returns invalid copy. Pattern matches digest_intro.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from app.ai_flags import feature_on
from app.ai_gateway import complete_json

PURPOSE = "engagement_copy"
PROMPT_VERSION = "engagement-copy-v1"

_LANG_NAME = {"az": "Azerbaijani", "en": "English", "ru": "Russian"}

_SYSTEM = (
    "Write a short engagement notification title and body for a job platform. "
    "Use only the facts in the user context. Do not invent employers, skills, "
    "companies, or scores. Only use skill names listed in have/missing. "
    "No email, phone, personal names, URLs, ALL CAPS, or excessive emoji. "
    "Tone: encouraging and practical, not spammy. "
    "For near-miss (match_near): mention at least one missing skill and invite learning. "
    "Write in the language named in the context. "
    "title ≤ 60 characters; body ≤ 160 characters, 1–2 sentences."
)

_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "title": {"type": "string"},
        "body": {"type": "string"},
        "tone": {"type": "string"},
    },
    "required": ["title", "body"],
}

# Soft-fail templates: {title}, {score_pct}, {skills} (have or missing).
_TEMPLATES = {
    "az": {
        "match_new": (
            "Sənə uyğun yeni elan: {title} · {score_pct}%",
            "{skills} üst-üstə düşür. Bax və müraciət et.",
        ),
        "match_near": (
            "Yaxın elan: {title} · {score_pct}%",
            "{skills} çatışır. Artırsan, bu elanı tövsiyə edirəm.",
        ),
        "profile_nudge": (
            "Profilini tamamla",
            "CV və skill-lərini doldur ki, sənə uyğun elanları tapa bilək.",
        ),
        "coach_weekly": (
            "Bu həftənin öyrənmə planı{role_suffix}",
            "Rolun üçün qısa plan hazırdır — güclü tərəflər və öyrəniləcək skill-lər.",
        ),
    },
    "en": {
        "match_new": (
            "New match for you: {title} · {score_pct}%",
            "{skills} overlap. Open it and apply.",
        ),
        "match_near": (
            "Almost a match: {title} · {score_pct}%",
            "Missing: {skills}. Level up and I will recommend this role.",
        ),
        "profile_nudge": (
            "Complete your profile",
            "Fill in your CV and skills so we can find matching jobs for you.",
        ),
        "coach_weekly": (
            "This week’s learning plan{role_suffix}",
            "A short plan for your target role — strengths and skills to learn.",
        ),
    },
    "ru": {
        "match_new": (
            "Новое совпадение: {title} · {score_pct}%",
            "Совпадают: {skills}. Откройте и откликнитесь.",
        ),
        "match_near": (
            "Почти совпадение: {title} · {score_pct}%",
            "Не хватает: {skills}. Подтяните навыки — и я порекомендую вакансию.",
        ),
        "profile_nudge": (
            "Заполните профиль",
            "Добавьте CV и навыки, чтобы мы могли находить подходящие вакансии.",
        ),
        "coach_weekly": (
            "План обучения на эту неделю{role_suffix}",
            "Краткий план по вашей роли — сильные стороны и навыки для роста.",
        ),
    },
}

_FALLBACK_BODY = {
    "az": {
        "match_new": "«{title}» elanı profilinə uyğundur. Bax və müraciət et.",
        "match_near": "«{title}» elanı yaxındır. Çatışmayan skill-ləri artırsan, bu elanı tövsiyə edirəm.",
    },
    "en": {
        "match_new": "«{title}» looks like a strong fit. Open it and apply.",
        "match_near": "«{title}» is close. Level up the missing skills and I will recommend this role.",
    },
    "ru": {
        "match_new": "«{title}» хорошо подходит под ваш профиль. Откройте и откликнитесь.",
        "match_near": "«{title}» близко. Подтяните недостающие навыки — и я порекомендую эту вакансию.",
    },
}


def copy_enabled(conn=None) -> bool:
    return feature_on("engagement_copy", conn)


def _pick_locale(lang: str | None) -> str:
    text = (lang or "").strip().lower()[:2]
    return text if text in _LANG_NAME else "az"


def _skill_list(values: list[str] | list[dict[str, Any]] | None, *, limit: int = 4) -> list[str]:
    names: list[str] = []
    for item in values or []:
        if isinstance(item, dict):
            name = str(item.get("name") or item.get("canonical_name") or "").strip()
        else:
            name = str(item or "").strip()
        if name and name not in names:
            names.append(name)
        if len(names) >= limit:
            break
    return names


def _score_pct(score: float | int | None) -> int:
    if not isinstance(score, (int, float)):
        return 0
    return max(0, min(100, round(float(score) * 100)))


def skill_sig(*, have: list[str], missing: list[str]) -> str:
    parts = sorted({n.lower() for n in have}) + sorted({n.lower() for n in missing})
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def template_copy(
    *,
    kind: str,
    locale: str,
    job_title: str = "",
    score: float | int | None = None,
    have: list[str] | None = None,
    missing: list[str] | None = None,
    role: str = "",
) -> dict[str, str]:
    """Locale title/body when AI is off or soft-fails."""
    lang = _pick_locale(locale)
    pack = _TEMPLATES[lang]
    title_t, body_t = pack.get(kind) or pack["match_new"]
    title_job = (job_title or "").strip() or "—"
    pct = _score_pct(score)
    have_names = _skill_list(have)
    missing_names = _skill_list(missing)
    if kind == "match_near":
        skills = ", ".join(missing_names) if missing_names else ""
    else:
        skills = ", ".join(have_names) if have_names else ""
    role_name = (role or "").strip()
    role_suffix = f": {role_name}" if role_name else ""
    title = title_t.format(
        title=title_job,
        score_pct=pct,
        skills=skills or "—",
        role_suffix=role_suffix,
    )
    if kind in {"match_new", "match_near"} and not skills:
        body = _FALLBACK_BODY[lang][kind].format(title=title_job)
    else:
        body = body_t.format(
            title=title_job,
            score_pct=pct,
            skills=skills or "—",
            role_suffix=role_suffix,
        )
    title = " ".join(title.split())
    body = " ".join(body.split())
    return {"title": title[:60], "body": body[:160]}


def _build_user_prompt(
    *,
    locale: str,
    kind: str,
    job_id: int | None,
    job_title: str,
    score: float | int | None,
    have: list[str],
    missing: list[str],
    has_academy: bool,
    role: str,
    day: str,
    sig: str,
) -> str:
    lang = _pick_locale(locale)
    jid = int(job_id) if isinstance(job_id, int) and job_id > 0 else 0
    parts = [
        f"Language: {_LANG_NAME[lang]}",
        f"kind: {kind}",
        f"job_id: {jid}",
        f"job_title: {(job_title or '').strip() or '(none)'}",
        f"score: {_score_pct(score)}%",
        "have: " + (", ".join(have) if have else "(none)"),
        "missing: " + (", ".join(missing) if missing else "(none)"),
        f"has_academy: {'yes' if has_academy else 'no'}",
        f"role: {(role or '').strip() or '(none)'}",
        f"day: {day}",
        f"skill_sig: {sig}",
        "Return JSON with title and body only.",
    ]
    return "\n".join(parts)


def _clamp_copy(data: dict[str, Any]) -> dict[str, str] | None:
    title = " ".join(str(data.get("title") or "").split())
    body = " ".join(str(data.get("body") or "").split())
    if not title or not body:
        return None
    if len(title) < 8 or len(body) < 12:
        return None
    return {"title": title[:60], "body": body[:160]}


def _mentions_allowed_skills(body: str, *, have: list[str], missing: list[str], kind: str) -> bool:
    """Reject copy that invents skill tokens not in context (near-miss must cite missing)."""
    text = (body or "").lower()
    if kind == "match_near" and missing:
        return any(name.lower() in text for name in missing)
    return True


def maybe_engagement_copy(
    conn,
    *,
    kind: str,
    locale: str,
    job_id: int | None = None,
    job_title: str = "",
    score: float | int | None = None,
    have: list[str] | list[dict[str, Any]] | None = None,
    missing: list[str] | list[dict[str, Any]] | None = None,
    has_academy: bool = False,
    role: str = "",
    when: datetime | None = None,
) -> tuple[dict[str, str], str]:
    """Return ({title, body}, status) where status is applied|template|skipped:<reason>.

    Title/body are always filled (AI or soft-fail template) so fanout can sync channels.
    """
    have_names = _skill_list(have)
    missing_names = _skill_list(missing)
    fallback = template_copy(
        kind=kind,
        locale=locale,
        job_title=job_title,
        score=score,
        have=have_names,
        missing=missing_names,
        role=role,
    )
    if not copy_enabled(conn):
        return fallback, "template:disabled"

    moment = when or datetime.now(timezone.utc)
    day = moment.astimezone(timezone.utc).strftime("%Y-%m-%d")
    sig = skill_sig(have=have_names, missing=missing_names)

    result = complete_json(
        purpose=PURPOSE,
        prompt_version=PROMPT_VERSION,
        system=_SYSTEM,
        user=_build_user_prompt(
            locale=locale,
            kind=kind,
            job_id=job_id,
            job_title=job_title,
            score=score,
            have=have_names,
            missing=missing_names,
            has_academy=has_academy,
            role=role,
            day=day,
            sig=sig,
        ),
        schema=_SCHEMA,
        schema_name="engagement_copy",
        known_pii=None,
        conn=conn,
        timeout=20.0,
    )
    if not result.ok or not isinstance(result.data, dict):
        reason = (result.error or "ai_failed").replace(" ", "_")[:80]
        return fallback, f"template:{reason}"

    clamped = _clamp_copy(result.data)
    if clamped is None:
        return fallback, "template:empty_copy"
    if not _mentions_allowed_skills(
        clamped["body"], have=have_names, missing=missing_names, kind=kind
    ):
        return fallback, "template:missing_skill"
    return clamped, "applied"
