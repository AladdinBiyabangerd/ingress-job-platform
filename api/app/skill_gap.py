"""Skill-gap analysis for a target role (plan §7.2).

v1: target skills = role_skill_weight (signature skills). Market share from
skill_trend_daily is optional when the trends table is populated.
"""

from __future__ import annotations

import json
from typing import Any

from app.cv_profile import _profile_payload, ensure_profile_tables
from app.role_suggestions import (
    _build_skill_lookup,
    _candidate_skills,
    _matching_granted,
    _pick_locale,
)

DEFAULT_TOP = 15
MAX_TOP = 30

EXPLANATION = {
    "az": {
        "have": "Sizdə var",
        "missing": "Öyrənmək üçün",
        "empty_role": "Rol tapılmadı",
        "sep": " · ",
        "list": ", ",
    },
    "en": {
        "have": "You have",
        "missing": "Learn next",
        "empty_role": "Role not found",
        "sep": " · ",
        "list": ", ",
    },
    "ru": {
        "have": "У вас есть",
        "missing": "Изучить дальше",
        "empty_role": "Роль не найдена",
        "sep": " · ",
        "list": ", ",
    },
}


def _row_get(row, key: str, index: int):
    if row is None:
        return None
    try:
        return row[key]
    except (KeyError, IndexError, TypeError):
        return row[index]


def _parse_json_list(raw: object) -> list:
    if isinstance(raw, list):
        return raw
    if not isinstance(raw, str) or not raw.strip():
        return []
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return value if isinstance(value, list) else []


def clamp_top(value: int | None) -> int:
    if value is None:
        return DEFAULT_TOP
    try:
        n = int(value)
    except (TypeError, ValueError):
        return DEFAULT_TOP
    return max(1, min(MAX_TOP, n))


def _resolve_role(conn, role: str | None) -> dict | None:
    name = (role or "").strip()
    if not name:
        return None
    try:
        row = conn.execute(
            """
            SELECT id, canonical_name, category, academy_career_path_id
            FROM role_taxonomy
            WHERE lower(canonical_name) = lower(?)
            """,
            (name,),
        ).fetchone()
    except Exception:
        # Older DBs without academy_career_path_id.
        try:
            row = conn.execute(
                """
                SELECT id, canonical_name, category
                FROM role_taxonomy
                WHERE lower(canonical_name) = lower(?)
                """,
                (name,),
            ).fetchone()
        except Exception:
            return None
    if row is None:
        # Synonym match (JSON array stored as text).
        try:
            rows = conn.execute(
                """
                SELECT id, canonical_name, category, synonyms, academy_career_path_id
                FROM role_taxonomy
                """
            ).fetchall()
        except Exception:
            try:
                rows = conn.execute(
                    "SELECT id, canonical_name, category, synonyms FROM role_taxonomy"
                ).fetchall()
            except Exception:
                return None
        needle = name.lower()
        for item in rows:
            synonyms = _parse_json_list(_row_get(item, "synonyms", 3))
            if any(str(s).strip().lower() == needle for s in synonyms):
                row = item
                break
    if row is None:
        return None
    path_id = ""
    try:
        path_id = str(row["academy_career_path_id"] or "").strip()
    except (KeyError, IndexError, TypeError):
        # Tuple layouts:
        #   id, name, category, path
        #   id, name, category, synonyms, path
        for idx in (3, 4):
            try:
                value = row[idx]
            except (KeyError, IndexError, TypeError):
                continue
            # Synonyms column is JSON text starting with '[' — skip it.
            text = str(value or "").strip()
            if text.startswith("["):
                continue
            path_id = text.strip("/")
            break
    return {
        "id": int(_row_get(row, "id", 0)),
        "canonical_name": str(_row_get(row, "canonical_name", 1) or ""),
        "category": str(_row_get(row, "category", 2) or ""),
        "academy_career_path_id": path_id,
    }


def _role_target_skills(conn, role_id: int, top: int) -> list[dict[str, Any]]:
    try:
        rows = conn.execute(
            """
            SELECT
                w.skill_id,
                w.weight,
                s.canonical_name,
                s.academy_course_ids,
                COALESCE(w.group_key, '') AS group_key
            FROM role_skill_weight w
            JOIN skill_dictionary s ON s.id = w.skill_id
            WHERE w.role_id = ?
            ORDER BY w.weight DESC, s.canonical_name
            LIMIT ?
            """,
            (role_id, top),
        ).fetchall()
    except Exception:
        try:
            rows = conn.execute(
                """
                SELECT w.skill_id, w.weight, s.canonical_name, s.academy_course_ids
                FROM role_skill_weight w
                JOIN skill_dictionary s ON s.id = w.skill_id
                WHERE w.role_id = ?
                ORDER BY w.weight DESC, s.canonical_name
                LIMIT ?
                """,
                (role_id, top),
            ).fetchall()
        except Exception:
            return []
        return [
            {
                "skill_id": int(_row_get(row, "skill_id", 0)),
                "name": str(_row_get(row, "canonical_name", 2) or "").strip(),
                "weight": round(float(_row_get(row, "weight", 1) or 0), 4),
                "share": None,
                "growth": None,
                "academy_courses": [
                    str(x).strip()
                    for x in _parse_json_list(_row_get(row, "academy_course_ids", 3))
                    if str(x).strip()
                ],
                "group_key": "",
            }
            for row in rows
            if float(_row_get(row, "weight", 1) or 0) > 0
            and str(_row_get(row, "canonical_name", 2) or "").strip()
        ]
    out: list[dict[str, Any]] = []
    for row in rows:
        weight = float(_row_get(row, "weight", 1) or 0)
        name = str(_row_get(row, "canonical_name", 2) or "").strip()
        if weight <= 0 or not name:
            continue
        courses = [
            str(x).strip()
            for x in _parse_json_list(_row_get(row, "academy_course_ids", 3))
            if str(x).strip()
        ]
        out.append(
            {
                "skill_id": int(_row_get(row, "skill_id", 0)),
                "name": name,
                "weight": round(weight, 4),
                "share": None,
                "growth": None,
                "academy_courses": courses,
                "group_key": str(_row_get(row, "group_key", 4) or "").strip().lower(),
            }
        )
    return out


def _priority_key(row: dict) -> tuple:
    share = row.get("share")
    growth = row.get("growth")
    if share is not None:
        growth_factor = max(0.1, 1.0 + float(growth or 0.0))
        return (-float(share) * growth_factor, -float(row["weight"]), row["name"].lower())
    return (0.0, -float(row["weight"]), row["name"].lower())


def _format_explanation(lang: str, have: list[str], missing: list[str]) -> str:
    tpl = EXPLANATION[_pick_locale(lang)]
    parts: list[str] = []
    if have:
        parts.append(f"{tpl['have']}: {tpl['list'].join(have)}")
    if missing:
        parts.append(f"{tpl['missing']}: {tpl['list'].join(missing)}")
    return tpl["sep"].join(parts)


def skill_gap_payload(
    conn,
    *,
    user_id: str,
    role: str | None,
    top: int | None = None,
    lang: str | None = None,
) -> dict:
    ensure_profile_tables(conn)
    chosen_top = clamp_top(top)
    locale = _pick_locale(lang)
    matching = _matching_granted(conn, user_id)
    profile_payload = _profile_payload(conn, user_id=user_id)
    profile = profile_payload.get("profile") if isinstance(profile_payload.get("profile"), dict) else {}
    status = str(profile_payload.get("status") or "empty")

    base = {
        "role": None,
        "category": "",
        "academy_career_path": "",
        "have": [],
        "missing": [],
        "matching_consent": matching,
        "profile_status": status,
        "top": chosen_top,
        "source": "role_skill_weight",
        "explanation": "",
    }
    if not matching:
        return base

    resolved = _resolve_role(conn, role)
    if resolved is None:
        tpl = EXPLANATION[locale]
        base["explanation"] = tpl["empty_role"]
        return base

    base["role"] = resolved["canonical_name"]
    base["category"] = resolved["category"]
    base["academy_career_path"] = str(resolved.get("academy_career_path_id") or "").strip()
    targets = _role_target_skills(conn, resolved["id"], chosen_top)
    if not targets:
        return base

    from app.trends import trend_metrics_for_skills

    metrics = trend_metrics_for_skills(
        conn,
        skill_ids=[int(item["skill_id"]) for item in targets],
        category=resolved["category"],
    )
    enriched = False
    for item in targets:
        hit = metrics.get(int(item["skill_id"]))
        if not hit:
            continue
        item["share"] = hit.get("share")
        item["growth"] = hit.get("growth")
        enriched = True
    if enriched:
        base["source"] = "role_skill_weight+skill_trend_daily"

    lookup = _build_skill_lookup(conn)
    candidate = _candidate_skills(profile, lookup) if profile_payload.get("exists") else {}

    # OR-groups: if any member is on the profile, siblings are not "learn next".
    satisfied_groups: set[str] = set()
    for item in targets:
        group_key = str(item.get("group_key") or "").strip().lower()
        if group_key and int(item["skill_id"]) in candidate:
            satisfied_groups.add(group_key)

    have: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    have_ids: list[int] = []
    missing_ids: list[int] = []
    for item in targets:
        entry = {
            "name": item["name"],
            "weight": item["weight"],
            "share": item["share"],
            "growth": item["growth"],
            "academy_courses": item["academy_courses"],
        }
        group_key = str(item.get("group_key") or "").strip().lower()
        if item["skill_id"] in candidate:
            hit = candidate[item["skill_id"]]
            entry["years"] = hit.get("years")
            have.append(entry)
            have_ids.append(int(item["skill_id"]))
        elif group_key and group_key in satisfied_groups:
            continue
        else:
            missing.append(entry)
            missing_ids.append(int(item["skill_id"]))

    if have_ids and missing_ids:
        from app.trends import best_pair_share_for_missing

        pair_hits = best_pair_share_for_missing(
            conn,
            have_skill_ids=have_ids,
            missing_skill_ids=missing_ids,
            category=resolved["category"],
        )
        for entry, skill_id in zip(missing, missing_ids):
            hit = pair_hits.get(skill_id)
            if not hit:
                continue
            entry["often_with"] = {
                "base_name": hit["base_name"],
                "share": hit["share"],
                "co_ad_count": hit["co_ad_count"],
            }
            if enriched is False:
                enriched = True
                base["source"] = "role_skill_weight+skill_trend_daily"

    # Priority: share × growth when trends exist, else role weight.
    missing.sort(key=_priority_key)
    have.sort(key=_priority_key)

    base["have"] = have
    base["missing"] = missing
    base["explanation"] = _format_explanation(
        locale,
        [x["name"] for x in have],
        [x["name"] for x in missing],
    )
    return base


def skill_gap(
    *,
    user_id: str,
    role: str | None,
    top: int | None = None,
    lang: str | None = None,
) -> dict:
    from app.cabinet_store import _LOCK, _connect

    subject = (user_id or "").strip()
    with _LOCK:
        conn = _connect()
        try:
            return skill_gap_payload(
                conn,
                user_id=subject,
                role=role,
                top=top,
                lang=lang,
            )
        finally:
            conn.close()
