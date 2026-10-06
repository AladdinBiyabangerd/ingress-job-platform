"""Job ↔ candidate matching (plan §6.2 / §6.3).

Structured score is always computed. On Postgres + pgvector + embeddings,
AI #2 re-ranks the top pool: final = 0.7·struct + 0.3·cosine.
SQLite / missing vectors → structured only (ai_rerank false).
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from app.cv_profile import _profile_payload, ensure_profile_tables
from app.role_suggestions import (
    _build_skill_lookup,
    _candidate_skills,
    _matching_granted,
    _pick_locale,
)

DEFAULT_LIMIT = 20
MAX_LIMIT = 50
RERANK_POOL = 50

W_SKILLS = 0.45
W_SENIORITY = 0.20
W_LOCATION = 0.20
W_LANGUAGE = 0.10
W_FRESHNESS = 0.05

W_STRUCT = 0.7
W_SEMANTIC = 0.3

FEEDBACK_VOTES = ("up", "down")
FEEDBACK_REASONS = ("", "location", "seniority", "technology", "salary")

SENIORITY_RANK = {
    "intern": 0,
    "junior": 1,
    "middle": 2,
    "mid": 2,
    "senior": 3,
    "lead": 4,
    "principal": 5,
    "staff": 5,
}

_TITLE_SENIORITY = (
    (re.compile(r"(?i)\b(principal|staff)\b"), "principal"),
    (re.compile(r"(?i)\b(lead|head|director)\b"), "lead"),
    (re.compile(r"(?i)\b(senior|sr\.?)\b"), "senior"),
    (re.compile(r"(?i)\b(middle|mid[- ]?level|mid)\b"), "middle"),
    (re.compile(r"(?i)\b(junior|jr\.?|entry[- ]?level)\b"), "junior"),
    (re.compile(r"(?i)\b(intern|trainee|stajyer)\b"), "intern"),
)

EXPLANATION = {
    "az": {
        "skills": "{have}/{total} bacarıq uyğundur: {names}",
        "none": "Ortaq bacarıq yoxdur",
        "remote": "Uzaqdan",
        "relocation": "Relokasiya",
        "visa": "Viza dəstəyi",
        "sep": " · ",
        "yes": "bəli",
    },
    "en": {
        "skills": "{have}/{total} skills match: {names}",
        "none": "No overlapping skills",
        "remote": "Remote",
        "relocation": "Relocation",
        "visa": "Visa support",
        "sep": " · ",
        "yes": "yes",
    },
    "ru": {
        "skills": "{have}/{total} навыков совпадают: {names}",
        "none": "Нет общих навыков",
        "remote": "Удалённо",
        "relocation": "Релокация",
        "visa": "Визовая поддержка",
        "sep": " · ",
        "yes": "да",
    },
}

FEEDBACK_SCHEMA = """
CREATE TABLE IF NOT EXISTS match_feedback (
    user_id TEXT NOT NULL,
    job_id INTEGER NOT NULL,
    vote TEXT NOT NULL,
    reason TEXT NOT NULL DEFAULT '',
    ts TEXT NOT NULL,
    PRIMARY KEY (user_id, job_id)
);

CREATE INDEX IF NOT EXISTS match_feedback_job ON match_feedback(job_id);
CREATE INDEX IF NOT EXISTS match_feedback_user ON match_feedback(user_id);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ensure_match_tables(conn) -> None:
    conn.executescript(FEEDBACK_SCHEMA)


def rerank_enabled(conn=None) -> bool:
    """AI #2 flag. Default on when gateway can run; force off with AI_RERANK_ENABLED=0."""
    from app.ai_flags import feature_on

    return feature_on("rerank", conn)


def clamp_limit(value: int | None) -> int:
    if value is None:
        return DEFAULT_LIMIT
    try:
        n = int(value)
    except (TypeError, ValueError):
        return DEFAULT_LIMIT
    return max(1, min(MAX_LIMIT, n))


def _row_get(row, key: str, index: int):
    if row is None:
        return None
    try:
        return row[key]
    except (KeyError, IndexError, TypeError):
        return row[index]


def detect_job_seniority(title: str) -> str | None:
    text = (title or "").strip()
    if not text:
        return None
    for pattern, level in _TITLE_SENIORITY:
        if pattern.search(text):
            return level
    return None


def seniority_score(candidate: str | None, job_level: str | None) -> float:
    if not candidate or not job_level:
        return 0.5
    c = SENIORITY_RANK.get(str(candidate).strip().lower())
    j = SENIORITY_RANK.get(str(job_level).strip().lower())
    if c is None or j is None:
        return 0.5
    diff = abs(c - j)
    if diff == 0:
        return 1.0
    if diff == 1:
        return 0.6
    if diff == 2:
        return 0.3
    return 0.1


def skill_overlap_score(
    candidate: dict[int, dict],
    job_skills: list[tuple[int, str]],
) -> tuple[float, list[str], list[str]]:
    """Return (score, have_names, missing_names)."""
    if not job_skills:
        return 0.0, [], []
    have: list[str] = []
    missing: list[str] = []
    matched = 0.0
    for skill_id, name in job_skills:
        hit = candidate.get(skill_id)
        if hit is None:
            missing.append(name)
            continue
        matched += float(hit["factor"])
        have.append(name)
    total = float(len(job_skills))
    return round(matched / total, 4), have, missing


def location_score(prefs: dict, *, remote: bool, relocation: bool) -> float:
    if not isinstance(prefs, dict):
        return 0.5
    parts: list[float] = []
    want_remote = prefs.get("remote")
    if want_remote is True:
        parts.append(1.0 if remote else 0.25)
    elif want_remote is False:
        parts.append(1.0 if not remote else 0.4)

    want_reloc = prefs.get("relocation")
    if want_reloc is True:
        parts.append(1.0 if relocation else 0.3)
    elif want_reloc is False:
        parts.append(1.0 if not relocation else 0.5)

    needs_visa = prefs.get("needs_visa_sponsorship")
    if needs_visa is True:
        # Job.relocation flag doubles as visa/relocation support in crawl data.
        parts.append(1.0 if relocation else 0.2)

    if not parts:
        return 0.5
    return round(sum(parts) / len(parts), 4)


def language_score(candidate_langs: list[str], job_lang: str) -> float:
    job = (job_lang or "").strip().lower()[:2]
    if not job or job not in {"az", "en", "ru"}:
        return 0.5
    if not candidate_langs:
        return 0.5
    normalized = {str(x).strip().lower()[:2] for x in candidate_langs if str(x).strip()}
    # Also accept full names / codes from profile language objects handled upstream.
    return 1.0 if job in normalized else 0.2


def freshness_score(created_at: str) -> float:
    raw = (created_at or "").strip()
    if not raw:
        return 0.4
    try:
        # Accept date-only or ISO with timezone / naive.
        if len(raw) == 10 and raw[4] == "-" and raw[7] == "-":
            created = datetime.fromisoformat(raw).replace(tzinfo=timezone.utc)
        else:
            created = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
    except ValueError:
        return 0.4
    age_days = (datetime.now(timezone.utc) - created.astimezone(timezone.utc)).total_seconds() / 86400.0
    if age_days <= 7:
        return 1.0
    if age_days <= 30:
        return 0.7
    if age_days <= 90:
        return 0.4
    return 0.2


def _candidate_languages(profile: dict) -> list[str]:
    raw = profile.get("languages") if isinstance(profile, dict) else None
    out: list[str] = []
    if not isinstance(raw, list):
        return out
    for item in raw:
        if isinstance(item, str):
            code = item.strip().lower()
        elif isinstance(item, dict):
            code = str(item.get("code") or item.get("name") or "").strip().lower()
        else:
            continue
        if not code:
            continue
        if code.startswith("az") or "azerbaijan" in code:
            out.append("az")
        elif code.startswith("en") or "english" in code:
            out.append("en")
        elif code.startswith("ru") or "russian" in code or "рус" in code:
            out.append("ru")
        elif code[:2] in {"az", "en", "ru"}:
            out.append(code[:2])
    return out


def _format_explanation(
    lang: str,
    *,
    have: list[str],
    missing: list[str],
    job_skill_count: int,
    remote: bool,
    relocation: bool,
) -> str:
    tpl = EXPLANATION[_pick_locale(lang)]
    parts: list[str] = []
    if job_skill_count <= 0:
        parts.append(tpl["none"])
    elif have:
        parts.append(
            tpl["skills"].format(
                have=len(have),
                total=job_skill_count,
                names=", ".join(have),
            )
        )
    else:
        parts.append(tpl["none"])
    if remote:
        parts.append(tpl["remote"])
    if relocation:
        parts.append(f"{tpl['relocation']}: {tpl['yes']}")
    # Keep missing available for API consumers; mention briefly when present.
    if missing and have:
        # Prefer skill overlap sentence; missing list is in the payload.
        pass
    return tpl["sep"].join(parts)


def _load_published_jobs(conn) -> list[dict[str, Any]]:
    try:
        rows = conn.execute(
            """
            SELECT
                id, title, company, city,
                COALESCE(remote, 0) AS remote,
                COALESCE(relocation, 0) AS relocation,
                COALESCE(language, '') AS language,
                COALESCE(category, '') AS category,
                COALESCE(salary, '') AS salary,
                COALESCE(created_at, '') AS created_at
            FROM jobs
            WHERE status = 'published'
              AND COALESCE(hidden, 0) = 0
              AND (merged_into IS NULL OR merged_into = 0)
            """
        ).fetchall()
    except Exception:
        return []
    jobs: list[dict[str, Any]] = []
    for row in rows:
        jobs.append(
            {
                "id": int(_row_get(row, "id", 0)),
                "title": str(_row_get(row, "title", 1) or ""),
                "company": str(_row_get(row, "company", 2) or ""),
                "city": str(_row_get(row, "city", 3) or ""),
                "remote": bool(int(_row_get(row, "remote", 4) or 0)),
                "relocation": bool(int(_row_get(row, "relocation", 5) or 0)),
                "language": str(_row_get(row, "language", 6) or ""),
                "category": str(_row_get(row, "category", 7) or ""),
                "salary": str(_row_get(row, "salary", 8) or ""),
                "created_at": str(_row_get(row, "created_at", 9) or ""),
            }
        )
    return jobs


def _load_job_skills(conn) -> dict[int, list[tuple[int, str]]]:
    out: dict[int, list[tuple[int, str]]] = {}
    try:
        rows = conn.execute(
            """
            SELECT js.job_id, js.skill_id, s.canonical_name
            FROM job_skill js
            JOIN skill_dictionary s ON s.id = js.skill_id
            ORDER BY s.canonical_name
            """
        ).fetchall()
    except Exception:
        return out
    for row in rows:
        job_id = int(_row_get(row, "job_id", 0))
        skill_id = int(_row_get(row, "skill_id", 1))
        name = str(_row_get(row, "canonical_name", 2) or "").strip()
        if not name:
            continue
        out.setdefault(job_id, []).append((skill_id, name))
    return out


def _load_feedback(conn, user_id: str) -> dict[int, dict]:
    ensure_match_tables(conn)
    out: dict[int, dict] = {}
    try:
        rows = conn.execute(
            "SELECT job_id, vote, reason FROM match_feedback WHERE user_id = ?",
            (user_id,),
        ).fetchall()
    except Exception:
        return out
    for row in rows:
        job_id = int(_row_get(row, "job_id", 0))
        out[job_id] = {
            "vote": str(_row_get(row, "vote", 1) or ""),
            "reason": str(_row_get(row, "reason", 2) or ""),
        }
    return out


def score_job(
    *,
    job: dict[str, Any],
    job_skills: list[tuple[int, str]],
    candidate: dict[int, dict],
    candidate_seniority: str | None,
    candidate_langs: list[str],
    prefs: dict,
    lang: str,
) -> dict[str, Any] | None:
    skill_s, have, missing = skill_overlap_score(candidate, job_skills)
    # Skip jobs with zero skill overlap when the ad has skills — keeps noise down.
    if job_skills and skill_s <= 0:
        return None

    job_level = detect_job_seniority(job["title"])
    sen_s = seniority_score(candidate_seniority, job_level)
    loc_s = location_score(prefs, remote=job["remote"], relocation=job["relocation"])
    lang_s = language_score(candidate_langs, job["language"])
    fresh_s = freshness_score(job["created_at"])

    total = round(
        W_SKILLS * skill_s
        + W_SENIORITY * sen_s
        + W_LOCATION * loc_s
        + W_LANGUAGE * lang_s
        + W_FRESHNESS * fresh_s,
        4,
    )
    if total <= 0:
        return None

    return {
        "job_id": job["id"],
        "title": job["title"],
        "company": job["company"],
        "city": job["city"],
        "remote": job["remote"],
        "relocation": job["relocation"],
        "category": job["category"],
        "salary": job["salary"],
        "language": job["language"],
        "created_at": job["created_at"],
        "score": total,
        "components": {
            "skills": skill_s,
            "seniority": sen_s,
            "location": loc_s,
            "language": lang_s,
            "freshness": fresh_s,
        },
        "have": have,
        "missing": missing,
        "job_seniority": job_level or "",
        "explanation": _format_explanation(
            lang,
            have=have,
            missing=missing,
            job_skill_count=len(job_skills),
            remote=job["remote"],
            relocation=job["relocation"],
        ),
        "ai_rerank": False,
    }


def matches_payload(
    conn,
    *,
    user_id: str,
    limit: int | None = None,
    lang: str | None = None,
) -> dict:
    ensure_profile_tables(conn)
    ensure_match_tables(conn)
    chosen_limit = clamp_limit(limit)
    locale = _pick_locale(lang)
    profile_payload = _profile_payload(conn, user_id=user_id)
    status = str(profile_payload.get("status") or "empty")
    profile = profile_payload.get("profile") if isinstance(profile_payload.get("profile"), dict) else {}
    raw_skills = profile.get("skills") if isinstance(profile.get("skills"), list) else []
    skill_count = len(raw_skills)
    matching = _matching_granted(conn, user_id)

    base = {
        "matches": [],
        "limit": chosen_limit,
        "profile_status": status,
        "matching_consent": matching,
        "skill_count": skill_count,
        "ai_rerank": False,
    }
    if not matching:
        return base
    if not profile_payload.get("exists") or skill_count == 0:
        return base

    lookup = _build_skill_lookup(conn)
    candidate = _candidate_skills(profile, lookup)
    if not candidate:
        return base

    prefs = profile.get("preferences") if isinstance(profile.get("preferences"), dict) else {}
    candidate_seniority = str(profile.get("seniority") or "").strip().lower() or None
    candidate_langs = _candidate_languages(profile)
    feedback = _load_feedback(conn, user_id)
    jobs = _load_published_jobs(conn)
    skills_by_job = _load_job_skills(conn)

    scored: list[dict[str, Any]] = []
    for job in jobs:
        item = score_job(
            job=job,
            job_skills=skills_by_job.get(job["id"], []),
            candidate=candidate,
            candidate_seniority=candidate_seniority,
            candidate_langs=candidate_langs,
            prefs=prefs,
            lang=locale,
        )
        if item is None:
            continue
        fb = feedback.get(job["id"])
        item["feedback"] = fb
        scored.append(item)

    scored.sort(key=lambda row: (-row["score"], -row["job_id"]))
    pool = scored[: max(chosen_limit, RERANK_POOL)]
    used_rerank = _apply_semantic_rerank(
        conn,
        user_id=user_id,
        pool=pool,
    )
    if used_rerank:
        pool.sort(key=lambda row: (-row["score"], -row["job_id"]))
        base["ai_rerank"] = True
    matches = pool[:chosen_limit]
    if used_rerank:
        try:
            from app.match_why import append_why_sentences

            profile_version = str(profile_payload.get("updated_at") or "")[:80]
            append_why_sentences(
                conn,
                matches=matches,
                lang=locale,
                profile_version=profile_version or "v0",
            )
        except Exception:
            pass
    base["matches"] = matches
    return base


def _apply_semantic_rerank(
    conn,
    *,
    user_id: str,
    pool: list[dict],
) -> bool:
    """Blend cosine similarity into scores for pool items with job embeddings.

    Returns True when at least one item was re-ranked.
    """
    if not pool or not rerank_enabled(conn):
        return False
    try:
        from app.embeddings import (
            ENTITY_JOB,
            ENTITY_PROFILE,
            cosine_similarity,
            embedding_model,
            get_embedding,
            load_embeddings,
            pgvector_available,
        )
        from app.jobs_db import postgres_enabled
    except Exception:
        return False
    if not postgres_enabled() or not pgvector_available(conn):
        return False

    model = embedding_model()
    profile_row = get_embedding(
        conn,
        entity_type=ENTITY_PROFILE,
        entity_id=user_id,
        model=model,
    )
    if profile_row is None:
        return False
    profile_vec = profile_row[0]
    job_ids = [str(item["job_id"]) for item in pool]
    job_vecs = load_embeddings(
        conn,
        entity_type=ENTITY_JOB,
        entity_ids=job_ids,
        model=model,
    )
    if not job_vecs:
        return False

    applied = False
    for item in pool:
        jid = str(item["job_id"])
        job_vec = job_vecs.get(jid)
        if not job_vec:
            item["ai_rerank"] = False
            continue
        semantic = cosine_similarity(profile_vec, job_vec)
        struct = float(item.get("score") or 0.0)
        blended = round(W_STRUCT * struct + W_SEMANTIC * semantic, 4)
        comps = item.get("components") if isinstance(item.get("components"), dict) else {}
        comps = dict(comps)
        comps["semantic"] = round(semantic, 4)
        comps["struct"] = round(struct, 4)
        item["components"] = comps
        item["score"] = blended
        item["ai_rerank"] = True
        applied = True
    return applied


def list_matches(*, user_id: str, limit: int | None = None, lang: str | None = None) -> dict:
    from app.cabinet_store import _LOCK, _connect

    subject = (user_id or "").strip()
    with _LOCK:
        conn = _connect()
        try:
            return matches_payload(conn, user_id=subject, limit=limit, lang=lang)
        finally:
            conn.close()


def save_match_feedback(
    *,
    user_id: str,
    job_id: int,
    vote: str,
    reason: str = "",
) -> dict:
    from app.cabinet_store import _LOCK, _connect

    subject = (user_id or "").strip()
    chosen_vote = (vote or "").strip().lower()
    if chosen_vote not in FEEDBACK_VOTES:
        raise ValueError("invalid_vote")
    chosen_reason = (reason or "").strip().lower()
    if chosen_vote == "up":
        chosen_reason = ""
    elif chosen_reason not in FEEDBACK_REASONS:
        raise ValueError("invalid_reason")

    with _LOCK:
        conn = _connect()
        try:
            ensure_match_tables(conn)
            if not _matching_granted(conn, subject):
                raise PermissionError("matching_consent_required")
            row = conn.execute(
                """
                SELECT id FROM jobs
                WHERE id = ?
                  AND status = 'published'
                  AND COALESCE(hidden, 0) = 0
                  AND (merged_into IS NULL OR merged_into = 0)
                """,
                (int(job_id),),
            ).fetchone()
            if row is None:
                raise LookupError("job_not_found")
            ts = _now()
            conn.execute(
                """
                INSERT INTO match_feedback (user_id, job_id, vote, reason, ts)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id, job_id) DO UPDATE SET
                    vote = excluded.vote,
                    reason = excluded.reason,
                    ts = excluded.ts
                """,
                (subject, int(job_id), chosen_vote, chosen_reason, ts),
            )
            conn.commit()
            return {
                "job_id": int(job_id),
                "vote": chosen_vote,
                "reason": chosen_reason,
                "ts": ts,
            }
        finally:
            conn.close()


