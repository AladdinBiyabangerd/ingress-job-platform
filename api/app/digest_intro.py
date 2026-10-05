"""AI #4: optional personalized digest intro (plan §8.1 / §11).

Soft-fails to None when disabled, over budget, or provider errors so digests
keep the static locale intro.
"""

from __future__ import annotations

import os
from typing import Any

from app.ai_gateway import complete_json, enabled as gateway_enabled
from app.cv_profile import _profile_payload

PURPOSE = "digest_intro"
PROMPT_VERSION = "digest-intro-v1"

_LANG_NAME = {"az": "Azerbaijani", "en": "English", "ru": "Russian"}

_SYSTEM = (
    "Write a short personal intro for a job digest email. "
    "Use only the facts in the user context. Do not invent employers, salaries, "
    "or skills. Do not include email, phone, names, or URLs. "
    "Exactly 2 or 3 sentences. Warm and practical, not salesy. "
    "Write in the language named in the context."
)

_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "intro": {"type": "string"},
    },
    "required": ["intro"],
}


def intro_enabled() -> bool:
    raw = os.environ.get("DIGEST_AI_INTRO_ENABLED", "").strip().lower()
    if raw in {"0", "false", "no", "off"}:
        return False
    if raw in {"1", "true", "yes", "on"}:
        return True
    # Default on when gateway can run (key + AI_GATEWAY_ENABLED).
    return gateway_enabled()


def _pick_locale(lang: str) -> str:
    text = (lang or "").strip().lower()[:2]
    return text if text in _LANG_NAME else "az"


def _skill_names(profile: dict, *, limit: int = 8) -> list[str]:
    raw = profile.get("skills") if isinstance(profile.get("skills"), list) else []
    names: list[str] = []
    for item in raw:
        if isinstance(item, str):
            name = item.strip()
        elif isinstance(item, dict):
            name = str(item.get("name") or item.get("canonical_name") or "").strip()
        else:
            continue
        if name and name not in names:
            names.append(name)
        if len(names) >= limit:
            break
    return names


def _match_lines(matches: list[dict], *, limit: int = 5) -> list[str]:
    lines: list[str] = []
    for item in matches[:limit]:
        title = str(item.get("title") or "").strip()
        company = str(item.get("company") or "").strip()
        score = item.get("score")
        score_pct = f"{round(float(score) * 100)}%" if isinstance(score, (int, float)) else ""
        bit = f"{title} ({company})" if company else title
        if score_pct:
            bit = f"{bit} {score_pct}".strip()
        if bit:
            lines.append(bit)
    return lines


def _build_user_prompt(
    *,
    lang: str,
    profile: dict,
    matches: list[dict],
    trends: list[str],
    gap: str,
) -> str:
    locale = _pick_locale(lang)
    headline = str(profile.get("headline") or "").strip()
    seniority = str(profile.get("seniority") or "").strip()
    skills = _skill_names(profile)
    match_lines = _match_lines(matches)
    parts = [
        f"Language: {_LANG_NAME[locale]}",
        f"Headline: {headline or '(none)'}",
        f"Seniority: {seniority or '(none)'}",
        "Skills: " + (", ".join(skills) if skills else "(none)"),
        "Matched jobs:",
    ]
    if match_lines:
        parts.extend(f"- {line}" for line in match_lines)
    else:
        parts.append("- (none)")
    if trends:
        parts.append("Skill trends:")
        parts.extend(f"- {row}" for row in trends[:3])
    if gap:
        parts.append(f"Learning tip: {gap}")
    parts.append("Write the intro paragraph only in the JSON intro field.")
    return "\n".join(parts)


def maybe_digest_intro(
    conn,
    *,
    user_id: str,
    lang: str,
    matches: list[dict],
    trends: list[str],
    gap: str,
) -> tuple[str | None, str]:
    """Return (intro_or_None, status) where status is applied|skipped:<reason>."""
    if not intro_enabled():
        return None, "skipped:disabled"
    if not matches:
        return None, "skipped:empty"

    profile_payload = _profile_payload(conn, user_id=user_id)
    profile = profile_payload.get("profile") if isinstance(profile_payload.get("profile"), dict) else {}

    result = complete_json(
        purpose=PURPOSE,
        prompt_version=PROMPT_VERSION,
        system=_SYSTEM,
        user=_build_user_prompt(
            lang=lang,
            profile=profile,
            matches=matches,
            trends=trends,
            gap=gap,
        ),
        schema=_SCHEMA,
        schema_name="digest_intro",
        known_pii=None,
        conn=conn,
        timeout=30.0,
    )
    if not result.ok or not isinstance(result.data, dict):
        reason = (result.error or "ai_failed").replace(" ", "_")[:80]
        return None, f"skipped:{reason}"

    intro = str(result.data.get("intro") or "").strip()
    # Collapse whitespace; keep short.
    intro = " ".join(intro.split())
    if not intro or len(intro) < 20:
        return None, "skipped:empty_intro"
    if len(intro) > 600:
        intro = intro[:597].rstrip() + "..."
    return intro, "applied"
