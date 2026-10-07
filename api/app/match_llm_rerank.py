"""AI #2: LLM relevance re-rank for top match pool (batch).

Soft-fails to the pre-LLM (struct / semantic-blended) scores.
final = 0.55·blended + 0.45·(relevance/5) when the model returns a score.
"""

from __future__ import annotations

import json
from typing import Any

from app.ai_flags import feature_on
from app.ai_gateway import complete_json

PURPOSE = "match_llm_rerank"
PROMPT_VERSION = "match-llm-rerank-v1"
DEFAULT_TOP = 10

W_BLENDED = 0.55
W_RELEVANCE = 0.45

_SYSTEM = (
    "You score how relevant each job is for the candidate using ONLY the facts "
    "in the user message. Return relevance as an integer 1–5 for each job_id.\n"
    "Rules:\n"
    "- Skill overlap 0 → relevance at most 2.\n"
    "- Seniority 2+ levels apart → relevance at most 2.\n"
    "- Do not invent skills, employers, or experience.\n"
    "- note: ≤12 words, optional, no PII.\n"
    "Respond with the JSON schema only."
)

_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "scores": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "job_id": {"type": "integer"},
                    "relevance": {"type": "integer"},
                    "note": {"type": "string"},
                },
                "required": ["job_id", "relevance", "note"],
            },
        },
    },
    "required": ["scores"],
}


def llm_rerank_enabled(conn=None) -> bool:
    return feature_on("llm_rerank", conn)


def _skill_names(raw: object, *, limit: int = 12) -> list[str]:
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    for item in raw:
        if isinstance(item, str):
            name = item.strip()
        elif isinstance(item, dict):
            name = str(item.get("name") or item.get("canonical_name") or "").strip()
        else:
            continue
        if name and name not in out:
            out.append(name)
        if len(out) >= limit:
            break
    return out


def _build_user(
    *,
    profile: dict,
    profile_version: str,
    matches: list[dict],
) -> str:
    prefs = profile.get("preferences") if isinstance(profile.get("preferences"), dict) else {}
    pref_bits: list[str] = []
    if prefs.get("remote") is True:
        pref_bits.append("remote")
    elif prefs.get("remote") is False:
        pref_bits.append("on-site")
    if prefs.get("relocation") is True:
        pref_bits.append("open_relocation")
    elif prefs.get("relocation") is False:
        pref_bits.append("no_relocation")
    years = profile.get("total_years")
    years_s = str(years) if isinstance(years, (int, float)) else ""
    lines = [
        f"ProfileVersion: {(profile_version or 'v0')[:80]}",
        f"Seniority: {str(profile.get('seniority') or '').strip() or '(none)'}",
        f"Years: {years_s or '(unknown)'}",
        "TopSkills: " + (", ".join(_skill_names(profile.get("skills"))) or "(none)"),
        "Preferences: " + (", ".join(pref_bits) if pref_bits else "(none)"),
        "Jobs:",
    ]
    for item in matches:
        have = item.get("have") if isinstance(item.get("have"), list) else []
        missing = item.get("missing") if isinstance(item.get("missing"), list) else []
        card = {
            "job_id": int(item.get("job_id") or 0),
            "title": str(item.get("title") or "").strip()[:120],
            "company": str(item.get("company") or "").strip()[:80],
            "have": [str(x) for x in have[:8]],
            "missing": [str(x) for x in missing[:8]],
            "job_seniority": str(item.get("job_seniority") or "").strip() or None,
            "remote": bool(item.get("remote")),
        }
        lines.append(json.dumps(card, ensure_ascii=False))
    lines.append("Score each job_id with relevance 1-5.")
    return "\n".join(lines)


def apply_llm_rerank(
    conn,
    *,
    matches: list[dict],
    profile: dict,
    profile_version: str,
    top_n: int = DEFAULT_TOP,
) -> bool:
    """Mutate top-N match scores with LLM relevance. Returns True if any applied."""
    if not llm_rerank_enabled(conn) or not matches:
        return False
    n = max(0, min(int(top_n or DEFAULT_TOP), len(matches)))
    if n == 0:
        return False
    subset = [m for m in matches[:n] if isinstance(m, dict) and m.get("job_id") is not None]
    if not subset:
        return False

    result = complete_json(
        purpose=PURPOSE,
        prompt_version=PROMPT_VERSION,
        system=_SYSTEM,
        user=_build_user(
            profile=profile if isinstance(profile, dict) else {},
            profile_version=profile_version,
            matches=subset,
        ),
        schema=_SCHEMA,
        schema_name="match_llm_rerank",
        known_pii=None,
        conn=conn,
        timeout=30.0,
    )
    if not result.ok or not isinstance(result.data, dict):
        return False

    raw_scores = result.data.get("scores")
    if not isinstance(raw_scores, list):
        return False

    by_id: dict[int, dict] = {}
    for row in raw_scores:
        if not isinstance(row, dict):
            continue
        try:
            jid = int(row.get("job_id"))
            rel = int(row.get("relevance"))
        except (TypeError, ValueError):
            continue
        if rel < 1 or rel > 5:
            continue
        note = " ".join(str(row.get("note") or "").split())[:80]
        by_id[jid] = {"relevance": rel, "note": note}

    if not by_id:
        return False

    applied = False
    for item in subset:
        try:
            jid = int(item["job_id"])
        except (TypeError, ValueError, KeyError):
            continue
        scored = by_id.get(jid)
        if not scored:
            continue
        rel = scored["relevance"]
        blended = float(item.get("score") or 0.0)
        final = round(W_BLENDED * blended + W_RELEVANCE * (rel / 5.0), 4)
        comps = item.get("components") if isinstance(item.get("components"), dict) else {}
        comps = dict(comps)
        comps["llm_relevance"] = rel
        if scored["note"]:
            comps["llm_note"] = scored["note"]
        item["components"] = comps
        item["score"] = final
        item["ai_llm_rerank"] = True
        applied = True
    return applied
