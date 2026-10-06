"""Read published jobs from the shared jobs database.

SQLite file when DATABASE_URL is unset. The same Postgres database as the
worker when DATABASE_URL is set.

Only status published is selected, so pending, rejected, and closed cabinet ads stay off
the public list. Source URLs stay in job_sources.source_url and are never selected.
Any http(s) or www link inside the description is removed before the
response is built, so a listing address cannot leak through the text.

GET /jobs list omits description text and apply form; GET /jobs/{id} returns the full body.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import unicodedata
from pathlib import Path

from app.apply_form import parse_stored
from app.companies import application_count, application_counts, company_slug

def _db_path() -> Path:
    configured = os.environ.get("JOBS_DB_PATH", "").strip()
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[2] / "worker" / "data" / "jobs.sqlite"


DB_PATH = _db_path()

# No leading \b: a link glued to a word ("gärnahttps://…") must go too.
_URL = re.compile(r"(?i)(?:https?://|www\.)\S+")

_LIST_SELECT_CORE = """
    j.id,
    j.title,
    j.company,
    j.city,
    j.created_at,
    COALESCE(j.language, '') AS language,
    COALESCE(j.remote, 0) AS remote,
    COALESCE(j.relocation, 0) AS relocation,
    COALESCE(j.tech_stack, '') AS tech_stack,
    COALESCE(j.category, '') AS category,
    COALESCE(j.salary, '') AS salary,
    COALESCE(j.job_type, '') AS job_type,
    COALESCE(j.owner_subject, '') AS owner_subject,
    CASE WHEN EXISTS (
        SELECT 1
        FROM job_sources js2
        WHERE js2.job_id = j.id AND TRIM(js2.source_url) != ''
    ) THEN 1 ELSE 0 END AS has_original,
    COALESCE(
        (
            SELECT js.source_name
            FROM job_sources js
            WHERE js.job_id = j.id
            ORDER BY js.id
            LIMIT 1
        ),
        ''
    ) AS source_name,
    COALESCE(
        (
            SELECT cs.homepage
            FROM job_sources js3
            JOIN crawl_sources cs ON cs.name = js3.source_name
            WHERE js3.job_id = j.id
            ORDER BY js3.id
            LIMIT 1
        ),
        ''
    ) AS source_homepage
"""

_PUBLISHED_WHERE = """
FROM jobs j
WHERE j.status = 'published'
  AND COALESCE(j.hidden, 0) = 0
  AND (j.merged_into IS NULL OR j.merged_into = 0)
"""

_LIST_FROM_WHERE = f"""
{_PUBLISHED_WHERE}
ORDER BY j.id
"""

# List endpoint: no description / apply form (payload + DB read).
_LIST_SQL = f"""
SELECT
{_LIST_SELECT_CORE}
{_LIST_FROM_WHERE}
"""

# Detail endpoint: full public body.
_DETAIL_SQL = f"""
SELECT
{_LIST_SELECT_CORE},
    COALESCE(NULLIF(j.cleaned_text, ''), j.text) AS text,
    COALESCE(j.apply_form, '') AS apply_form
{_LIST_FROM_WHERE}
"""

_FACET_SQL = f"""
SELECT
    j.title,
    COALESCE(j.language, '') AS language,
    COALESCE(j.category, '') AS category,
    COALESCE(j.tech_stack, '') AS tech_stack
{_PUBLISHED_WHERE}
"""

SORTS = ("newest", "oldest", "title")
WHENS = ("any", "today", "week")
DEFAULT_PER_PAGE = 20
MAX_PER_PAGE = 60
_LANG_FACET_ORDER = ("az", "en", "ru", "tr", "es", "uk", "de", "fr", "pt")

_NOISE = re.compile(
    r"(?im)^(?:application url|apply url)\s*$"
    r"|^please mention the word \*\*.*$"
)
_MOJIBAKE = re.compile(r"[\u00c2\u00c3\u00e2][\u0080-\u00bf]+")


def repair_text(value: str) -> str:
    if not value:
        return ""
    if not any(mark in value for mark in ("\u00c2", "\u00c3", "\u00e2", "\u00a0")):
        return value
    try:
        return value.encode("latin1").decode("utf-8")
    except UnicodeError:
        pass

    def repair_run(match: re.Match[str]) -> str:
        chunk = match.group(0)
        try:
            return chunk.encode("latin1").decode("utf-8")
        except UnicodeError:
            return chunk

    value = _MOJIBAKE.sub(repair_run, value)
    return value.replace("\u00c2", "").replace("\u00a0", " ")


def public_text(value: str) -> str:
    cleaned = repair_text(value or "")
    cleaned = _URL.sub("", cleaned)
    lines = []
    for line in cleaned.splitlines():
        plain = line.strip().replace("**", "")
        if _NOISE.match(plain) or plain.lower().startswith("please mention the word"):
            continue
        lines.append(line.replace("**", ""))
    cleaned = "\n".join(lines)
    cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    return cleaned.strip()


_AZ = re.compile(r"[əğıöüşçƏĞİÖÜŞÇ]")
_UK = re.compile(r"[іїєґІЇЄҐ]")
_CYR = re.compile(r"[а-яёА-ЯЁ]")


def listing_language(title: str, body: str) -> str:
    sample = f"{title}\n{body[:900]}"
    if _AZ.search(sample):
        return "az"
    if _UK.search(sample):
        return "uk"
    if _CYR.search(sample):
        return "ru"
    low = sample.lower()
    if re.search(r"[áéíóúñ¿¡]", low) and re.search(r"\b(el|la|los|para|con|una|experiencia|y)\b", low):
        return "es"
    if re.search(r"[äöüß]", low) and re.search(r"\b(und|der|die|das|mit|für)\b", low):
        return "de"
    if re.search(r"[àâçéèêëîïôùû]", low) and re.search(r"\b(et|les|des|une|pour|avec)\b", low):
        return "fr"
    if re.search(r"[ğış]", low) and re.search(r"\b(ve|bir|için|ile)\b", low):
        return "tr"
    return "en"


def _ensure_columns() -> None:
    from app.cabinet_store import ensure_schema

    ensure_schema()


def _connect():
    _ensure_columns()
    from app.jobs_db import connect, postgres_enabled

    if postgres_enabled():
        return connect()
    if not DB_PATH.is_file():
        raise FileNotFoundError(DB_PATH)
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _plain(value: str) -> str:
    return _URL.sub("", repair_text(value or "")).strip()


def tech_stack(value: object) -> list[str]:
    """Stored JSON list of tech names. Anything unreadable is an empty list."""
    raw = str(value or "").strip()
    if not raw:
        return []
    try:
        items = json.loads(raw)
    except (TypeError, ValueError):
        return []
    if not isinstance(items, list):
        return []
    out: list[str] = []
    for item in items:
        name = str(item or "").strip()
        if name and len(name) <= 40 and name not in out:
            out.append(name)
    return out[:12]


# Same list as worker/worker/techstack.py CATEGORIES. Anything else
# (including the worker's "-" for non-tech rows) is returned as "".
CATEGORIES = (
    "Backend", "Frontend", "Full-stack", "Mobile", "DevOps/Cloud", "Data/ML",
    "QA", "Security", "Design/UX", "Product", "IT Support", "Other tech",
)


def job_category(value: object) -> str:
    name = str(value or "").strip()
    return name if name in CATEGORIES else ""


def _homepage(value: object) -> str:
    url = str(value or "").strip()
    return url if re.match(r"(?i)^https?://[^\s\"<>]+$", url) else ""


def _public(row: sqlite3.Row, applications: dict[int, int] | None = None, *, full: bool = False) -> dict:
    title = _plain(row["title"] or "")
    body = public_text(row["text"] or "") if full else ""
    stored = (row["language"] or "").strip().lower()
    language = stored if stored in {"az", "en", "ru"} else listing_language(title, body)
    job_type = (row["job_type"] or "").strip().lower()
    if job_type not in {"ofis", "hibrid", "uzaqdan"}:
        job_type = ""
    company = _plain(row["company"] or "")
    onsite = bool((row["owner_subject"] or "").strip())
    job = {
        "id": int(row["id"]),
        "title": title,
        "company": company,
        "company_slug": company_slug(company),
        "city": _plain(row["city"] or ""),
        "remote": bool(int(row["remote"] or 0)),
        "relocation": bool(int(row["relocation"] or 0)),
        "tech_stack": tech_stack(row["tech_stack"]),
        "category": job_category(row["category"]),
        "language": language,
        "salary": _plain(row["salary"] or ""),
        "job_type": job_type,
        "source_name": row["source_name"] or "",
        "created_at": row["created_at"] or "",
        "onsite": onsite,
        # On-site applications only; external ads are applied to on the source site.
        "applications": int((applications or {}).get(int(row["id"]), 0)) if onsite else None,
        "has_original": bool(int(row["has_original"] or 0)),
    }
    if full:
        job["text"] = body
        job["form"] = parse_stored(row["apply_form"]) if onsite else None
    return job


def list_jobs() -> list[dict]:
    conn = _connect()
    try:
        rows = conn.execute(_LIST_SQL).fetchall()
        counts = application_counts(conn)
    finally:
        conn.close()
    return [_public(row, counts, full=False) for row in rows]


def _parse_salary_amount(value: object) -> int | None:
    """First number in free-text salary; currency words/symbols ignored."""
    raw = str(value or "").strip()
    if not raw:
        return None
    cleaned = re.sub(r"[₼$€£¥₽]", " ", raw)
    cleaned = re.sub(
        r"(?i)\b(azn|usd|eur|gbp|try|rub|rur|manat|dollar|dollars|euro|euros|"
        r"руб(?:ль|ля|лей)?|доллар(?:а|ов|ы)?|евро|манат)\b",
        " ",
        cleaned,
    )
    match = re.search(r"\d{1,3}(?:[.,\s]\d{3})+|\d+", cleaned)
    if not match:
        return None
    token = match.group(0)
    if re.fullmatch(r"\d{1,3}([.,\s]\d{3})+", token):
        digits = re.sub(r"[.,\s]", "", token)
    else:
        digits = re.search(r"\d+", token).group(0)
    try:
        return int(digits)
    except ValueError:
        return None


def _normalize_salary_text(value: object) -> str:
    text = str(value or "").lower().replace("ё", "е")
    text = unicodedata.normalize("NFD", text)
    text = re.sub(r"[\u0300-\u036f]", "", text)
    text = text.replace("ə", "e").replace("ı", "i")
    return re.sub(r"\s+", " ", text).strip()


def _is_negotiable_salary(value: object) -> bool:
    normalized = _normalize_salary_text(value)
    patterns = (
        r"\bmuqavile\s+ile\b",
        r"\brazilasma\b",
        r"\bnegotiable\b",
        r"\bby[\s-]+agreement\b",
        r"(?:^|[^\w])договорная(?:$|[^\w])",
        r"(?:^|[^\w])по\s+договоренности(?:$|[^\w])",
    )
    return any(re.search(p, normalized, re.IGNORECASE | re.UNICODE) for p in patterns)


def _tokens(values: list[str] | str | None) -> list[str]:
    if values is None:
        return []
    if isinstance(values, str):
        parts = values.split(",")
    else:
        parts = []
        for value in values:
            parts.extend(str(value or "").split(","))
    out: list[str] = []
    for part in parts:
        name = part.strip()
        if name and name not in out:
            out.append(name)
    return out


def _row_language(row) -> str:
    title = _plain(row["title"] or "")
    stored = (row["language"] or "").strip().lower()
    if stored in {"az", "en", "ru"}:
        return stored
    return listing_language(title, "")


def _salary_matches(salary: str, salary_min: int | None, salary_max: int | None) -> bool:
    if salary_min is None and salary_max is None:
        return True
    amount = _parse_salary_amount(salary)
    if amount is None:
        return _is_negotiable_salary(salary)
    if salary_min is not None and amount < salary_min:
        return False
    if salary_max is not None and amount > salary_max:
        return False
    return True


def _build_sql_filters(
    *,
    q: str,
    company: str,
    remote: bool,
    relocation: bool,
    categories: list[str],
) -> tuple[str, list]:
    clauses: list[str] = []
    params: list = []
    needle = q.strip().lower()
    if needle:
        like = f"%{needle}%"
        clauses.append("(LOWER(j.title) LIKE ? OR LOWER(j.company) LIKE ?)")
        params.extend([like, like])
    company_q = company.strip().lower()
    if company_q:
        clauses.append("LOWER(j.company) LIKE ?")
        params.append(f"%{company_q}%")
    if remote:
        clauses.append("(COALESCE(j.remote, 0) = 1 OR LOWER(COALESCE(j.job_type, '')) = 'uzaqdan')")
    if relocation:
        clauses.append("COALESCE(j.relocation, 0) = 1")
    valid_cats = [c for c in categories if c in CATEGORIES]
    if valid_cats:
        placeholders = ",".join("?" * len(valid_cats))
        clauses.append(f"j.category IN ({placeholders})")
        params.extend(valid_cats)
    where = _PUBLISHED_WHERE
    if clauses:
        where = where + " AND " + " AND ".join(clauses)
    return where, params


def _age_days(created_at: object) -> float | None:
    from datetime import datetime, timezone

    raw = str(created_at or "").strip()
    if not raw:
        return None
    try:
        # Accept trailing Z and offset-less values.
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)).total_seconds() / 86400.0


def _when_matches(created_at: object, when: str) -> bool:
    if when == "any":
        return True
    days = _age_days(created_at)
    if days is None:
        return False
    if when == "today":
        return days < 1
    if when == "week":
        return days < 7
    return True


def _order_sql(sort: str) -> str:
    if sort == "oldest":
        return "ORDER BY j.created_at ASC, j.id ASC"
    if sort == "title":
        return "ORDER BY LOWER(j.title) ASC, j.id ASC"
    return "ORDER BY j.created_at DESC, j.id DESC"


def _page_counts(conn, job_ids: list[int]) -> dict[int, int]:
    if not job_ids:
        return {}
    placeholders = ",".join("?" * len(job_ids))
    try:
        rows = conn.execute(
            f"""
            SELECT a.job_id AS job_id, COUNT(*) AS total
            FROM applications a
            WHERE a.job_id IN ({placeholders})
              AND LOWER(COALESCE(a.status, '')) NOT IN ('withdrawn', 'deleted')
            GROUP BY a.job_id
            """,
            job_ids,
        ).fetchall()
    except Exception:
        return {}
    return {int(row["job_id"]): int(row["total"] or 0) for row in rows}


def _build_facets(conn) -> dict:
    from collections import Counter

    lang_counts: Counter[str] = Counter()
    cat_counts: Counter[str] = Counter()
    stack_counts: Counter[str] = Counter()
    for row in conn.execute(_FACET_SQL).fetchall():
        lang_counts[_row_language(row)] += 1
        cat = job_category(row["category"])
        if cat:
            cat_counts[cat] += 1
        for name in tech_stack(row["tech_stack"]):
            stack_counts[name] += 1

    languages = sorted(
        [{"code": code, "total": total} for code, total in lang_counts.items()],
        key=lambda item: (
            _LANG_FACET_ORDER.index(item["code"]) if item["code"] in _LANG_FACET_ORDER else 99,
            item["code"],
        ),
    )
    categories = sorted(
        [{"name": name, "total": total} for name, total in cat_counts.items()],
        key=lambda item: (
            CATEGORIES.index(item["name"]) if item["name"] in CATEGORIES else 99,
            item["name"],
        ),
    )
    stacks = sorted(
        [{"name": name, "total": total} for name, total in stack_counts.items()],
        key=lambda item: (-item["total"], item["name"]),
    )
    return {"languages": languages, "categories": categories, "stacks": stacks}


def query_jobs(
    *,
    page: int = 1,
    per_page: int = DEFAULT_PER_PAGE,
    q: str = "",
    company: str = "",
    remote: bool = False,
    relocation: bool = False,
    when: str = "any",
    sort: str = "newest",
    languages: list[str] | str | None = None,
    categories: list[str] | str | None = None,
    stacks: list[str] | str | None = None,
    salary_min: int | None = None,
    salary_max: int | None = None,
) -> dict:
    """Paginated public job list with optional filters and catalog facets."""
    import math

    page = max(1, int(page or 1))
    per_page = max(1, min(MAX_PER_PAGE, int(per_page or DEFAULT_PER_PAGE)))
    sort = sort if sort in SORTS else "newest"
    when = when if when in WHENS else "any"
    lang_filter = [c.strip().lower() for c in _tokens(languages) if c.strip()]
    cat_filter = _tokens(categories)
    stack_filter = _tokens(stacks)
    needs_python = bool(
        lang_filter
        or stack_filter
        or salary_min is not None
        or salary_max is not None
        or when in {"today", "week"}
    )

    where, params = _build_sql_filters(
        q=q,
        company=company,
        remote=remote,
        relocation=relocation,
        categories=cat_filter,
    )
    order = _order_sql(sort)

    conn = _connect()
    try:
        catalog_row = conn.execute(f"SELECT COUNT(*) AS total {_PUBLISHED_WHERE}").fetchone()
        catalog_total = int(catalog_row["total"] or 0)
        facets = _build_facets(conn)

        if needs_python:
            rows = conn.execute(
                f"SELECT {_LIST_SELECT_CORE} {where} {order}",
                params,
            ).fetchall()
            matched = []
            for row in rows:
                if not _when_matches(row["created_at"], when):
                    continue
                if lang_filter and _row_language(row) not in lang_filter:
                    continue
                if stack_filter:
                    own = tech_stack(row["tech_stack"])
                    if not any(name in own for name in stack_filter):
                        continue
                salary = _plain(row["salary"] or "")
                if not _salary_matches(salary, salary_min, salary_max):
                    continue
                matched.append(row)
            total = len(matched)
            pages = max(1, math.ceil(total / per_page)) if total else 1
            current = min(page, pages)
            start = (current - 1) * per_page
            page_rows = matched[start : start + per_page]
        else:
            count_row = conn.execute(f"SELECT COUNT(*) AS total {where}", params).fetchone()
            total = int(count_row["total"] or 0)
            pages = max(1, math.ceil(total / per_page)) if total else 1
            current = min(page, pages)
            offset = (current - 1) * per_page
            page_rows = conn.execute(
                f"SELECT {_LIST_SELECT_CORE} {where} {order} LIMIT ? OFFSET ?",
                [*params, per_page, offset],
            ).fetchall()

        ids = [int(row["id"]) for row in page_rows]
        counts = _page_counts(conn, ids)
    finally:
        conn.close()

    return {
        "items": [_public(row, counts, full=False) for row in page_rows],
        "total": total,
        "page": current,
        "per_page": per_page,
        "pages": pages,
        "catalog_total": catalog_total,
        "facets": facets,
    }


def get_job(job_id: int) -> dict | None:
    conn = _connect()
    try:
        row = conn.execute(
            f"SELECT * FROM ({_DETAIL_SQL}) AS published WHERE id = ?",
            (job_id,),
        ).fetchone()
        counts = {job_id: application_count(conn, job_id)} if row is not None else {}
    finally:
        conn.close()
    if row is None:
        return None
    job = _public(row, counts, full=True)
    # Only the detail page links the source site (attribution some feeds
    # require). The list stays free of addresses for guests.
    job["source_homepage"] = _homepage(row["source_homepage"])
    return job


def published_source_url(job_id: int) -> str | None:
    """Source URL for a published job. None when the job is not public."""
    conn = _connect()
    try:
        row = conn.execute(
            """
            SELECT js.source_url
            FROM jobs j
            JOIN job_sources js ON js.job_id = j.id
            WHERE j.id = ? AND j.status = 'published'
              AND COALESCE(j.hidden, 0) = 0
              AND (j.merged_into IS NULL OR j.merged_into = 0)
            ORDER BY js.id
            LIMIT 1
            """,
            (job_id,),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    return row["source_url"] or ""


def apply_target(job_id: int) -> dict | None:
    """How a published ad is applied to. External ads expose the URL only here."""
    conn = _connect()
    try:
        row = conn.execute(
            """
            SELECT
                COALESCE(j.owner_subject, '') AS owner_subject,
                (
                    SELECT js.source_url
                    FROM job_sources js
                    WHERE js.job_id = j.id AND TRIM(js.source_url) != ''
                    ORDER BY js.id
                    LIMIT 1
                ) AS source_url
            FROM jobs j
            WHERE j.id = ?
              AND j.status = 'published'
              AND COALESCE(j.hidden, 0) = 0
              AND (j.merged_into IS NULL OR j.merged_into = 0)
            """,
            (job_id,),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    if (row["owner_subject"] or "").strip():
        return {"kind": "onsite"}
    url = row["source_url"] or ""
    if not url:
        return None
    return {"kind": "external", "url": url}
