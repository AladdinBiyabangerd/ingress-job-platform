"""AI role skill coach: what to learn next for a target role.

Soft-fails to coach=null. Post-validates skill names against have/missing sets.
Returns (coach, error_code) so callers can surface why advice is missing.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.ai_flags import feature_on
from app.ai_gateway import complete_json

log = logging.getLogger("ingress-job.api.role_coach")

PURPOSE = "role_coach"
# v4: include market share/growth on skill cards (daily metric refresh may
# regenerate once; same-day page refresh still hits ai_cache).
PROMPT_VERSION = "role-coach-v4"

_LANG_NAME = {"az": "Azerbaijani", "en": "English", "ru": "Russian"}

_SYSTEM = (
    "You are a career coach speaking directly to the learner who will read "
    "this advice. Use ONLY the skill names and facts in the user message. Do "
    "not invent skill names — every skill in must_learn / already_strong / "
    "transferable must come from the provided MissingSkills or HaveSkills "
    "lists.\n"
    "When share (market demand fraction) or growth (recent demand change) is "
    "present on a skill, prefer higher share / positive growth for must_learn "
    "priority and mention demand briefly in why when useful. Ignore missing "
    "share/growth fields.\n"
    "Voice: second person only (you / your; Azerbaijani: siz / sizin; "
    "Russian: вы / ваш). Never third person about a 'candidate', 'namizəd', "
    "'applicant', or 'they'. The reader is the person in the profile.\n"
    "Output:\n"
    "- fit_summary: 2–3 sentences in the requested language, addressing the "
    "reader directly.\n"
    "- must_learn: up to 5 items from MissingSkills only {skill, why, priority}; "
    "why addresses the reader (why you should learn it).\n"
    "- already_strong: up to 5 skill names from HaveSkills only.\n"
    "- transferable: up to 3 {from, to, note} where from∈HaveSkills and "
    "to∈MissingSkills; note addresses the reader.\n"
    "priority is an integer 1–5 (1 = highest). No PII."
)

_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "fit_summary": {"type": "string"},
        "must_learn": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "skill": {"type": "string"},
                    "why": {"type": "string"},
                    "priority": {"type": "integer"},
                },
                "required": ["skill", "why", "priority"],
            },
        },
        "already_strong": {
            "type": "array",
            "items": {"type": "string"},
        },
        "transferable": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "from": {"type": "string"},
                    "to": {"type": "string"},
                    "note": {"type": "string"},
                },
                "required": ["from", "to", "note"],
            },
        },
    },
    "required": ["fit_summary", "must_learn", "already_strong", "transferable"],
}


def coach_enabled(conn=None) -> bool:
    return feature_on("role_coach", conn)


def _pick_locale(lang: str) -> str:
    text = (lang or "").strip().lower()[:2]
    return text if text in _LANG_NAME else "az"


def _metric_float(raw: object, *, digits: int = 4) -> float | None:
    if raw is None:
        return None
    try:
        return round(float(raw), digits)
    except (TypeError, ValueError):
        return None


def _skill_card(items: list[dict], *, limit: int = 15) -> list[dict]:
    """Prompt cards for HaveSkills / MissingSkills.

    Includes market share/growth when present (better coaching). Sorted by
    role weight desc, then name, so list reshuffles alone do not change the
    cache key. Rounded metrics keep same-day refreshes cache-stable; a daily
    trends refresh may regenerate once — that is intentional.
    """
    scored: list[tuple[float, str, dict[str, Any]]] = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        try:
            weight = float(item.get("weight"))
        except (TypeError, ValueError):
            weight = 0.0
        card: dict[str, Any] = {"name": name, "weight": weight}
        if item.get("years") is not None:
            card["years"] = item.get("years")
        share = _metric_float(item.get("share"))
        if share is not None:
            card["share"] = share
        growth = _metric_float(item.get("growth"))
        if growth is not None:
            card["growth"] = growth
        scored.append((-weight, name.lower(), card))
    scored.sort(key=lambda row: (row[0], row[1]))
    return [row[2] for row in scored[:limit]]


def _name_set(items: list[dict]) -> set[str]:
    return {
        str(item.get("name") or "").strip()
        for item in items
        if isinstance(item, dict) and str(item.get("name") or "").strip()
    }


def _canon_map(names: set[str]) -> dict[str, str]:
    return {n.lower(): n for n in names}


def _resolve_name(raw: object, canon: dict[str, str]) -> str | None:
    key = str(raw or "").strip().lower()
    if not key:
        return None
    return canon.get(key)


def _build_user(
    *,
    lang: str,
    role_name: str,
    have: list[dict],
    missing: list[dict],
    profile: dict,
) -> str:
    locale = _pick_locale(lang)
    skills = profile.get("skills") if isinstance(profile.get("skills"), list) else []
    top: list[str] = []
    seen: set[str] = set()
    for item in skills:
        if isinstance(item, str):
            name = item.strip()
        elif isinstance(item, dict):
            name = str(item.get("name") or "").strip()
        else:
            continue
        key = name.lower()
        if not name or key in seen:
            continue
        seen.add(key)
        top.append(name)
    # Alphabetical — profile list order must not bust the per-role cache key.
    top = sorted(top, key=str.lower)[:12]
    years = profile.get("total_years")
    years_s = str(years) if isinstance(years, (int, float)) else ""
    role = str(role_name or "").strip()
    return "\n".join(
        [
            f"Language: {_LANG_NAME[locale]}",
            f"Role: {role}",
            f"YourSeniority: {str(profile.get('seniority') or '').strip() or '(none)'}",
            f"YourYears: {years_s or '(unknown)'}",
            "TopSkills: " + (", ".join(top) if top else "(none)"),
            "HaveSkills: " + json.dumps(_skill_card(have), ensure_ascii=False),
            "MissingSkills: " + json.dumps(_skill_card(missing), ensure_ascii=False),
            "Write fit_summary, why, and note in second person to the learner.",
            "Tailor advice specifically to this Role; do not reuse another role's plan.",
            "Respond with fit_summary, must_learn, already_strong, transferable.",
        ]
    )


def _validate_coach(data: dict, *, have: list[dict], missing: list[dict]) -> dict | None:
    have_canon = _canon_map(_name_set(have))
    miss_canon = _canon_map(_name_set(missing))
    summary = " ".join(str(data.get("fit_summary") or "").split())
    if len(summary) < 20:
        return None
    if len(summary) > 600:
        summary = summary[:597].rstrip() + "..."

    must_learn: list[dict] = []
    raw_must = data.get("must_learn") if isinstance(data.get("must_learn"), list) else []
    seen_must: set[str] = set()
    for item in raw_must:
        if not isinstance(item, dict):
            continue
        skill = _resolve_name(item.get("skill"), miss_canon)
        if not skill or skill in seen_must:
            continue
        try:
            priority = int(item.get("priority"))
        except (TypeError, ValueError):
            priority = 3
        priority = max(1, min(5, priority))
        why = " ".join(str(item.get("why") or "").split())[:160]
        if not why:
            continue
        must_learn.append({"skill": skill, "why": why, "priority": priority})
        seen_must.add(skill)
        if len(must_learn) >= 5:
            break
    must_learn.sort(key=lambda row: (row["priority"], row["skill"].lower()))

    already_strong: list[str] = []
    raw_strong = data.get("already_strong") if isinstance(data.get("already_strong"), list) else []
    for item in raw_strong:
        skill = _resolve_name(item, have_canon)
        if skill and skill not in already_strong:
            already_strong.append(skill)
        if len(already_strong) >= 5:
            break

    transferable: list[dict] = []
    raw_xfer = data.get("transferable") if isinstance(data.get("transferable"), list) else []
    seen_xfer: set[tuple[str, str]] = set()
    for item in raw_xfer:
        if not isinstance(item, dict):
            continue
        frm = _resolve_name(item.get("from"), have_canon)
        to = _resolve_name(item.get("to"), miss_canon)
        if not frm or not to:
            continue
        key = (frm, to)
        if key in seen_xfer:
            continue
        note = " ".join(str(item.get("note") or "").split())[:120]
        if not note:
            continue
        transferable.append({"from": frm, "to": to, "note": note})
        seen_xfer.add(key)
        if len(transferable) >= 3:
            break

    return {
        "fit_summary": summary,
        "must_learn": must_learn,
        "already_strong": already_strong,
        "transferable": transferable,
    }


def _fail(role_name: str, code: str) -> tuple[None, str]:
    log.warning("role_coach soft-fail role=%s reason=%s", role_name or "-", code)
    return None, code


def build_role_coach(
    conn,
    *,
    role_name: str,
    have: list[dict],
    missing: list[dict],
    profile: dict,
    lang: str,
    allow_provider: bool = True,
) -> tuple[dict | None, str]:
    """Return (validated coach payload, error_code). error_code is '' on success.

    allow_provider=False: cache-only (miss → ``ai_pending``) for non-blocking HTTP.
    """
    if not coach_enabled(conn):
        return _fail(role_name, "role_coach_disabled")
    if not role_name or (not have and not missing):
        return _fail(role_name, "coach_no_skills")
    result = complete_json(
        purpose=PURPOSE,
        prompt_version=PROMPT_VERSION,
        system=_SYSTEM,
        user=_build_user(
            lang=lang,
            role_name=role_name,
            have=have,
            missing=missing,
            profile=profile if isinstance(profile, dict) else {},
        ),
        schema=_SCHEMA,
        schema_name="role_coach",
        known_pii=None,
        conn=conn,
        timeout=30.0,
        allow_provider=allow_provider,
    )
    if not result.ok or not isinstance(result.data, dict):
        code = str(result.error or "ai_failed").strip() or "ai_failed"
        if code == "ai_pending":
            return None, "ai_pending"
        return _fail(role_name, code[:80])
    validated = _validate_coach(result.data, have=have, missing=missing)
    if validated is None:
        return _fail(role_name, "ai_validation_failed")
    return validated, ""
