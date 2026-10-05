"""Deterministic role suggestions from profile skills × role taxonomy (plan §6.1).

rol_score = Σ(matched) / Σ(totals) with OR-groups (max within group), then
thin-role dampen and optional headline affinity. No AI.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from typing import Any

from app.consents import _grants_for, ensure_consent_tables
from app.cv_profile import _profile_payload, ensure_profile_tables

LOCALES = ("az", "en", "ru")
DEFAULT_LIMIT = 5
MAX_LIMIT = 10
YEARS_FULL = 5.0
YEARS_MIN_FACTOR = 0.5
YEARS_MAX_FACTOR = 1.5
MIN_ROLE_WEIGHT = 1.0
HEADLINE_BOOST = 1.15
GROUP_MISSING_CAP = 3

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


def _profile_affinity_texts(profile: dict) -> list[str]:
    texts: list[str] = []
    if not isinstance(profile, dict):
        return texts
    headline = str(profile.get("headline") or "").strip()
    if headline:
        texts.append(headline)
    desired = profile.get("desired_roles")
    if isinstance(desired, list):
        for item in desired:
            if isinstance(item, str):
                value = item.strip()
            elif isinstance(item, dict):
                value = str(item.get("name") or item.get("title") or "").strip()
            else:
                value = ""
            if value:
                texts.append(value)
    history = profile.get("work_history")
    if isinstance(history, list):
        for item in history:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "").strip()
            if title:
                texts.append(title)
    return texts


def _label_matches_text(text: str, label: str) -> bool:
    hay = (text or "").strip().lower()
    needle = (label or "").strip().lower()
    if not hay or not needle:
        return False
    if needle in hay:
        return True
    words = [w for w in re.split(r"[\s/|,+\-]+", needle) if len(w) >= 2]
    if len(words) >= 2 and all(w in hay for w in words):
        return True
    return False


def _role_affinity(profile: dict, canonical: str, synonyms: list[str]) -> bool:
    texts = _profile_affinity_texts(profile)
    if not texts:
        return False
    labels = [canonical, *synonyms]
    for text in texts:
        for label in labels:
            if _label_matches_text(text, label):
                return True
    return False


def _load_role_weights(conn, role_id: int) -> list[dict[str, Any]]:
    """Load signature skills; group_key falls back to '' on older schemas."""
    try:
        rows = conn.execute(
            """
            SELECT w.skill_id, w.weight, s.canonical_name, COALESCE(w.group_key, '') AS group_key
            FROM role_skill_weight w
            JOIN skill_dictionary s ON s.id = w.skill_id
            WHERE w.role_id = ?
            ORDER BY w.weight DESC, s.canonical_name
            """,
            (role_id,),
        ).fetchall()
    except Exception:
        try:
            rows = conn.execute(
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
            return []
        return [
            {
                "skill_id": int(_row_get(row, "skill_id", 0)),
                "weight": float(_row_get(row, "weight", 1) or 0),
                "name": str(_row_get(row, "canonical_name", 2) or "").strip(),
                "group_key": "",
            }
            for row in rows
        ]
    out: list[dict[str, Any]] = []
    for row in rows:
        name = str(_row_get(row, "canonical_name", 2) or "").strip()
        weight = float(_row_get(row, "weight", 1) or 0)
        if weight <= 0 or not name:
            continue
        out.append(
            {
                "skill_id": int(_row_get(row, "skill_id", 0)),
                "weight": weight,
                "name": name,
                "group_key": str(_row_get(row, "group_key", 3) or "").strip().lower(),
            }
        )
    return out


def _score_role_weights(
    weights: list[dict[str, Any]],
    candidate: dict[int, dict],
) -> tuple[float, float, list[str], list[str]] | None:
    """Return (matched, total, have, missing) or None if unscorable."""
    ungrouped: list[dict[str, Any]] = []
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in weights:
        key = item["group_key"]
        if key:
            groups[key].append(item)
        else:
            ungrouped.append(item)

    total = 0.0
    matched = 0.0
    have: list[str] = []
    missing: list[str] = []

    for item in ungrouped:
        weight = float(item["weight"])
        total += weight
        hit = candidate.get(int(item["skill_id"]))
        if hit is None:
            missing.append(item["name"])
            continue
        matched += weight * float(hit["factor"])
        have.append(item["name"])

    for _key, members in groups.items():
        if not members:
            continue
        group_total = max(float(m["weight"]) for m in members)
        total += group_total
        best_matched = 0.0
        matched_names: list[str] = []
        for member in members:
            hit = candidate.get(int(member["skill_id"]))
            if hit is None:
                continue
            contrib = float(member["weight"]) * float(hit["factor"])
            if contrib > best_matched:
                best_matched = contrib
            matched_names.append(member["name"])
        if matched_names:
            matched += best_matched
            # Prefer higher-weight matched names first for explanation.
            matched_names.sort(
                key=lambda name: (
                    -next(float(m["weight"]) for m in members if m["name"] == name),
                    name.lower(),
                )
            )
            have.extend(matched_names)
        else:
            alts = sorted(
                members,
                key=lambda m: (-float(m["weight"]), m["name"].lower()),
            )[:GROUP_MISSING_CAP]
            missing.extend(m["name"] for m in alts)

    if total <= 0 or matched <= 0:
        return None
    return matched, total, have, missing


def _score_roles(
    conn,
    *,
    candidate: dict[int, dict],
    profile: dict,
    limit: int,
    lang: str,
) -> list[dict[str, Any]]:
    try:
        try:
            roles = conn.execute(
                """
                SELECT id, canonical_name, category, synonyms, academy_career_path_id
                FROM role_taxonomy
                ORDER BY canonical_name
                """
            ).fetchall()
        except Exception:
            roles = conn.execute(
                """
                SELECT id, canonical_name, category, synonyms
                FROM role_taxonomy
                ORDER BY canonical_name
                """
            ).fetchall()
    except Exception:
        return []

    scored: list[dict[str, Any]] = []
    for role in roles:
        role_id = int(_row_get(role, "id", 0))
        weights = _load_role_weights(conn, role_id)
        if not weights:
            continue

        result = _score_role_weights(weights, candidate)
        if result is None:
            continue
        matched, total, have, missing = result
        score = matched / total
        # Thin roles (sparse signature weights) cannot dominate via 100% of a tiny set.
        score *= min(1.0, total / MIN_ROLE_WEIGHT)

        canonical = str(_row_get(role, "canonical_name", 1) or "")
        synonyms = _parse_synonyms(_row_get(role, "synonyms", 3))
        if _role_affinity(profile, canonical, synonyms):
            score = min(1.0, score * HEADLINE_BOOST)

        score = round(score, 4)
        path_id = ""
        try:
            path_id = str(_row_get(role, "academy_career_path_id", 4) or "").strip()
        except Exception:
            path_id = ""
        scored.append(
            {
                "canonical_name": canonical,
                "category": str(_row_get(role, "category", 2) or ""),
                "score": score,
                "have": have,
                "missing": missing,
                "academy_career_path": path_id,
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
    base["roles"] = _score_roles(
        conn,
        candidate=candidate,
        profile=profile,
        limit=chosen_limit,
        lang=locale,
    )
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
