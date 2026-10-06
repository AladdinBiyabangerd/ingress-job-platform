"""Company directory derived from the public (published, visible) jobs.

There is no companies table: a company is every visible job whose company
name normalizes to the same key. The key ignores case, spacing, quotes and
common legal forms (LLC, MMC, GmbH, Inc, ООО ...), so "Acme, Inc." and
"ACME LLC" are one company. Empty and placeholder names ("Confidential",
"Company not listed") are skipped.

Application numbers are plain counts from the on-site applications table,
read with one grouped query. No applicant data is selected.
"""

from __future__ import annotations

import hashlib
import math
import re
import unicodedata
from collections import Counter

# Legal forms removed from the start or end of a name. Lower case, dots removed.
_LEGAL = {
    "llc", "llp", "lp", "ltd", "limited", "inc", "incorporated", "corp", "corporation", "co", "company",
    "plc", "gmbh", "ag", "kg", "ug", "se", "sa", "sas", "sarl", "srl", "spa", "bv", "nv", "oy", "ab", "as",
    "aps", "kft", "pty", "pte", "sro", "doo", "ou", "oü", "jsc", "ojsc", "cjsc", "pjsc",
    "mmc", "asc", "qsc", "aşc", "qasc", "ooo", "оао", "ооо", "зао", "пао", "ао", "тоо", "тов", "ип",
}
# Forms that also come first ("ООО «Ромашка»", "MMC Kontakt").
_LEGAL_PREFIX = {"mmc", "asc", "qsc", "asc", "ooo", "оао", "ооо", "зао", "пао", "ао", "тоо", "тов", "ип", "llc", "jsc"}
# Multi-word legal forms, matched on the normalized (lower case, no punctuation) text.
_LEGAL_PHRASES = (
    "məhdud məsuliyyətli cəmiyyəti",
    "məhdud məsuliyyətli cəmiyyət",
    "açıq səhmdar cəmiyyəti",
    "qapalı səhmdar cəmiyyəti",
    "səhmdar cəmiyyəti",
    "sp z oo",
    "pty ltd",
    "pte ltd",
    "co ltd",
    "public limited company",
    "limited liability company",
)
_JUNK = {
    "", "confidential", "company confidential", "anonymous", "anonim", "hidden", "private", "n a", "na", "none",
    "null", "unknown", "not specified", "not listed", "company not listed", "employer", "company", "şirkət",
    "şirkət göstərilməyib", "gizli", "konfidensial", "компания", "компания не указана", "не указана",
    "конфиденциально", "работодатель", "stealth", "stealth startup", "stealth mode", "-", "—",
}
_QUOTES = "\"'«»“”„‘’`´"
_AZ_LATIN = str.maketrans({"ə": "e", "ı": "i", "ş": "s", "ç": "c", "ğ": "g", "ö": "o", "ü": "u", "і": "i"})
_CYRILLIC = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "zh", "з": "z", "и": "i",
    "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t",
    "у": "u", "ф": "f", "х": "h", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sch", "ъ": "", "ы": "y", "ь": "",
    "э": "e", "ю": "yu", "я": "ya", "ї": "yi", "є": "ye", "ґ": "g",
}

SORTS = ("jobs", "newest", "name", "applications")
EXCLUDED_STATUSES = ("withdrawn", "deleted")


def _words(name: str) -> list[str]:
    text = unicodedata.normalize("NFKD", unicodedata.normalize("NFKC", name or "").casefold())
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = text.replace("&", " and ")
    for ch in _QUOTES:
        text = text.replace(ch, " ")
    text = re.sub(r"(?<=\w)\.(?=\w)", "", text)  # l.l.c -> llc, s.a. -> sa.
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    return text.split()


_JUNK_KEYS = {" ".join(_words(item)) for item in _JUNK}


def company_key(name: object) -> str:
    """Normalized identity of a company name, or "" for empty/placeholder names."""
    words = _words(str(name or ""))
    joined = " ".join(words)
    if joined in _JUNK_KEYS or not re.search(r"[^\W\d_]", joined):
        return ""
    for phrase in _LEGAL_PHRASES:
        joined = re.sub(rf"(?:^|\s){re.escape(phrase)}(?:\s|$)", " ", joined).strip()
    words = joined.split()
    # Strip legal forms at either end, keeping at least one real word.
    while len(words) > 1 and words[-1] in _LEGAL:
        words.pop()
    while len(words) > 1 and words[0] in _LEGAL_PREFIX:
        words.pop(0)
    key = " ".join(words)
    if key in _JUNK_KEYS or key in _LEGAL or not re.search(r"[^\W\d_]", key):
        return ""
    return key


def slug_for(key: str) -> str:
    """URL slug for a company key: ASCII words joined by "-"; a hash when nothing is left."""
    if not key:
        return ""
    text = key.translate(_AZ_LATIN)
    text = "".join(_CYRILLIC.get(ch, ch) for ch in text)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:80].strip("-")
    if not slug:
        slug = "c-" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:10]
    return slug


def company_slug(name: object) -> str:
    return slug_for(company_key(name))


def _rollback(conn) -> None:
    # A failed statement aborts a Postgres transaction; sqlite ignores this.
    try:
        conn.rollback()
    except Exception:
        pass


def application_counts(conn) -> dict[int, int]:
    """job id -> on-site application count, in one grouped query."""
    try:
        rows = conn.execute(
            """
            SELECT a.job_id AS job_id, COUNT(*) AS total
            FROM applications a
            WHERE LOWER(COALESCE(a.status, '')) NOT IN ('withdrawn', 'deleted')
            GROUP BY a.job_id
            """
        ).fetchall()
    except Exception:
        _rollback(conn)
        return {}
    return {int(row["job_id"]): int(row["total"] or 0) for row in rows}


def application_count(conn, job_id: int) -> int:
    try:
        row = conn.execute(
            """
            SELECT COUNT(*) AS total
            FROM applications a
            WHERE a.job_id = ? AND LOWER(COALESCE(a.status, '')) NOT IN ('withdrawn', 'deleted')
            """,
            (job_id,),
        ).fetchone()
    except Exception:
        _rollback(conn)
        return 0
    return int(row["total"] or 0) if row is not None else 0


def _display_name(spellings: list[str]) -> str:
    # The most used spelling; a tie goes to the one on the newest job (spellings are newest first).
    counts = Counter(spellings)
    return sorted(counts, key=lambda name: (-counts[name], spellings.index(name)))[0]


def _top(counter: Counter, limit: int) -> list[dict]:
    ranked = sorted(counter.items(), key=lambda item: (-item[1], item[0].casefold()))
    return [{"name": name, "count": count} for name, count in ranked[:limit]]


def summarize(jobs: list[dict]) -> tuple[dict[str, dict], dict[str, list[dict]], int]:
    """Group public jobs by company slug.

    Returns (summaries by slug, jobs by slug newest first, on-site applications
    across all listed companies). Each job needs company, city, remote,
    relocation, category, tech_stack, created_at, onsite and applications.
    """
    groups: dict[str, list[dict]] = {}
    for job in jobs:
        slug = company_slug(job.get("company"))
        if slug:
            groups.setdefault(slug, []).append(job)
    total_apps = sum(int(job.get("applications") or 0) for group in groups.values() for job in group if job.get("onsite"))
    summaries: dict[str, dict] = {}
    ordered: dict[str, list[dict]] = {}
    for slug, group in groups.items():
        group = sorted(group, key=lambda job: (str(job.get("created_at") or ""), int(job.get("id") or 0)), reverse=True)
        ordered[slug] = group
        names = [str(job.get("company") or "").strip() for job in group]
        categories = Counter(job["category"] for job in group if job.get("category"))
        tech = Counter(name for job in group for name in (job.get("tech_stack") or []))
        cities = Counter(str(job.get("city") or "").strip() for job in group if str(job.get("city") or "").strip())
        onsite = [job for job in group if job.get("onsite")]
        apps = sum(int(job.get("applications") or 0) for job in onsite)
        remote = sum(1 for job in group if job.get("remote") or job.get("job_type") == "uzaqdan")
        summaries[slug] = {
            "slug": slug,
            "name": _display_name(names),
            "open_jobs": len(group),
            "onsite_jobs": len(onsite),
            "remote_jobs": remote,
            "relocation_jobs": sum(1 for job in group if job.get("relocation")),
            "remote_share": round(100 * remote / len(group)),
            "top_categories": _top(categories, 3),
            "top_tech": _top(tech, 6),
            "locations": [item["name"] for item in _top(cities, 5)],
            "latest_posted": str(group[0].get("created_at") or ""),
            "applications": apps,
            "applications_per_job": round(apps / len(onsite), 1) if onsite else 0.0,
            "application_share": round(100 * apps / total_apps, 1) if total_apps else 0.0,
        }
    return summaries, ordered, total_apps


def _sorted(items: list[dict], sort: str) -> list[dict]:
    # Stable sorts, least important key first.
    out = sorted(items, key=lambda item: (item["name"].casefold(), item["slug"]))
    if sort == "name":
        return out
    out.sort(key=lambda item: item["latest_posted"], reverse=True)
    if sort == "newest":
        return out
    out.sort(key=lambda item: item["open_jobs"], reverse=True)
    if sort == "applications":
        out.sort(key=lambda item: item["applications"], reverse=True)
    return out


def _page(items: list, page: int, per_page: int) -> dict:
    total = len(items)
    pages = max(1, math.ceil(total / per_page))
    current = min(max(1, page), pages)
    start = (current - 1) * per_page
    return {"items": items[start : start + per_page], "total": total, "page": current, "per_page": per_page, "pages": pages}


def _matches(summary: dict, query: str) -> bool:
    if not query:
        return True
    needle = query.casefold().strip()
    if needle in summary["name"].casefold():
        return True
    key = company_key(query)
    return bool(key) and slug_for(key) in summary["slug"]


def paginate_directory(
    summaries: dict[str, dict],
    total_apps: int,
    *,
    q: str = "",
    sort: str = "jobs",
    page: int = 1,
    per_page: int = 24,
) -> dict:
    chosen = sort if sort in SORTS else "jobs"
    items = _sorted([item for item in summaries.values() if _matches(item, q)], chosen)
    result = _page(items, page, per_page)
    result.update({"sort": chosen, "q": q, "companies": len(summaries), "total_applications": total_apps})
    return result


def company_directory(jobs: list[dict], *, q: str = "", sort: str = "jobs", page: int = 1, per_page: int = 24) -> dict:
    summaries, _, total_apps = summarize(jobs)
    return paginate_directory(summaries, total_apps, q=q, sort=sort, page=page, per_page=per_page)


def company_detail(jobs: list[dict], slug: str, *, page: int = 1, per_page: int = 20) -> dict | None:
    summaries, ordered, total_apps = summarize(jobs)
    return company_page_from_groups(summaries, ordered, total_apps, slug, page=page, per_page=per_page)


def company_page_from_groups(
    summaries: dict[str, dict],
    ordered: dict[str, list[dict]],
    total_apps: int,
    slug: str,
    *,
    page: int = 1,
    per_page: int = 20,
) -> dict | None:
    summary = summaries.get(slug)
    if summary is None:
        return None
    return {"company": summary, "jobs": _page(ordered[slug], page, per_page), "total_applications": total_apps}
