"""Batch import of ads the user viewed on LinkedIn (Chrome extension).

Rows are written like collected ads: empty owner_subject, source_name
'linkedin-extension'. Dedupe is by LinkedIn job id / source URL.
The original URL is stored in job_sources and is not shown to guests.
"""

from __future__ import annotations

import re
import sqlite3
from urllib.parse import urlsplit

from app.cabinet_store import PUBLISHED, _LOCK, _connect, _now

SOURCE_NAME = "linkedin-extension"
_ID = re.compile(r"^\d{5,20}$")
_AZ = re.compile(r"[əğıöşüçƏĞİÖŞÜÇ]")
_RU = re.compile(r"[а-яА-ЯёЁ]")


def _http(value: str) -> str:
    text = (value or "").strip()
    if not text or len(text) > 500 or any(c.isspace() for c in text):
        return ""
    parts = urlsplit(text)
    if parts.scheme not in {"http", "https"} or not parts.netloc or parts.username or parts.password:
        return ""
    return text


def _language(text: str) -> str:
    if _RU.search(text):
        return "ru"
    if _AZ.search(text):
        return "az"
    return "en"


def _job_type(remote: bool, employment: str) -> str:
    return "uzaqdan" if remote else ""


def import_jobs(items: list[dict]) -> dict:
    """items are validated dicts. Returns created/duplicates/errors counts and details."""
    created: list[dict] = []
    duplicates: list[dict] = []
    errors: list[dict] = []
    now = _now()
    with _LOCK:
        conn = _connect()
        try:
            for item in items:
                lid = str(item.get("linkedin_id") or "").strip()
                title = (item.get("title") or "").strip()[:140]
                company = (item.get("company") or "").strip()[:120]
                if not _ID.match(lid) or not title:
                    errors.append({"linkedin_id": lid, "error": "Başlıq və ya LinkedIn id yanlışdır"})
                    continue
                li_url = f"https://www.linkedin.com/jobs/view/{lid}/"
                apply_url = _http(item.get("apply_url") or "")
                source_url = apply_url or li_url
                remote = bool(item.get("remote"))
                location = (item.get("location") or "").strip()[:80]
                text = (item.get("description") or "").replace("\r\n", "\n").strip()[:8000]
                posted = (item.get("posted") or "").strip()[:60]
                employment = (item.get("employment_type") or "").strip()[:60]
                note = " | ".join(p for p in (f"LinkedIn {li_url}", posted, employment) if p)[:300]
                dup = conn.execute(
                    "SELECT job_id FROM job_sources WHERE source_url IN (?, ?) "
                    "OR (source_name = ? AND external_id = ?)",
                    (li_url, source_url, SOURCE_NAME, lid),
                ).fetchone()
                if dup is not None:
                    duplicates.append({"linkedin_id": lid, "job_id": int(dup[0])})
                    continue
                try:
                    cur = conn.execute(
                        """
                        INSERT INTO jobs (
                            title, company, city, text, cleaned_text, status, created_at, norm_key,
                            owner_subject, language, salary, job_type, remote, updated_at
                        ) VALUES (?, ?, ?, ?, NULL, ?, ?, ?, '', ?, '', ?, ?, ?)
                        """,
                        (
                            title,
                            company,
                            "" if remote else location,
                            text,
                            PUBLISHED,
                            now,
                            f"{SOURCE_NAME}:{lid}",
                            _language(f"{title} {text}"),
                            _job_type(remote, employment),
                            1 if remote else 0,
                            now,
                        ),
                    )
                    job_id = int(cur.lastrowid)
                    conn.execute(
                        """
                        INSERT INTO job_sources (
                            job_id, source_name, source_url, external_id, last_seen, credit_note
                        ) VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (job_id, SOURCE_NAME, source_url, lid, now, note),
                    )
                    conn.commit()
                    created.append({"linkedin_id": lid, "job_id": job_id})
                except sqlite3.IntegrityError:
                    conn.rollback()
                    duplicates.append({"linkedin_id": lid, "job_id": None})
                except Exception as exc:  # one bad row must not stop the batch
                    conn.rollback()
                    errors.append({"linkedin_id": lid, "error": str(exc)[:120]})
        finally:
            conn.close()
    return {
        "created": len(created),
        "duplicates": len(duplicates),
        "errors": len(errors),
        "created_items": created,
        "duplicate_items": duplicates,
        "error_items": errors,
    }
