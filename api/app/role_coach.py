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
PROMPT_VERSION = "role-coach-v1"

_LANG_NAME = {"az": "Azerbaijani", "en": "English", "ru": "Russian"}

_SYSTEM = (
    "You are a career coach for one target role. Use ONLY the skill names and "
    "facts in the user message. Do not invent skill names — every skill in "
    "must_learn / already_strong / transferable must come from the provided "
    "MissingSkills or HaveSkills lists.\n"
    "Output:\n"
    "- fit_summary: 2–3 sentences in the requested language.\n"
    "- must_learn: up to 5 items from MissingSkills only {skill, why, priority}.\n"
    "- already_strong: up to 5 skill names from HaveSkills only.\n"
    "- transferable: up to 3 {from, to, note} where from∈HaveSkills and to∈MissingSkills.\n"
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


def _skill_card(items: list[dict], *, limit: int = 15) -> list[dict]:
    """Stable prompt fields only — omit trend share so cache keys survive daily metrics."""
    out: list[dict] = []
    for item in items[:limit]:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        card: dict[str, Any] = {"name": name, "weight": item.get("weight")}
        if item.get("years") is not None:
            card["years"] = item.get("years")
        out.append(card)
    return out


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
    for item in skills:
        if isinstance(item, str):
            name = item.strip()
        elif isinstance(item, dict):
            name = str(item.get("name") or "").strip()
        else:
            continue
        if name and name not in top:
            top.append(name)
        if len(top) >= 12:
            break
    years = profile.get("total_years")
    years_s = str(years) if isinstance(years, (int, float)) else ""
    return "\n".join(
        [
            f"Language: {_LANG_NAME[locale]}",
            f"Role: {role_name}",
            f"CandidateSeniority: {str(profile.get('seniority') or '').strip() or '(none)'}",
            f"CandidateYears: {years_s or '(unknown)'}",
            "TopSkills: " + (", ".join(top) if top else "(none)"),
            "HaveSkills: " + json.dumps(_skill_card(have), ensure_ascii=False),
            "MissingSkills: " + json.dumps(_skill_card(missing), ensure_ascii=False),
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
) -> tuple[dict | None, str]:
    """Return (validated coach payload, error_code). error_code is '' on success."""
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
    )
    if not result.ok or not isinstance(result.data, dict):
        code = str(result.error or "ai_failed").strip() or "ai_failed"
        return _fail(role_name, code[:80])
    validated = _validate_coach(result.data, have=have, missing=missing)
    if validated is None:
        return _fail(role_name, "ai_validation_failed")
    return validated, ""
