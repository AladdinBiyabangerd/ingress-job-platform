"""Structured CV candidate_profile read/edit/confirm (Phase 1 review).

Plan §5.3 / §12 / §13.1: GET+PUT /api/profile over jobs-DB candidate_profile.
Separate from accounts.sqlite candidate_profiles (contact-only).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from threading import Lock
from typing import Any

from app.cv_queue import ensure_cv_queue_tables

PROFILE_STATUSES = ("draft", "confirmed")
SENIORITY_VALUES = ("", "intern", "junior", "middle", "senior", "lead", "principal", "staff")
PARSE_QUEUE_OPEN = ("pending", "processing")
LOW_CONFIDENCE = 0.55
SKILL_NAME_MAX = 60
SKILL_YEARS_MAX = 60.0
HEADLINE_MAX = 200
SUMMARY_MAX = 2000
TEXT_SHORT = 120

EDIT_LOG_SCHEMA = """
CREATE TABLE IF NOT EXISTS profile_edit_log (
    id INTEGER PRIMARY KEY,
    user_id TEXT NOT NULL,
    profile_id INTEGER,
    action TEXT NOT NULL,
    before_data TEXT NOT NULL DEFAULT '{}',
    after_data TEXT NOT NULL DEFAULT '{}',
    before_status TEXT NOT NULL DEFAULT '',
    after_status TEXT NOT NULL DEFAULT '',
    ts TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS profile_edit_log_user ON profile_edit_log(user_id, id);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


_PROFILE_ENSURED: set[str] = set()
_PROFILE_LOCK = Lock()


def ensure_profile_tables(conn) -> None:
    from app.jobs_db import schema_cache_key

    ensure_cv_queue_tables(conn)
    key = schema_cache_key()
    if key in _PROFILE_ENSURED:
        return
    with _PROFILE_LOCK:
        if key in _PROFILE_ENSURED:
            return
        conn.executescript(EDIT_LOG_SCHEMA)
        _PROFILE_ENSURED.add(key)


def _row_get(row, key: str, index: int):
    if row is None:
        return None
    try:
        return row[key]
    except (KeyError, IndexError, TypeError):
        return row[index]


def _parse_data(raw: object) -> dict:
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str) or not raw.strip():
        return {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def _empty_profile() -> dict:
    return {
        "contact": {"full_name": "", "email": "", "phone": "", "city": "", "country": ""},
        "links": {"linkedin_url": "", "github": "", "portfolio": "", "other": []},
        "headline": "",
        "summary": "",
        "seniority": "",
        "total_years": None,
        "work_history": [],
        "skills": [],
        "languages": [],
        "education": [],
        "desired_roles": [],
        "preferences": {
            "remote": None,
            "relocation": None,
            "relocation_countries": [],
            "needs_visa_sponsorship": None,
        },
        "salary_expectation": {"min": None, "currency": None, "period": "year"},
        "parse_meta": {"method": "", "confidence": None, "parser_version": "", "source": ""},
    }


def _as_str(value: object, *, max_len: int) -> str:
    if value is None:
        return ""
    return str(value).strip()[:max_len]


def _as_float(value: object) -> float | None:
    """Parse a non-negative float (confidence, etc.). Keeps 2 decimal places."""
    if value is None or value == "":
        return None
    try:
        raw = value
        if isinstance(raw, str):
            raw = raw.strip().replace(",", ".")
        number = float(raw)
    except (TypeError, ValueError):
        return None
    if number < 0 or number > SKILL_YEARS_MAX:
        return None
    return round(number, 2)


def _as_years(value: object) -> float | None:
    """Experience years as whole years (1, 2, 3…) — drop fake precision like 1.28."""
    number = _as_float(value)
    if number is None:
        return None
    return float(max(0, int(round(number))))


def _normalize_skill(item: object) -> dict | None:
    if isinstance(item, str):
        name = item.strip()[:SKILL_NAME_MAX]
        if not name:
            return None
        return {"name": name, "years": None, "level": "", "source": "user"}
    if not isinstance(item, dict):
        return None
    name = _as_str(item.get("name"), max_len=SKILL_NAME_MAX)
    if not name:
        return None
    years = _as_years(item.get("years"))
    level = _as_str(item.get("level"), max_len=40)
    source = _as_str(item.get("source") or "user", max_len=40) or "user"
    return {"name": name, "years": years, "level": level, "source": source}


def _normalize_work(item: object) -> dict | None:
    if not isinstance(item, dict):
        return None
    title = _as_str(item.get("title"), max_len=TEXT_SHORT)
    company = _as_str(item.get("company"), max_len=TEXT_SHORT)
    if not title and not company:
        return None
    skills = []
    for skill in item.get("skills") or []:
        if isinstance(skill, str) and skill.strip():
            skills.append(skill.strip()[:SKILL_NAME_MAX])
        elif isinstance(skill, dict):
            name = _as_str(skill.get("name"), max_len=SKILL_NAME_MAX)
            if name:
                skills.append(name)
    employment_type = _as_str(item.get("employment_type"), max_len=40).lower()
    if employment_type not in {
        "",
        "internship",
        "full_time",
        "part_time",
        "contract",
        "freelance",
    }:
        employment_type = ""
    return {
        "title": title,
        "company": company,
        "location": _as_str(item.get("location"), max_len=TEXT_SHORT),
        "start": _as_str(item.get("start"), max_len=20),
        "end": _as_str(item.get("end"), max_len=20) or None,
        "summary": _as_str(item.get("summary"), max_len=SUMMARY_MAX),
        "skills": skills[:40],
        "employment_type": employment_type,
    }


def _normalize_language(item: object) -> dict | None:
    if not isinstance(item, dict):
        return None
    code = _as_str(item.get("code"), max_len=16).lower()
    if not code:
        return None
    return {"code": code, "level": _as_str(item.get("level"), max_len=40)}


def _normalize_education(item: object) -> dict | None:
    if not isinstance(item, dict):
        return None
    degree = _as_str(item.get("degree"), max_len=TEXT_SHORT)
    field = _as_str(item.get("field"), max_len=TEXT_SHORT)
    school = _as_str(item.get("school"), max_len=TEXT_SHORT)
    year = item.get("year")
    year_value: int | None
    try:
        year_value = int(year) if year not in (None, "") else None
    except (TypeError, ValueError):
        year_value = None
    if year_value is not None and (year_value < 1950 or year_value > 2100):
        year_value = None
    if not any((degree, field, school, year_value)):
        return None
    return {"degree": degree, "field": field, "school": school, "year": year_value}


def normalize_profile_data(raw: object, *, base: dict | None = None) -> dict:
    """Coerce user/parser JSON into the §5.2 shape used by the review UI."""
    data = dict(base or _empty_profile())
    incoming = raw if isinstance(raw, dict) else {}

    contact_in = incoming.get("contact") if isinstance(incoming.get("contact"), dict) else {}
    contact = dict(data.get("contact") or {})
    for key in ("full_name", "email", "phone", "city", "country"):
        if key in contact_in:
            contact[key] = _as_str(contact_in.get(key), max_len=TEXT_SHORT)
    data["contact"] = contact

    links_in = incoming.get("links") if isinstance(incoming.get("links"), dict) else {}
    links = dict(data.get("links") or {})
    for key in ("linkedin_url", "github", "portfolio"):
        if key in links_in:
            links[key] = _as_str(links_in.get(key), max_len=300)
    if "other" in links_in and isinstance(links_in["other"], list):
        links["other"] = [
            _as_str(item, max_len=300) for item in links_in["other"] if _as_str(item, max_len=300)
        ][:20]
    # Parser stores links under contact.links; lift into top-level links.
    nested = contact_in.get("links") if isinstance(contact_in.get("links"), dict) else {}
    for src, dest in (("linkedin", "linkedin_url"), ("github", "github"), ("portfolio", "portfolio")):
        if nested.get(src) and not links.get(dest):
            links[dest] = _as_str(nested.get(src), max_len=300)
    data["links"] = links
    if nested:
        contact["links"] = {
            "linkedin": links.get("linkedin_url") or _as_str(nested.get("linkedin"), max_len=300),
            "github": links.get("github") or _as_str(nested.get("github"), max_len=300),
            "portfolio": links.get("portfolio") or _as_str(nested.get("portfolio"), max_len=300),
        }
        data["contact"] = contact

    if "headline" in incoming:
        data["headline"] = _as_str(incoming.get("headline"), max_len=HEADLINE_MAX)
    if "summary" in incoming or "about" in incoming:
        raw_summary = incoming.get("summary") if "summary" in incoming else incoming.get("about")
        data["summary"] = _as_str(raw_summary, max_len=SUMMARY_MAX)
    if "seniority" in incoming:
        seniority = _as_str(incoming.get("seniority"), max_len=40).lower()
        data["seniority"] = seniority if seniority in SENIORITY_VALUES else data.get("seniority") or ""
    if "total_years" in incoming:
        data["total_years"] = _as_years(incoming.get("total_years"))

    if "skills" in incoming and isinstance(incoming.get("skills"), list):
        skills = []
        seen: set[str] = set()
        for item in incoming["skills"][:80]:
            skill = _normalize_skill(item)
            if not skill:
                continue
            key = skill["name"].lower()
            if key in seen:
                continue
            seen.add(key)
            skills.append(skill)
        data["skills"] = skills

    if "work_history" in incoming and isinstance(incoming.get("work_history"), list):
        jobs = []
        for item in incoming["work_history"][:40]:
            job = _normalize_work(item)
            if job:
                jobs.append(job)
        data["work_history"] = jobs

    if "languages" in incoming and isinstance(incoming.get("languages"), list):
        langs = []
        for item in incoming["languages"][:20]:
            lang = _normalize_language(item)
            if lang:
                langs.append(lang)
        data["languages"] = langs

    if "education" in incoming and isinstance(incoming.get("education"), list):
        edu = []
        for item in incoming["education"][:20]:
            row = _normalize_education(item)
            if row:
                edu.append(row)
        data["education"] = edu

    if "desired_roles" in incoming and isinstance(incoming.get("desired_roles"), list):
        data["desired_roles"] = [
            _as_str(item, max_len=TEXT_SHORT)
            for item in incoming["desired_roles"]
            if _as_str(item, max_len=TEXT_SHORT)
        ][:20]

    prefs_in = incoming.get("preferences") if isinstance(incoming.get("preferences"), dict) else None
    if prefs_in is not None:
        prefs = dict(data.get("preferences") or {})
        for key in ("remote", "relocation", "needs_visa_sponsorship"):
            if key in prefs_in:
                value = prefs_in.get(key)
                prefs[key] = None if value is None else bool(value)
        if "relocation_countries" in prefs_in and isinstance(prefs_in["relocation_countries"], list):
            prefs["relocation_countries"] = [
                _as_str(code, max_len=8).upper()
                for code in prefs_in["relocation_countries"]
                if _as_str(code, max_len=8)
            ][:30]
        data["preferences"] = prefs

    meta_in = incoming.get("parse_meta") if isinstance(incoming.get("parse_meta"), dict) else None
    if meta_in is not None:
        meta = dict(data.get("parse_meta") or {})
        for key in ("method", "parser_version", "source", "error", "parse_source", "ai_fallback", "ai_error"):
            if key in meta_in:
                meta[key] = _as_str(meta_in.get(key), max_len=80)
        if "confidence" in meta_in:
            conf = _as_float(meta_in.get("confidence"))
            meta["confidence"] = None if conf is None else max(0.0, min(1.0, conf))
        if "sections_found" in meta_in and isinstance(meta_in["sections_found"], list):
            meta["sections_found"] = [
                _as_str(item, max_len=40) for item in meta_in["sections_found"] if _as_str(item, max_len=40)
            ][:40]
        quality_in = meta_in.get("quality") if isinstance(meta_in.get("quality"), dict) else None
        if quality_in is not None:
            q_score = _as_float(quality_in.get("score"))
            q_before = _as_float(quality_in.get("score_before"))
            meta["quality"] = {
                "score": None if q_score is None else max(0.0, min(1.0, q_score)),
                "score_before": None if q_before is None else max(0.0, min(1.0, q_before)),
                "threshold": max(0.0, min(1.0, _as_float(quality_in.get("threshold")) or 0.0)),
                "issues": [
                    _as_str(i, max_len=40)
                    for i in (quality_in.get("issues") if isinstance(quality_in.get("issues"), list) else [])
                    if _as_str(i, max_len=40)
                ][:20],
            }
        template_in = meta_in.get("template") if isinstance(meta_in.get("template"), dict) else None
        if template_in is not None:
            tpl_id = _as_str(template_in.get("id"), max_len=40)
            conf = _as_float(template_in.get("confidence"))
            meta["template"] = {
                "id": tpl_id or None,
                "name": _as_str(template_in.get("name"), max_len=80) if tpl_id else "",
                "confidence": None if conf is None else max(0.0, min(1.0, conf)),
                "applied": bool(template_in.get("applied")) if tpl_id else False,
            }
        ocr_in = meta_in.get("ocr") if isinstance(meta_in.get("ocr"), dict) else None
        if ocr_in is not None:
            status = _as_str(ocr_in.get("status"), max_len=20)
            if status in {"used", "unavailable", "disabled", "empty"}:
                meta["ocr"] = {"status": status}
                reason = _as_str(ocr_in.get("reason"), max_len=60)
                if reason:
                    meta["ocr"]["reason"] = reason
        data["parse_meta"] = meta

    # Keep top-level mirrors in sync with columns the UI edits.
    data["headline"] = _as_str(data.get("headline"), max_len=HEADLINE_MAX)
    data["summary"] = _as_str(data.get("summary"), max_len=SUMMARY_MAX)
    data["seniority"] = _as_str(data.get("seniority"), max_len=40)
    return data


def _low_confidence_fields(profile: dict, confidence: float | None) -> list[str]:
    fields: list[str] = []
    overall_low = confidence is None or confidence < LOW_CONFIDENCE
    if not (profile.get("headline") or "").strip():
        fields.append("headline")
    elif overall_low:
        fields.append("headline")
    if not (profile.get("seniority") or "").strip():
        fields.append("seniority")
    if profile.get("total_years") is None:
        fields.append("total_years")
    if not profile.get("skills"):
        fields.append("skills")
    elif overall_low:
        fields.append("skills")
    work = profile.get("work_history") or []
    if not work:
        fields.append("work_history")
    elif overall_low:
        fields.append("work_history")
    contact = profile.get("contact") if isinstance(profile.get("contact"), dict) else {}
    if not (contact.get("email") or contact.get("phone") or contact.get("full_name")):
        fields.append("contact")
    return fields


def _parse_queue_status(conn, user_id: str) -> str:
    row = conn.execute(
        """
        SELECT status FROM parse_cv_queue
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (user_id,),
    ).fetchone()
    if row is None:
        return "none"
    status = _row_get(row, "status", 0) or "none"
    return str(status)


def _profile_payload(conn, *, user_id: str) -> dict:
    ensure_profile_tables(conn)
    row = conn.execute(
        """
        SELECT id, cv_file_key, data, headline, seniority, total_years,
               status, parse_method, confidence, visibility, updated_at
        FROM candidate_profile
        WHERE user_id = ?
        """,
        (user_id,),
    ).fetchone()
    parse_status = _parse_queue_status(conn, user_id)
    if row is None:
        return {
            "exists": False,
            "status": "empty",
            "parse_status": parse_status,
            "cv_file_key": "",
            "headline": "",
            "seniority": "",
            "total_years": None,
            "confidence": None,
            "parse_method": "",
            "visibility": "hidden",
            "updated_at": None,
            "low_confidence": True,
            "low_confidence_fields": ["headline", "skills", "work_history"],
            "needs_review": parse_status in PARSE_QUEUE_OPEN,
            "profile": _empty_profile(),
        }

    data = _parse_data(_row_get(row, "data", 2))
    profile = normalize_profile_data(data, base=_empty_profile())
    headline = _as_str(_row_get(row, "headline", 3) or profile.get("headline"), max_len=HEADLINE_MAX)
    seniority = _as_str(_row_get(row, "seniority", 4) or profile.get("seniority"), max_len=40)
    total_years = _row_get(row, "total_years", 5)
    if total_years is None:
        total_years = profile.get("total_years")
    total_years = _as_years(total_years)
    profile["headline"] = headline
    profile["seniority"] = seniority
    profile["total_years"] = total_years
    confidence = _as_float(_row_get(row, "confidence", 8))
    meta = profile.setdefault("parse_meta", {})
    if confidence is not None:
        meta["confidence"] = confidence
    method = _as_str(_row_get(row, "parse_method", 7), max_len=40)
    if method:
        meta["method"] = method
    status = _as_str(_row_get(row, "status", 6), max_len=20) or "draft"
    if status not in PROFILE_STATUSES:
        status = "draft"
    low_fields = _low_confidence_fields(profile, confidence)
    return {
        "exists": True,
        "id": int(_row_get(row, "id", 0)),
        "status": status,
        "parse_status": parse_status,
        "cv_file_key": _as_str(_row_get(row, "cv_file_key", 1), max_len=500),
        "headline": headline,
        "seniority": seniority,
        "total_years": total_years,
        "confidence": confidence,
        "parse_method": method,
        "visibility": _as_str(_row_get(row, "visibility", 9), max_len=20) or "hidden",
        "updated_at": _row_get(row, "updated_at", 10),
        "low_confidence": bool(low_fields) or (confidence is not None and confidence < LOW_CONFIDENCE),
        "low_confidence_fields": low_fields,
        "needs_review": status == "draft" or parse_status in PARSE_QUEUE_OPEN,
        "profile": profile,
    }


def read_profile(*, user_id: str) -> dict:
    from app.cabinet_store import _LOCK, _connect

    with _LOCK:
        conn = _connect()
        try:
            return _profile_payload(conn, user_id=user_id)
        finally:
            conn.close()


def _snapshot(payload: dict) -> tuple[str, str]:
    data = payload.get("profile") if isinstance(payload.get("profile"), dict) else {}
    return json.dumps(data, ensure_ascii=False, separators=(",", ":")), str(payload.get("status") or "")


def _log_edit(
    conn,
    *,
    user_id: str,
    profile_id: int | None,
    action: str,
    before: dict,
    after: dict,
) -> None:
    before_data, before_status = _snapshot(before)
    after_data, after_status = _snapshot(after)
    conn.execute(
        """
        INSERT INTO profile_edit_log (
            user_id, profile_id, action, before_data, after_data,
            before_status, after_status, ts
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            profile_id,
            action,
            before_data,
            after_data,
            before_status,
            after_status,
            _now(),
        ),
    )


def _fail_open_parse_jobs(conn, *, user_id: str, error: str) -> int:
    cur = conn.execute(
        """
        UPDATE parse_cv_queue
        SET status = 'failed', error = ?, finished_at = ?
        WHERE user_id = ? AND status IN ('pending', 'processing')
        """,
        ((error or "cancelled")[:1000], _now(), user_id),
    )
    n = getattr(cur, "rowcount", None)
    if n is None or int(n) < 0:
        return 1
    return int(n)


def cancel_open_parse(*, user_id: str) -> dict:
    """Mark open CV parse jobs failed without wiping the profile."""
    from app.cabinet_store import _LOCK, _connect

    subject = (user_id or "").strip()
    if not subject:
        raise ValueError("user_id")

    with _LOCK:
        conn = _connect()
        try:
            ensure_profile_tables(conn)
            _fail_open_parse_jobs(conn, user_id=subject, error="cancelled by user")
            conn.commit()
            return _profile_payload(conn, user_id=subject)
        finally:
            conn.close()


def clear_profile(*, user_id: str) -> dict:
    """Wipe candidate_profile and cancel open parse jobs so the user can start over."""
    from app.cabinet_store import _LOCK, _connect

    subject = (user_id or "").strip()
    if not subject:
        raise ValueError("user_id")

    with _LOCK:
        conn = _connect()
        try:
            ensure_profile_tables(conn)
            before = _profile_payload(conn, user_id=subject)
            row = conn.execute(
                "SELECT id FROM candidate_profile WHERE user_id = ?",
                (subject,),
            ).fetchone()
            profile_id = int(_row_get(row, "id", 0)) if row is not None else None
            if row is not None:
                conn.execute("DELETE FROM candidate_profile WHERE user_id = ?", (subject,))
            _fail_open_parse_jobs(conn, user_id=subject, error="cleared by user")
            after = _profile_payload(conn, user_id=subject)
            if before.get("exists") or before.get("parse_status") in PARSE_QUEUE_OPEN:
                _log_edit(
                    conn,
                    user_id=subject,
                    profile_id=profile_id,
                    action="clear",
                    before=before,
                    after=after,
                )
            conn.commit()
            return after
        finally:
            conn.close()


def save_profile(
    *,
    user_id: str,
    data: dict | None = None,
    headline: str | None = None,
    seniority: str | None = None,
    total_years: Any = None,
    confirm: bool = False,
) -> dict:
    from app.cabinet_store import _LOCK, _connect

    subject = (user_id or "").strip()
    if not subject:
        raise ValueError("user_id")

    with _LOCK:
        conn = _connect()
        try:
            ensure_profile_tables(conn)
            before = _profile_payload(conn, user_id=subject)
            base = before.get("profile") if before.get("exists") else _empty_profile()
            merged = normalize_profile_data(data or {}, base=base if isinstance(base, dict) else _empty_profile())
            if headline is not None:
                merged["headline"] = _as_str(headline, max_len=HEADLINE_MAX)
            if seniority is not None:
                value = _as_str(seniority, max_len=40).lower()
                if value and value not in SENIORITY_VALUES:
                    raise ValueError("seniority")
                merged["seniority"] = value
            if total_years is not None or (data is not None and "total_years" in data):
                # Explicit null clears; omitted leaves merged value.
                if total_years is not None or "total_years" in (data or {}):
                    source = total_years if total_years is not None else data.get("total_years")
                    merged["total_years"] = _as_years(source)

            now = _now()
            encoded = json.dumps(merged, ensure_ascii=False, separators=(",", ":"))
            if confirm:
                status = "confirmed"
            elif before.get("exists"):
                status = before.get("status") or "draft"
                if status not in PROFILE_STATUSES:
                    status = "draft"
            else:
                status = "draft"

            confidence = _as_float((merged.get("parse_meta") or {}).get("confidence"))
            if confidence is None:
                confidence = before.get("confidence")
            parse_method = _as_str((merged.get("parse_meta") or {}).get("method") or before.get("parse_method"), max_len=40)
            visibility = before.get("visibility") if before.get("exists") else "hidden"
            cv_file_key = before.get("cv_file_key") if before.get("exists") else ""

            existing = conn.execute(
                "SELECT id FROM candidate_profile WHERE user_id = ?",
                (subject,),
            ).fetchone()
            if existing is None:
                cur = conn.execute(
                    """
                    INSERT INTO candidate_profile (
                        user_id, cv_file_key, data, headline, seniority, total_years,
                        status, parse_method, confidence, visibility, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        subject,
                        cv_file_key or "",
                        encoded,
                        merged["headline"],
                        merged["seniority"],
                        merged["total_years"],
                        status,
                        parse_method or "",
                        confidence,
                        visibility or "hidden",
                        now,
                    ),
                )
                profile_id = int(cur.lastrowid)
            else:
                profile_id = int(_row_get(existing, "id", 0))
                conn.execute(
                    """
                    UPDATE candidate_profile
                    SET data = ?, headline = ?, seniority = ?, total_years = ?,
                        status = ?, parse_method = ?, confidence = ?, updated_at = ?
                    WHERE user_id = ?
                    """,
                    (
                        encoded,
                        merged["headline"],
                        merged["seniority"],
                        merged["total_years"],
                        status,
                        parse_method or "",
                        confidence,
                        now,
                        subject,
                    ),
                )

            action = "confirm" if confirm else "save"
            after = _profile_payload(conn, user_id=subject)
            _log_edit(
                conn,
                user_id=subject,
                profile_id=profile_id,
                action=action,
                before=before,
                after=after,
            )
            conn.commit()
            result = after
        finally:
            conn.close()
    _maybe_embed_profile(subject)
    return result


def _maybe_embed_profile(user_id: str) -> None:
    """Best-effort profile embedding after save (AI #2). Soft-fails."""
    try:
        from app.embeddings import embed_profile_for_user

        embed_profile_for_user(user_id=user_id)
    except Exception:
        pass


def upload_profile_cv(*, user_id: str, filename: str, data: bytes) -> dict:
    """Store a CV for profile parsing (no job application) and enqueue parse."""
    from app.applications import store_uploaded_cv
    from app.cabinet_store import _LOCK, _connect
    from app.cv_parse_jobs import schedule_parse_cv_drain
    from app.cv_queue import enqueue_parse

    subject = (user_id or "").strip()
    if not subject:
        raise ValueError("user_id")

    original, stored = store_uploaded_cv(filename, data)
    with _LOCK:
        conn = _connect()
        try:
            ensure_profile_tables(conn)
            enqueue_parse(
                conn,
                user_id=subject,
                cv_file_key=stored,
                cv_name=original,
                application_id=None,
            )
            existing = conn.execute(
                "SELECT id FROM candidate_profile WHERE user_id = ?",
                (subject,),
            ).fetchone()
            if existing is not None:
                conn.execute(
                    """
                    UPDATE candidate_profile
                    SET cv_file_key = ?, status = 'draft', updated_at = ?
                    WHERE user_id = ?
                    """,
                    (stored, _now(), subject),
                )
            conn.commit()
            payload = _profile_payload(conn, user_id=subject)
            payload["cv_name"] = original
            payload["queued"] = True
        finally:
            conn.close()
    schedule_parse_cv_drain()
    return payload
