"""AI #2: optional short “why this match” sentence (plan §6.2).

Only top-N results. Soft-fails to template explanation. Cached via ai_gateway
(complete_json) keyed by prompt content including profile_version + job_id.
"""

from __future__ import annotations

import os
from typing import Any

from app.ai_gateway import complete_json, enabled as gateway_enabled

PURPOSE = "match_why"
PROMPT_VERSION = "match-why-v1"
DEFAULT_TOP = 5

_LANG_NAME = {"az": "Azerbaijani", "en": "English", "ru": "Russian"}

_SYSTEM = (
    "Write one short sentence explaining why this job fits the candidate. "
    "Use only the facts in the user context. Do not invent employers, salaries, "
    "skills, or locations. Do not include names, email, phone, or URLs. "
    "Write in the language named in the context."
)

_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "why": {"type": "string"},
    },
    "required": ["why"],
}


def why_enabled() -> bool:
    raw = os.environ.get("AI_MATCH_WHY_ENABLED", "").strip().lower()
    if raw in {"0", "false", "no", "off"}:
        return False
    if raw in {"1", "true", "yes", "on"}:
        return True
    return gateway_enabled()


def _pick_locale(lang: str) -> str:
    text = (lang or "").strip().lower()[:2]
    return text if text in _LANG_NAME else "az"


def _build_user(
    *,
    lang: str,
    profile_version: str,
    match: dict,
) -> str:
    locale = _pick_locale(lang)
    have = match.get("have") if isinstance(match.get("have"), list) else []
    missing = match.get("missing") if isinstance(match.get("missing"), list) else []
    comps = match.get("components") if isinstance(match.get("components"), dict) else {}
    return "\n".join(
        [
            f"Language: {_LANG_NAME[locale]}",
            f"ProfileVersion: {profile_version}",
            f"JobId: {match.get('job_id')}",
            f"Title: {str(match.get('title') or '').strip()}",
            f"Company: {str(match.get('company') or '').strip()}",
            f"JobSeniority: {str(match.get('job_seniority') or '').strip() or '(none)'}",
            f"Remote: {'yes' if match.get('remote') else 'no'}",
            f"Relocation: {'yes' if match.get('relocation') else 'no'}",
            "HaveSkills: " + (", ".join(str(x) for x in have[:12]) if have else "(none)"),
            "MissingSkills: " + (", ".join(str(x) for x in missing[:12]) if missing else "(none)"),
            f"SkillScore: {comps.get('skills', '')}",
            f"SemanticScore: {comps.get('semantic', '')}",
            "Write one sentence in the JSON why field.",
        ]
    )


def append_why_sentences(
    conn,
    *,
    matches: list[dict],
    lang: str,
    profile_version: str,
    top_n: int = DEFAULT_TOP,
) -> None:
    """Mutate matches[:top_n] explanations in place when AI succeeds."""
    if not why_enabled() or not matches:
        return
    n = max(0, min(int(top_n or DEFAULT_TOP), len(matches)))
    version = (profile_version or "v0")[:80]
    for item in matches[:n]:
        if not isinstance(item, dict):
            continue
        result = complete_json(
            purpose=PURPOSE,
            prompt_version=PROMPT_VERSION,
            system=_SYSTEM,
            user=_build_user(lang=lang, profile_version=version, match=item),
            schema=_SCHEMA,
            schema_name="match_why",
            known_pii=None,
            conn=conn,
            timeout=20.0,
        )
        if not result.ok or not isinstance(result.data, dict):
            continue
        why = " ".join(str(result.data.get("why") or "").split())
        if len(why) < 12:
            continue
        if len(why) > 280:
            why = why[:277].rstrip() + "..."
        base = str(item.get("explanation") or "").strip()
        item["explanation"] = f"{base} · {why}" if base else why
        item["ai_why"] = True
