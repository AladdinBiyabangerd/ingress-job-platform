"""Deterministic role suggestions from profile skills × role taxonomy (plan §6.1).

rol_score = Σ(matched_signature_weight × years_factor) / Σ(all_signature_weights)
Top-N with template have/missing explanation. No AI.
"""

from __future__ import annotations

import json
from typing import Any

from app.consents import _grants_for, ensure_consent_tables
from app.cv_profile import _profile_payload, ensure_profile_tables

LOCALES = ("az", "en", "ru")
DEFAULT_LIMIT = 5
MAX_LIMIT = 10
YEARS_FULL = 5.0
YEARS_MIN_FACTOR = 0.5
YEARS_MAX_FACTOR = 1.5

EXPLANATION = {
    "az": {"have": "Sizdə var", "missing": "Çatışmır", "sep": " · ", "list": ", "},
    "en": {"have": "You have", "missing": "Missing", "sep": " · ", "list": ", "},
    "ru": {"have": "У вас есть", "missing": "Не хватает", "sep": " · ", "list": ", "},
}


def _pick_locale(lang: str | None) -> str:
    code = (lang or "az").strip().lower()[:2]
    return code if code in LOCALES else "az"


def clamp_limit(value: int | None) -> int:
    if value is None:
        return DEFAULT_LIMIT
    try:
        n = int(value)
    except (TypeError, ValueError):
        return DEFAULT_LIMIT
    return max(1, min(MAX_LIMIT, n))


def years_factor(years: float | None) -> float:
    if years is None:
        return 1.0
    try:
        y = float(years)
    except (TypeError, ValueError):
        return 1.0
    if y < 0:
        y = 0.0
    return max(YEARS_MIN_FACTOR, min(YEARS_MAX_FACTOR, y / YEARS_FULL))


def _row_get(row, key: str, index: int):
    if row is None:
        return None
    try:
        return row[key]
    except (KeyError, IndexError, TypeError):
        return row[index]


def _parse_synonyms(raw: object) -> list[str]:
    if isinstance(raw, list):
        return [str(x) for x in raw if str(x).strip()]
    if not isinstance(raw, str) or not raw.strip():
        return []
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(value, list):
        return []
    return [str(x) for x in value if str(x).strip()]


def _build_skill_lookup(conn) -> dict[str, tuple[int, str]]:
    """Map lower(canonical|synonym) → (skill_id, canonical_name)."""
    mapping: dict[str, tuple[int, str]] = {}
    try:
        rows = conn.execute(
            "SELECT id, canonical_name, synonyms FROM skill_dictionary"
        ).fetchall()
    except Exception:
        return mapping
    for row in rows:
        skill_id = int(_row_get(row, "id", 0))
        name = str(_row_get(row, "canonical_name", 1) or "").strip()
        if not name:
            continue
        mapping[name.lower()] = (skill_id, name)
        for syn in _parse_synonyms(_row_get(row, "synonyms", 2)):
            key = syn.strip().lower()
            if key and key not in mapping:
                mapping[key] = (skill_id, name)
    return mapping


def _candidate_skills(profile: dict, lookup: dict[str, tuple[int, str]]) -> dict[int, dict]:
    """skill_id → {name, years, factor} for resolved profile skills."""
    out: dict[int, dict] = {}
    raw = profile.get("skills") if isinstance(profile, dict) else None
    if not isinstance(raw, list):
        return out
    for item in raw:
        if isinstance(item, str):
            name, years = item.strip(), None
        elif isinstance(item, dict):
            name = str(item.get("name") or "").strip()
            years = item.get("years")
            if years is not None:
                try:
                    years = float(years)
                except (TypeError, ValueError):
                    years = None
        else:
            continue
        if not name:
            continue
        hit = lookup.get(name.lower())
        if hit is None:
            continue
        skill_id, canonical = hit
        factor = years_factor(years)
        prev = out.get(skill_id)
        if prev is None or factor > prev["factor"]:
            out[skill_id] = {"name": canonical, "years": years, "factor": factor}
    return out


def _format_explanation(lang: str, have: list[str], missing: list[str]) -> str:
    tpl = EXPLANATION[_pick_locale(lang)]
    parts: list[str] = []
    if have:
        parts.append(f"{tpl['have']}: {tpl['list'].join(have)}")
    if missing:
        parts.append(f"{tpl['missing']}: {tpl['list'].join(missing)}")
    return tpl["sep"].join(parts)


def _matching_granted(conn, user_id: str) -> bool:
    ensure_consent_tables(conn)
    grants = _grants_for(conn, user_id)
    item = grants.get("matching") or {}
    return bool(item.get("granted"))


def _score_roles(
    conn,
    *,
    candidate: dict[int, dict],
    limit: int,
    lang: str,
) -> list[dict[str, Any]]:
    try:
        roles = conn.execute(
            """
            SELECT id, canonical_name, category
            FROM role_taxonomy
            ORDER BY canonical_name
            """
        ).fetchall()
    except Exception:
        return []

    scored: list[dict[str, Any]] = []
    for role in roles:
        role_id = int(_row_get(role, "id", 0))
        try:
            weights = conn.execute(
                """
                SELECT w.skill_id, w.weight, s.canonical_name
                FROM role_skill_weight w
                JOIN skill_dictionary s ON s.id = w.skill_id
                WHERE w.role_id = ?
                ORDER BY w.weight DESC, s.canonical_name
                """,
                (role_id,),
            ).fetchall()
        except Exception:
            continue
        if not weights:
            continue

        total = 0.0
        matched = 0.0
        have: list[str] = []
        missing: list[str] = []
        for row in weights:
            skill_id = int(_row_get(row, "skill_id", 0))
            weight = float(_row_get(row, "weight", 1) or 0)
            skill_name = str(_row_get(row, "canonical_name", 2) or "")
            if weight <= 0 or not skill_name:
                continue
            total += weight
            hit = candidate.get(skill_id)
            if hit is None:
                missing.append(skill_name)
                continue
            matched += weight * float(hit["factor"])
            have.append(skill_name)

        if total <= 0 or matched <= 0:
            continue
        score = round(matched / total, 4)
        scored.append(
            {
                "canonical_name": str(_row_get(role, "canonical_name", 1) or ""),
                "category": str(_row_get(role, "category", 2) or ""),
                "score": score,
                "have": have,
                "missing": missing,
                "explanation": _format_explanation(lang, have, missing),
            }
        )

    scored.sort(key=lambda row: (-row["score"], row["canonical_name"].lower()))
    return scored[:limit]


def suggest_roles_payload(
    conn,
    *,
    user_id: str,
    limit: int | None = None,
    lang: str | None = None,
) -> dict:
    ensure_profile_tables(conn)
    chosen_limit = clamp_limit(limit)
    locale = _pick_locale(lang)
    profile_payload = _profile_payload(conn, user_id=user_id)
    status = str(profile_payload.get("status") or "empty")
    profile = profile_payload.get("profile") if isinstance(profile_payload.get("profile"), dict) else {}
    raw_skills = profile.get("skills") if isinstance(profile.get("skills"), list) else []
    skill_count = len(raw_skills)
    matching = _matching_granted(conn, user_id)

    base = {
        "roles": [],
        "limit": chosen_limit,
        "profile_status": status,
        "matching_consent": matching,
        "skill_count": skill_count,
    }
    if not matching:
        return base
    if not profile_payload.get("exists") or skill_count == 0:
        return base

    lookup = _build_skill_lookup(conn)
    candidate = _candidate_skills(profile, lookup)
    base["roles"] = _score_roles(conn, candidate=candidate, limit=chosen_limit, lang=locale)
    return base


def suggest_roles(*, user_id: str, limit: int | None = None, lang: str | None = None) -> dict:
    from app.cabinet_store import _LOCK, _connect

    subject = (user_id or "").strip()
    with _LOCK:
        conn = _connect()
        try:
            return suggest_roles_payload(conn, user_id=subject, limit=limit, lang=lang)
        finally:
            conn.close()
