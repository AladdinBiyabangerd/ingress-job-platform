"""Job ↔ candidate matching (plan §6.2 / §6.3).

Hunt struct score + confidence (unknown dims do not invent fit). Down-voted
jobs are demoted (×0.4). Soft-skip skill overlap < 0.5; single matched skill
is half-weighted. For-you / matches list drops score < 0.33 or confidence
< 0.35 — the gate and the displayed ``score`` are always the rule-based score.

AI never rewrites ``score``. For the top RERANK_POOL gated jobs it only adds
signals (``components.semantic`` cosine, ``components.llm_relevance`` 1–5) and
the head is re-ordered with Reciprocal Rank Fusion (Cormack, Clarke & Büttcher,
SIGIR 2009; k=60) over the rule / semantic / LLM rankings. ``rank_score`` and
``components.rrf`` hold the fused value. SQLite / missing vectors → rule order
only (ai_rerank false); LLM may still run.
"""

from __future__ import annotations

import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

from app.cv_profile import _profile_payload, ensure_profile_tables
from app.hunt_scoring import (
    MIN_CONFIDENCE,
    MIN_SCORE,
    SCORING_VERSION,
    compute_score,
    data_completeness_fit,
    experience_fit,
    freshness_fit,
    passes_list_gates,
    preference_fit,
    role_seniority_fit,
    salary_fit,
    tech_skill_fit,
    work_authorization_fit,
)
from app.role_suggestions import (
    _build_skill_lookup,
    _candidate_skills,
    _matching_granted,
    _pick_locale,
    resolve_taxonomy_role,
)


def _ensure_worker_path() -> None:
    try:
        import worker.listing_language  # noqa: F401
        return
    except ImportError:
        pass
    repo_worker = Path(__file__).resolve().parents[2] / "worker"
    if repo_worker.is_dir() and str(repo_worker) not in sys.path:
        sys.path.insert(0, str(repo_worker))


_ensure_worker_path()
from worker.listing_language import resolve_listing_language  # noqa: E402

# Soft boost when a job hits role signature skills (role= filter).
ROLE_HIT_BOOST = 0.025
ROLE_HIT_BOOST_CAP = 0.2
ROLE_SIGNATURE_TOP = 40

DEFAULT_LIMIT = 20
# For-you may return every gated match; home paginates client-side.
MAX_LIMIT = 500
RERANK_POOL = 50

# Legacy component weights (kept for tests / callers of location_score helpers).
W_SKILLS = 0.45
W_SENIORITY = 0.20
W_LOCATION = 0.20
W_LANGUAGE = 0.10
W_FRESHNESS = 0.05

FEEDBACK_DOWN_FACTOR = 0.4
# Reciprocal Rank Fusion constant (Cormack et al., SIGIR 2009).
RRF_K = 60
# LLM relevance is requested for the top-N of the (semantic-fused) head.
LLM_RERANK_TOP = 10

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


_MATCH_ENSURED: set[str] = set()
_MATCH_LOCK = Lock()
_MATCH_JOBS_MEMO: tuple | None = None


def ensure_match_tables(conn) -> None:
    from app.jobs_db import schema_cache_key

    key = schema_cache_key()
    if key in _MATCH_ENSURED:
        return
    with _MATCH_LOCK:
        if key in _MATCH_ENSURED:
            return
        conn.executescript(FEEDBACK_SCHEMA)
        _MATCH_ENSURED.add(key)


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


def _match_catalog_fp(conn) -> tuple:
    from app.sqlite_jobs import published_catalog_fingerprint

    skills = (0, 0)
    try:
        row = conn.execute(
            "SELECT COUNT(*) AS n, COALESCE(MAX(job_id), 0) AS max_job FROM job_skill"
        ).fetchone()
        skills = (int(_row_get(row, "n", 0) or 0), int(_row_get(row, "max_job", 1) or 0))
    except Exception:
        pass
    return (published_catalog_fingerprint(conn), skills)


def _scan_published_jobs(conn) -> list[dict[str, Any]]:
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
                COALESCE(created_at, '') AS created_at,
                CASE
                  WHEN trim(COALESCE(language, '')) = ''
                  THEN substr(COALESCE(NULLIF(cleaned_text, ''), text), 1, 1200)
                  ELSE ''
                END AS language_sample
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
        title = str(_row_get(row, "title", 1) or "")
        stored = str(_row_get(row, "language", 6) or "")
        sample = str(_row_get(row, "language_sample", 10) or "")
        jobs.append(
            {
                "id": int(_row_get(row, "id", 0)),
                "title": title,
                "company": str(_row_get(row, "company", 2) or ""),
                "city": str(_row_get(row, "city", 3) or ""),
                "remote": bool(int(_row_get(row, "remote", 4) or 0)),
                "relocation": bool(int(_row_get(row, "relocation", 5) or 0)),
                "language": resolve_listing_language(stored, title, sample),
                "category": str(_row_get(row, "category", 7) or ""),
                "salary": str(_row_get(row, "salary", 8) or ""),
                "created_at": str(_row_get(row, "created_at", 9) or ""),
            }
        )
    return jobs


def _scan_job_skills(conn) -> dict[int, list[tuple[int, str]]]:
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


def _load_match_catalog(conn) -> tuple[list[dict[str, Any]], dict[int, list[tuple[int, str]]]]:
    """Published jobs + skills until catalog / job_skill fingerprint changes."""
    global _MATCH_JOBS_MEMO
    from app.jobs_db import schema_cache_key

    key = schema_cache_key()
    fp = _match_catalog_fp(conn)
    with _MATCH_LOCK:
        memo = _MATCH_JOBS_MEMO
        if memo is not None and memo[0] == key and memo[1] == fp:
            return memo[2], memo[3]
    jobs = _scan_published_jobs(conn)
    skills_by_job = _scan_job_skills(conn)
    with _MATCH_LOCK:
        _MATCH_JOBS_MEMO = (key, fp, jobs, skills_by_job)
    return jobs, skills_by_job


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
    salary_expectation: dict | None = None,
    total_years: float | None = None,
    work_history: list | None = None,
) -> dict[str, Any] | None:
    skill_s, have, missing = skill_overlap_score(candidate, job_skills)
    # Soft skip: need ≥ half of job skills; thin/partial overlap is noise.
    if job_skills and skill_s < 0.5:
        return None
    n_matched = len(have)
    # 1 matched skill → half credit; 2+ → full (cuts single-chip floor padding).
    skill_effective = round(skill_s * min(1.0, n_matched / 2.0), 4)

    job_level = detect_job_seniority(job["title"])
    dims = {
        "tech_skill_fit": tech_skill_fit(
            skill_effective, job_has_skills=bool(job_skills)
        ),
        "role_seniority_fit": role_seniority_fit(candidate_seniority, job_level),
        "preference_fit": preference_fit(
            prefs, remote=job["remote"], relocation=job["relocation"]
        ),
        "salary_fit": salary_fit(salary_expectation, job.get("salary")),
        "work_authorization_fit": work_authorization_fit(
            prefs, relocation=job["relocation"]
        ),
        "freshness": freshness_fit(job.get("created_at")),
        "data_completeness": data_completeness_fit(job, job_skills),
        "experience_fit": experience_fit(
            total_years, job, work_history=work_history
        ),
    }
    hunt = compute_score(dims)
    total = float(hunt["score"])
    if total <= 0:
        return None

    # Legacy component keys for match-why / digests; honest unknowns stay out.
    components = {
        "skills": dims["tech_skill_fit"] if dims["tech_skill_fit"] is not None else 0.0,
        "seniority": dims["role_seniority_fit"],
        "location": dims["preference_fit"],
        "language": language_score(candidate_langs, job["language"]),
        "freshness": dims["freshness"],
        "hunt_score": total,
        "confidence": hunt["confidence"],
    }

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
        "confidence": hunt["confidence"],
        "score_pct": hunt["score_pct"],
        "confidence_pct": hunt["confidence_pct"],
        "dimensions": hunt["dimensions"],
        "scoring_version": SCORING_VERSION,
        "hunt_score": total,
        "components": components,
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


def _role_signature_skill_ids(conn, role: str | None) -> set[int]:
    """Signature skill IDs for an optional role= filter on matches."""
    tax = resolve_taxonomy_role(conn, role)
    if tax is None:
        return set()
    role_id = int(tax.get("id") or 0)
    if role_id <= 0:
        return set()
    try:
        rows = conn.execute(
            """
            SELECT skill_id
            FROM role_skill_weight
            WHERE role_id = ?
            ORDER BY weight DESC
            LIMIT ?
            """,
            (role_id, ROLE_SIGNATURE_TOP),
        ).fetchall()
    except Exception:
        return set()
    out: set[int] = set()
    for row in rows:
        sid = int(_row_get(row, "skill_id", 0) or 0)
        if sid > 0:
            out.add(sid)
    return out


def _apply_role_scope(
    item: dict[str, Any],
    *,
    job_skills: list[tuple[int, str]],
    role_skill_ids: set[int],
) -> dict[str, Any] | None:
    """Drop jobs with zero role-signature overlap; soft-boost hits."""
    if not role_skill_ids:
        return item
    job_ids = {int(sid) for sid, _name in job_skills}
    hits = len(job_ids & role_skill_ids)
    if hits <= 0:
        return None
    boost = min(ROLE_HIT_BOOST_CAP, ROLE_HIT_BOOST * hits)
    try:
        score = float(item.get("score") or 0.0)
    except (TypeError, ValueError):
        score = 0.0
    new_score = round(min(1.0, score + boost), 4)
    item["score"] = new_score
    item["score_pct"] = int(round(new_score * 100))
    comps = item.get("components") if isinstance(item.get("components"), dict) else {}
    comps = dict(comps)
    comps["role_hits"] = hits
    comps["role_boost"] = boost
    item["components"] = comps
    item["role_skill_hits"] = hits
    return item


def matches_payload(
    conn,
    *,
    user_id: str,
    limit: int | None = None,
    lang: str | None = None,
    role: str | None = None,
    allow_ai_provider: bool = False,
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
    role_name = (role or "").strip() or None

    base = {
        "matches": [],
        "limit": chosen_limit,
        "profile_status": status,
        "matching_consent": matching,
        "skill_count": skill_count,
        "ai_rerank": False,
        "ai_llm_rerank": False,
        "ai_pending": False,
        "role": role_name or "",
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
    salary_expectation = (
        profile.get("salary_expectation")
        if isinstance(profile.get("salary_expectation"), dict)
        else None
    )
    work_history = (
        profile.get("work_history") if isinstance(profile.get("work_history"), list) else None
    )
    try:
        total_years = float(profile["total_years"]) if profile.get("total_years") is not None else None
    except (TypeError, ValueError):
        total_years = None
    candidate_seniority = str(profile.get("seniority") or "").strip().lower() or None
    candidate_langs = _candidate_languages(profile)
    feedback = _load_feedback(conn, user_id)
    jobs, skills_by_job = _load_match_catalog(conn)
    role_skill_ids = _role_signature_skill_ids(conn, role_name) if role_name else set()

    scored: list[dict[str, Any]] = []
    for job in jobs:
        job_skills = skills_by_job.get(job["id"], [])
        item = score_job(
            job=job,
            job_skills=job_skills,
            candidate=candidate,
            candidate_seniority=candidate_seniority,
            candidate_langs=candidate_langs,
            prefs=prefs,
            lang=locale,
            salary_expectation=salary_expectation,
            total_years=total_years,
            work_history=work_history,
        )
        if item is None:
            continue
        item = _apply_role_scope(item, job_skills=job_skills, role_skill_ids=role_skill_ids)
        if item is None:
            continue
        fb = feedback.get(job["id"])
        item["feedback"] = fb
        scored.append(item)

    # Rule score (hunt + role boost, × feedback demotion) drives the gate and display.
    _apply_feedback_demotion(scored)
    gated = [
        item
        for item in scored
        if passes_list_gates(
            float(item.get("score") or 0.0),
            float(item.get("confidence") or 0.0),
        )
    ]
    gated.sort(key=lambda row: (-row["score"], -row["job_id"]))
    # AI only re-orders the head; the tail keeps rule order and honest scores.
    rerank_head = gated[:RERANK_POOL]
    tail = gated[RERANK_POOL:]
    rule_order = [int(item["job_id"]) for item in rerank_head]
    used_rerank = _apply_semantic_rerank(
        conn,
        user_id=user_id,
        pool=rerank_head,
    )
    if used_rerank:
        base["ai_rerank"] = True
        rerank_head = rrf_fuse(rerank_head, rule_order=rule_order)

    profile_version = str(profile_payload.get("updated_at") or "")[:80] or "v0"
    used_llm = False
    llm_deferred = False
    llm_order = [int(item["job_id"]) for item in rerank_head[:LLM_RERANK_TOP]]
    try:
        from app.match_llm_rerank import apply_llm_rerank

        used_llm, llm_deferred = apply_llm_rerank(
            conn,
            matches=rerank_head,
            top_n=LLM_RERANK_TOP,
            profile=profile,
            profile_version=profile_version,
            allow_provider=allow_ai_provider,
        )
    except Exception:
        used_llm = False
        llm_deferred = False
    if used_llm:
        base["ai_llm_rerank"] = True
        rerank_head = rrf_fuse(
            rerank_head,
            rule_order=rule_order,
            llm_order=llm_order,
        )
    matches = (rerank_head + tail)[:chosen_limit]
    base["scoring_version"] = SCORING_VERSION
    base["min_score"] = MIN_SCORE
    base["min_confidence"] = MIN_CONFIDENCE
    why_deferred = False
    if used_rerank or used_llm or llm_deferred:
        try:
            from app.match_why import append_why_sentences

            why_deferred = append_why_sentences(
                conn,
                matches=matches,
                lang=locale,
                profile_version=profile_version,
                candidate=profile,
                allow_provider=allow_ai_provider,
            )
        except Exception:
            why_deferred = False
    if (llm_deferred or why_deferred) and not allow_ai_provider:
        try:
            from app.ai_warm import matches_warm_fail_code, schedule_matches_ai_warm

            sticky = matches_warm_fail_code(
                user_id=user_id,
                lang=locale,
                role=role_name,
                limit=chosen_limit,
            )
            if sticky:
                base["ai_pending"] = False
            else:
                base["ai_pending"] = True
                schedule_matches_ai_warm(
                    user_id=user_id,
                    lang=locale,
                    role=role_name,
                    limit=chosen_limit,
                )
        except Exception:
            base["ai_pending"] = True
    base["matches"] = matches
    return base


def _apply_feedback_demotion(pool: list[dict]) -> None:
    """Down-voted jobs stay listed but score *= FEEDBACK_DOWN_FACTOR."""
    for item in pool:
        if not isinstance(item, dict):
            continue
        fb = item.get("feedback")
        if not isinstance(fb, dict):
            continue
        if str(fb.get("vote") or "").strip().lower() != "down":
            continue
        try:
            score = float(item.get("score") or 0.0)
        except (TypeError, ValueError):
            continue
        new_score = round(score * FEEDBACK_DOWN_FACTOR, 4)
        item["score"] = new_score
        item["score_pct"] = int(round(new_score * 100))
        comps = item.get("components") if isinstance(item.get("components"), dict) else {}
        comps = dict(comps)
        comps["feedback_demotion"] = FEEDBACK_DOWN_FACTOR
        item["components"] = comps


def _signal_ranks(
    items: list[dict],
    key: str,
    tie_order: dict[int, int],
) -> dict[int, float]:
    """1-based ranks by components[key] desc (ties → tie_order); absent keys skipped."""
    present: list[tuple[float, int]] = []
    for item in items:
        comps = item.get("components") if isinstance(item.get("components"), dict) else {}
        val = comps.get(key)
        if isinstance(val, (int, float)) and not isinstance(val, bool):
            present.append((float(val), int(item["job_id"])))
    present.sort(key=lambda row: (-row[0], tie_order.get(row[1], 10**9)))
    ranks = {jid: float(i + 1) for i, (_v, jid) in enumerate(present)}
    return ranks


def rrf_fuse(
    pool: list[dict],
    *,
    rule_order: list[int],
    llm_order: list[int] | None = None,
    k: int = RRF_K,
) -> list[dict]:
    """Reciprocal Rank Fusion of rule / semantic / LLM rankings (score untouched).

    - rule: position in the gated rule-score order (always present);
    - semantic: by cosine; jobs without a vector get the mean rank of those with one;
    - LLM: by relevance among the jobs the model scored (ties → ``llm_order``, the
      order the model saw); jobs it scored no relevance for get the mean rank, jobs
      outside the LLM top-N contribute nothing (standard RRF for absent items).
    Returns a new list sorted by fused value desc, ties by rule order.
    """
    rule_rank = {jid: i + 1 for i, jid in enumerate(rule_order)}
    sem = _signal_ranks(pool, "semantic", rule_rank)
    sem_neutral = (len(sem) + 1) / 2.0 if sem else None
    llm: dict[int, float] = {}
    llm_neutral = None
    llm_seen = set(int(j) for j in (llm_order or []))
    if llm_seen:
        llm_tie = {int(jid): i for i, jid in enumerate(llm_order or [])}
        llm = _signal_ranks(
            [
                item
                for item in pool
                if int(item["job_id"]) in llm_seen and bool(item.get("ai_llm_rerank"))
            ],
            "llm_relevance",
            llm_tie,
        )
        llm_neutral = (len(llm) + 1) / 2.0 if llm else None
    fused: list[tuple[float, int, dict]] = []
    for item in pool:
        jid = int(item["job_id"])
        r_rule = rule_rank.get(jid, len(rule_rank) + 1)
        total = 1.0 / (k + r_rule)
        if sem_neutral is not None:
            total += 1.0 / (k + sem.get(jid, sem_neutral))
        if llm_neutral is not None and jid in llm_seen:
            total += 1.0 / (k + llm.get(jid, llm_neutral))
        total = round(total, 6)
        comps = item.get("components") if isinstance(item.get("components"), dict) else {}
        comps = dict(comps)
        comps["rrf"] = total
        item["components"] = comps
        item["rank_score"] = total
        fused.append((total, r_rule, item))
    fused.sort(key=lambda row: (-row[0], row[1]))
    return [row[2] for row in fused]


def _apply_semantic_rerank(
    conn,
    *,
    user_id: str,
    pool: list[dict],
) -> bool:
    """Attach cosine similarity (components.semantic) to pool items with vectors.

    Never changes ``score`` (rule score). Returns True when at least one item got
    a semantic signal; the caller fuses rankings with :func:`rrf_fuse`.
    Missing pgvector / embeddings table never fails the matches request.
    """
    if not pool or not rerank_enabled(conn):
        return False
    try:
        from app.embeddings import (
            ENTITY_JOB,
            ENTITY_PROFILE,
            cosine_similarity,
            embedding_model,
            ensure_embedding_tables,
            get_embedding,
            load_embeddings,
            pgvector_available,
        )
        from app.jobs_db import postgres_enabled
    except Exception:
        return False
    try:
        if not postgres_enabled() or not pgvector_available(conn):
            return False
        # Ensure table exists even if a prior ready-cache was stale.
        if not ensure_embedding_tables(conn):
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
            comps = item.get("components") if isinstance(item.get("components"), dict) else {}
            comps = dict(comps)
            comps["semantic"] = round(semantic, 4)
            item["components"] = comps
            item["ai_rerank"] = True
            applied = True
        return applied
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return False


def list_matches(
    *,
    user_id: str,
    limit: int | None = None,
    lang: str | None = None,
    role: str | None = None,
) -> dict:
    from app.cabinet_store import _LOCK, _connect

    subject = (user_id or "").strip()
    with _LOCK:
        conn = _connect()
        try:
            payload = matches_payload(
                conn, user_id=subject, limit=limit, lang=lang, role=role
            )
            # LLM why / rerank may have written ai_cache; keep across close.
            conn.commit()
            return payload
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


