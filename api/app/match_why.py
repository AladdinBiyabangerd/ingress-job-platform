"""AI #2: optional short “why this match” sentence (plan §6.2).

Only top-N results, in ONE structured-output call ({"items":[{job_id, why}]}).
Soft-fails to template explanation. Cached via ai_gateway (complete_json) keyed
by prompt content: profile_version + the job cards sorted by job_id, without
volatile AI scores, so the same top-N set hits the cache in any order.
"""

from __future__ import annotations

import json
from typing import Any

from app.ai_flags import feature_on
from app.ai_gateway import complete_json

PURPOSE = "match_why"
PROMPT_VERSION = "match-why-v3"
DEFAULT_TOP = 5

_LANG_NAME = {"az": "Azerbaijani", "en": "English", "ru": "Russian"}

_SYSTEM = (
    "For EACH job in Jobs, write exactly one sentence (≤30 words) explaining why that job "
    "fits the candidate. Return one item per job_id, using the job_id given. "
    "Each sentence must name 1–2 concrete overlapping skills from that job's have list. "
    "Ban clichés: do not write “great fit”, “perfect”, “ideal”, or vague praise. "
    "Use only facts in the user context. Do not invent skills, employers, or salaries. "
    "No names, email, phone, or URLs. "
    "Write in the language named in the context."
)

_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "job_id": {"type": "integer"},
                    "why": {"type": "string"},
                },
                "required": ["job_id", "why"],
            },
        },
    },
    "required": ["items"],
}


def why_enabled(conn=None) -> bool:
    return feature_on("match_why", conn)


def _pick_locale(lang: str) -> str:
    text = (lang or "").strip().lower()[:2]
    return text if text in _LANG_NAME else "az"


def _job_card(match: dict) -> dict:
    have = match.get("have") if isinstance(match.get("have"), list) else []
    missing = match.get("missing") if isinstance(match.get("missing"), list) else []
    comps = match.get("components") if isinstance(match.get("components"), dict) else {}
    return {
        "job_id": int(match.get("job_id") or 0),
        "title": str(match.get("title") or "").strip()[:120],
        "company": str(match.get("company") or "").strip()[:80],
        "job_seniority": str(match.get("job_seniority") or "").strip() or None,
        "remote": bool(match.get("remote")),
        "relocation": bool(match.get("relocation")),
        "have": [str(x) for x in have[:12]],
        "missing_top3": [str(x) for x in missing[:3]],
        "skill_score": comps.get("skills"),
    }


def _build_user(
    *,
    lang: str,
    profile_version: str,
    matches: list[dict],
    candidate: dict | None = None,
) -> str:
    locale = _pick_locale(lang)
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
    lines = [
        f"Language: {_LANG_NAME[locale]}",
        f"ProfileVersion: {profile_version}",
        f"CandidateSeniority: {str(cand.get('seniority') or '').strip() or '(none)'}",
        f"CandidateYears: {years_s or '(unknown)'}",
        f"CandidatePrefs: {', '.join(pref_bits) if pref_bits else '(none)'}",
        "Jobs:",
    ]
    cards = sorted((_job_card(m) for m in matches), key=lambda c: c["job_id"])
    for card in cards:
        lines.append(json.dumps(card, ensure_ascii=False, sort_keys=True))
    lines.append("Return one why sentence per job_id in the JSON items array.")
    return "\n".join(lines)


def _clean_why(raw: object) -> str:
    why = " ".join(str(raw or "").split())
    if len(why) < 12:
        return ""
    if len(why) > 280:
        why = why[:277].rstrip() + "..."
    return why


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
    """Mutate matches[:top_n] explanations in place when AI succeeds (one batch call).

    Returns True when the call was deferred (``ai_pending``).
    """
    if not why_enabled(conn) or not matches:
        return False
    n = max(0, min(int(top_n or DEFAULT_TOP), len(matches)))
    subset = [
        item for item in matches[:n] if isinstance(item, dict) and item.get("job_id") is not None
    ]
    if not subset:
        return False
    version = (profile_version or "v0")[:80]
    result = complete_json(
        purpose=PURPOSE,
        prompt_version=PROMPT_VERSION,
        system=_SYSTEM,
        user=_build_user(
            lang=lang,
            profile_version=version,
            matches=subset,
            candidate=candidate,
        ),
        schema=_SCHEMA,
        schema_name="match_why",
        known_pii=None,
        conn=conn,
        timeout=30.0,
        allow_provider=allow_provider,
    )
    if not result.ok or not isinstance(result.data, dict):
        return str(result.error or "") == "ai_pending"
    raw_items = result.data.get("items")
    if not isinstance(raw_items, list):
        return False
    wanted = {int(item["job_id"]) for item in subset}
    by_id: dict[int, str] = {}
    for row in raw_items:
        if not isinstance(row, dict):
            continue
        try:
            jid = int(row.get("job_id"))
        except (TypeError, ValueError):
            continue
        if jid not in wanted or jid in by_id:
            continue
        why = _clean_why(row.get("why"))
        if why:
            by_id[jid] = why
    for item in subset:
        why = by_id.get(int(item["job_id"]))
        if not why:
            continue
        base = str(item.get("explanation") or "").strip()
        item["explanation"] = f"{base} · {why}" if base else why
        item["ai_why"] = True
    return False
