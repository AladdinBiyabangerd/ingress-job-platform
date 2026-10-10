"""Hide scraped ads that fail the Azerbaijan market rules (keyword pass).

Company-posted ads (owner_subject set) are left alone. Matching source URLs
are written to crawl_rejects so the next crawl skips them without AI.
"""

from __future__ import annotations

import logging
from typing import Any

from worker.market_fit import ensure_rejects_table, mark_rejected
from worker.techstack import (
    az_market_relevant,
    foreign_office_without_offer,
    relocation_flag,
    remote_flag,
)

log = logging.getLogger("ingress-job.worker.market_purge")


def _row_get(row: Any, key: str, index: int):
    if hasattr(row, "keys"):
        try:
            return row[key]
        except Exception:
            pass
    return row[index]


def off_market_reason(title: str, place: str, text: str, *, remote: bool, relocation: bool) -> str:
    """Empty string when the ad may stay; otherwise a short reject reason."""
    kw_remote = remote or remote_flag(title, place, text)
    kw_reloc = relocation or relocation_flag(title, place, text)
    if foreign_office_without_offer(title, place, text):
        return "foreign_office"
    if not kw_remote and not kw_reloc:
        return "no_remote_or_reloc"
    if not az_market_relevant(
        title,
        place,
        text,
        remote=kw_remote,
        relocation=kw_reloc,
    ):
        return "foreign_locked_remote"
    return ""


def purge_off_market(conn) -> dict[str, int]:
    """Scan published scraped jobs; hide offenders; mark their source URLs."""
    ensure_rejects_table(conn)
    rows = conn.execute(
        """
        SELECT j.id, j.title, j.city,
               COALESCE(NULLIF(j.cleaned_text, ''), j.text) AS body,
               COALESCE(j.remote, 0) AS remote,
               COALESCE(j.relocation, 0) AS relocation
        FROM jobs j
        WHERE COALESCE(j.hidden, 0) = 0
          AND LOWER(COALESCE(j.status, '')) = 'published'
          AND COALESCE(j.owner_subject, '') = ''
          AND COALESCE(j.merged_into, 0) = 0
        ORDER BY j.id
        """
    ).fetchall()

    hide_ids: list[int] = []
    reasons: dict[str, int] = {}
    rejected_urls = 0

    for row in rows:
        job_id = int(_row_get(row, "id", 0))
        title = str(_row_get(row, "title", 1) or "")
        place = str(_row_get(row, "city", 2) or "")
        text = str(_row_get(row, "body", 3) or "")
        remote = bool(int(_row_get(row, "remote", 4) or 0))
        relocation = bool(int(_row_get(row, "relocation", 5) or 0))
        reason = off_market_reason(
            title, place, text, remote=remote, relocation=relocation
        )
        if not reason:
            continue
        hide_ids.append(job_id)
        reasons[reason] = reasons.get(reason, 0) + 1
        urls = conn.execute(
            """
            SELECT source_url FROM job_sources
            WHERE job_id = ? AND TRIM(COALESCE(source_url, '')) != ''
            """,
            (job_id,),
        ).fetchall()
        for url_row in urls:
            url = str(_row_get(url_row, "source_url", 0) or "").strip()
            if not url:
                continue
            mark_rejected(conn, url, reason, via_ai=False)
            rejected_urls += 1

    if hide_ids:
        chunk = 400
        with conn:
            for i in range(0, len(hide_ids), chunk):
                part = hide_ids[i : i + chunk]
                conn.execute(
                    f"UPDATE jobs SET hidden = 1 WHERE id IN ({', '.join('?' for _ in part)})",
                    part,
                )

    stats = {
        "scanned": len(rows),
        "hidden": len(hide_ids),
        "rejected_urls": rejected_urls,
        **{f"reason_{k}": v for k, v in sorted(reasons.items())},
    }
    log.info("market_purge %s", stats)
    return stats
