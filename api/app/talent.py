"""Employer talent search (browse-only MVP)."""

from __future__ import annotations

import json
import re

from app.cabinet_store import _LOCK, _connect
from app.consents import ensure_consent_tables
from app.cv_queue import ensure_cv_queue_tables

DEFAULT_PER_PAGE = 20
MAX_PER_PAGE = 40
MAX_SKILLS = 8
_WS = re.compile(r"\s+")


def _skills_from_data(raw: object) -> list[str]:
    data = raw
    if isinstance(raw, str):
        try:
            data = json.loads(raw or "{}")
        except json.JSONDecodeError:
            return []
    if not isinstance(data, dict):
        return []
    skills = data.get("skills") or []
    out: list[str] = []
    for item in skills:
        if isinstance(item, str):
            name = item.strip()
        elif isinstance(item, dict):
            name = str(item.get("name") or "").strip()
        else:
            continue
        if name and name not in out:
            out.append(name[:60])
        if len(out) >= 40:
            break
    return out


def _contact_bits(raw: object) -> tuple[str, str]:
    data = raw
    if isinstance(raw, str):
        try:
            data = json.loads(raw or "{}")
        except json.JSONDecodeError:
            return "", ""
    if not isinstance(data, dict):
        return "", ""
    contact = data.get("contact") if isinstance(data.get("contact"), dict) else {}
    city = _WS.sub(" ", str(contact.get("city") or "").strip())[:80]
    country = _WS.sub(" ", str(contact.get("country") or "").strip())[:80]
    return city, country


def _card(row, *, display_name: str = "") -> dict:
    visibility = (row["visibility"] or "hidden").strip().lower()
    skills = _skills_from_data(row["data"])[:MAX_SKILLS]
    city, country = _contact_bits(row["data"])
    card = {
        "id": int(row["id"]),
        "visibility": visibility,
        "headline": (row["headline"] or "").strip(),
        "seniority": (row["seniority"] or "").strip(),
        "total_years": row["total_years"],
        "skills": skills,
        "city": city,
        "country": country,
        "updated_at": row["updated_at"] or "",
    }
    if visibility == "public" and display_name:
        card["display_name"] = display_name
    return card


def search_talent(
    *,
    q: str = "",
    page: int = 1,
    per_page: int = DEFAULT_PER_PAGE,
) -> dict:
    from app.profiles import candidate_profile_for

    current = max(1, int(page or 1))
    size = min(MAX_PER_PAGE, max(1, int(per_page or DEFAULT_PER_PAGE)))
    needle = _WS.sub(" ", (q or "").strip())[:120]
    like = f"%{needle.lower()}%" if needle else ""

    with _LOCK:
        conn = _connect()
        try:
            ensure_cv_queue_tables(conn)
            ensure_consent_tables(conn)
            where = """
                cp.status = 'confirmed'
                AND LOWER(COALESCE(cp.visibility, '')) IN ('anonymous', 'public')
                AND EXISTS (
                    SELECT 1 FROM consent c
                    WHERE c.user_id = cp.user_id
                      AND c.kind = 'recruiter_visibility'
                      AND c.granted = 1
                )
            """
            params: list = []
            if like:
                where += """
                AND (
                    LOWER(COALESCE(cp.headline, '')) LIKE ?
                    OR LOWER(COALESCE(cp.seniority, '')) LIKE ?
                    OR LOWER(COALESCE(cp.data, '')) LIKE ?
                )
                """
                params.extend([like, like, like])

            total = int(
                conn.execute(
                    f"SELECT COUNT(*) FROM candidate_profile cp WHERE {where}",
                    params,
                ).fetchone()[0]
            )
            pages = (total + size - 1) // size if total else 0
            if pages and current > pages:
                current = pages
            offset = (current - 1) * size
            rows = conn.execute(
                f"""
                SELECT cp.id, cp.user_id, cp.data, cp.headline, cp.seniority,
                       cp.total_years, cp.visibility, cp.updated_at
                FROM candidate_profile cp
                WHERE {where}
                ORDER BY cp.updated_at DESC, cp.id DESC
                LIMIT ? OFFSET ?
                """,
                [*params, size, offset],
            ).fetchall()
        finally:
            conn.close()

    items = []
    for row in rows:
        visibility = (row["visibility"] or "").strip().lower()
        display_name = ""
        if visibility == "public":
            contact = candidate_profile_for(row["user_id"])
            display_name = (contact.get("display_name") or "").strip()
        items.append(_card(row, display_name=display_name))

    return {
        "items": items,
        "total": total,
        "page": current,
        "per_page": size,
        "pages": pages,
        "q": needle,
    }
