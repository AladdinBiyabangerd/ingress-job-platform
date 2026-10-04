"""Read published jobs from the shared jobs database.

SQLite file when DATABASE_URL is unset. The same Postgres database as the
worker when DATABASE_URL is set.

Only status published is selected, so pending, rejected, and closed cabinet ads stay off
the public list. Source URLs stay in job_sources.source_url and are never selected.
Any http(s) or www link inside the description is removed before the
response is built, so a listing address cannot leak through the text.
"""

from __future__ import annotations

import os
import re
import sqlite3
from pathlib import Path

from app.apply_form import parse_stored

def _db_path() -> Path:
    configured = os.environ.get("JOBS_DB_PATH", "").strip()
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[2] / "worker" / "data" / "jobs.sqlite"


DB_PATH = _db_path()

_URL = re.compile(r"(?i)\b(?:https?://|www\.)\S+")

_LIST_SQL = """
SELECT
    j.id,
    j.title,
    j.company,
    j.city,
    COALESCE(NULLIF(j.cleaned_text, ''), j.text) AS text,
    j.created_at,
    COALESCE(j.language, '') AS language,
    COALESCE(j.remote, 0) AS remote,
    COALESCE(j.salary, '') AS salary,
    COALESCE(j.job_type, '') AS job_type,
    COALESCE(j.owner_subject, '') AS owner_subject,
    COALESCE(j.apply_form, '') AS apply_form,
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
    ) AS source_name
FROM jobs j
WHERE j.status = 'published'
  AND COALESCE(j.hidden, 0) = 0
  AND (j.merged_into IS NULL OR j.merged_into = 0)
ORDER BY j.id
"""


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


def _public(row: sqlite3.Row) -> dict:
    title = _plain(row["title"] or "")
    body = public_text(row["text"] or "")
    stored = (row["language"] or "").strip().lower()
    language = stored if stored in {"az", "en", "ru"} else listing_language(title, body)
    job_type = (row["job_type"] or "").strip().lower()
    if job_type not in {"ofis", "hibrid", "uzaqdan"}:
        job_type = ""
    return {
        "id": int(row["id"]),
        "title": title,
        "company": _plain(row["company"] or ""),
        "city": _plain(row["city"] or ""),
        "remote": bool(int(row["remote"] or 0)),
        "text": body,
        "language": language,
        "salary": _plain(row["salary"] or ""),
        "job_type": job_type,
        "source_name": row["source_name"] or "",
        "created_at": row["created_at"] or "",
        "onsite": bool((row["owner_subject"] or "").strip()),
        "has_original": bool(int(row["has_original"] or 0)),
        "form": parse_stored(row["apply_form"]) if (row["owner_subject"] or "").strip() else None,
    }


def list_jobs() -> list[dict]:
    conn = _connect()
    try:
        rows = conn.execute(_LIST_SQL).fetchall()
    finally:
        conn.close()
    return [_public(row) for row in rows]


def get_job(job_id: int) -> dict | None:
    conn = _connect()
    try:
        row = conn.execute(
            f"SELECT * FROM ({_LIST_SQL}) AS published WHERE id = ?",
            (job_id,),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    return _public(row)


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
