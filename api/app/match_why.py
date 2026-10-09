"""AI #2: optional short “why this match” sentence (plan §6.2).

Only top-N results. Soft-fails to template explanation. Cached via ai_gateway
(complete_json) keyed by prompt content including profile_version + job_id.
"""

from __future__ import annotations

from typing import Any

from app.ai_flags import feature_on
from app.ai_gateway import complete_json

PURPOSE = "match_why"
PROMPT_VERSION = "match-why-v2"
DEFAULT_TOP = 5

_LANG_NAME = {"az": "Azerbaijani", "en": "English", "ru": "Russian"}

_SYSTEM = (
    "Write exactly one sentence (≤30 words) explaining why this job fits the candidate. "
    "Must name 1–2 concrete overlapping skills from HaveSkills. "
    "Ban clichés: do not write “great fit”, “perfect”, “ideal”, or vague praise. "
    "Use only facts in the user context. Do not invent skills, employers, or salaries. "
    "No names, email, phone, or URLs. "
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


def why_enabled(conn=None) -> bool:
    return feature_on("match_why", conn)


def _pick_locale(lang: str) -> str:
    text = (lang or "").strip().lower()[:2]
    return text if text in _LANG_NAME else "az"


def _build_user(
    *,
    lang: str,
    profile_version: str,
    match: dict,
    candidate: dict | None = None,
) -> str:
    locale = _pick_locale(lang)
    have = match.get("have") if isinstance(match.get("have"), list) else []
    missing = match.get("missing") if isinstance(match.get("missing"), list) else []
    comps = match.get("components") if isinstance(match.get("components"), dict) else {}
    cand = candidate if isinstance(candidate, dict) else {}
    prefs = cand.get("preferences") if isinstance(cand.get("preferences"), dict) else {}
    pref_bits: list[str] = []
    if prefs.get("remote") is True:
        pref_bits.append("remote")
    elif prefs.get("remote") is False:
        pref_bits.append("on-site")
    if prefs.get("relocation") is True:
        pref_bits.append("open_relocation")
    elif prefs.get("relocation") is False:
        pref_bits.append("no_relocation")
    years = cand.get("total_years")
    years_s = str(years) if isinstance(years, (int, float)) else ""
    llm_note = str(comps.get("llm_note") or "").strip()
    lines = [
        f"Language: {_LANG_NAME[locale]}",
        f"ProfileVersion: {profile_version}",
        f"CandidateSeniority: {str(cand.get('seniority') or '').strip() or '(none)'}",
        f"CandidateYears: {years_s or '(unknown)'}",
        f"CandidatePrefs: {', '.join(pref_bits) if pref_bits else '(none)'}",
        f"JobId: {match.get('job_id')}",
        f"Title: {str(match.get('title') or '').strip()}",
        f"Company: {str(match.get('company') or '').strip()}",
        f"JobSeniority: {str(match.get('job_seniority') or '').strip() or '(none)'}",
        f"Remote: {'yes' if match.get('remote') else 'no'}",
        f"Relocation: {'yes' if match.get('relocation') else 'no'}",
        "HaveSkills: " + (", ".join(str(x) for x in have[:12]) if have else "(none)"),
        "MissingSkillsTop3: "
        + (", ".join(str(x) for x in missing[:3]) if missing else "(none)"),
        f"SkillScore: {comps.get('skills', '')}",
        f"SemanticScore: {comps.get('semantic', '')}",
        f"LlmRelevance: {comps.get('llm_relevance', '')}",
        f"LlmNote: {llm_note or '(none)'}",
        "Write one sentence in the JSON why field.",
    ]
    return "\n".join(lines)


def append_why_sentences(
    conn,
    *,
    matches: list[dict],
    lang: str,
    profile_version: str,
    top_n: int = DEFAULT_TOP,
    candidate: dict | None = None,
    allow_provider: bool = True,
) -> bool:
    """Mutate matches[:top_n] explanations in place when AI succeeds.

    Returns True when at least one call was deferred (``ai_pending``).
    """
    if not why_enabled(conn) or not matches:
        return False
    n = max(0, min(int(top_n or DEFAULT_TOP), len(matches)))
    version = (profile_version or "v0")[:80]
    deferred = False
    for item in matches[:n]:
        if not isinstance(item, dict):
            continue
        result = complete_json(
            purpose=PURPOSE,
            prompt_version=PROMPT_VERSION,
            system=_SYSTEM,
            user=_build_user(
                lang=lang,
                profile_version=version,
                match=item,
                candidate=candidate,
            ),
            schema=_SCHEMA,
            schema_name="match_why",
            known_pii=None,
            conn=conn,
            timeout=20.0,
            allow_provider=allow_provider,
        )
        if not result.ok or not isinstance(result.data, dict):
            if str(result.error or "") == "ai_pending":
                deferred = True
            continue
        why = " ".join(str(result.data.get("why") or "").split())
        if len(why) < 12:
            continue
        if len(why) > 280:
            why = why[:277].rstrip() + "..."
        base = str(item.get("explanation") or "").strip()
        item["explanation"] = f"{base} · {why}" if base else why
        item["ai_why"] = True
    return deferred
