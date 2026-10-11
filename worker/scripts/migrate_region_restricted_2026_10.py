"""One-time migration: remote=1 -> 0 for open ads whose remote is limited to a region
that excludes Azerbaijan (EU/US/LATAM only, Western timezone overlap, work-authorization,
regional source boards). Touches ONLY jobs.remote. Never hides, never changes status.
Default is dry-run; --apply writes in one transaction. Aborts if >25% of remote rows match.

  .venv/bin/python scripts/migrate_region_restricted_2026_10.py [--db data/jobs.sqlite] [--apply]
"""
from __future__ import annotations

import argparse
import collections
import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from worker.techstack import region_restriction_reason  # noqa: E402

MAX_SHARE = 0.25


def plain(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text or ""))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="data/jobs.sqlite")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args(argv)
    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT j.id,j.title,j.city,j.text,j.relocation,"
        "(SELECT group_concat(source_name,'|') FROM job_sources s WHERE s.job_id=j.id) src "
        "FROM jobs j WHERE j.remote=1 AND j.status='published' AND j.hidden=0 "
        "AND j.merged_into IS NULL ORDER BY j.id"
    ).fetchall()
    hits, by = [], collections.defaultdict(list)
    for r in rows:
        reason = ""
        for src in (r["src"] or "").split("|") or [""]:
            reason = region_restriction_reason(r["title"], r["city"], plain(r["text"]), src)
            if not reason:
                break  # an unrestricted source listing exists
        if reason:
            hits.append(r["id"])
            by[reason].append(r["id"])
            print(f"#{r['id']} remote: 1 -> 0 | {reason} | {r['title'][:60]} | reloc={r['relocation']}")
    print(f"\nremote rows scanned: {len(rows)}, to change: {len(hits)}")
    for k, v in by.items():
        print(f"  {k}: {len(v)}")
    if rows and len(hits) / len(rows) > MAX_SHARE:
        print(f"STOP: >{int(MAX_SHARE*100)}% of remote rows match; not applying.")
        return 2
    if not args.apply:
        print("dry-run: nothing written (use --apply)")
        return 0
    with conn:
        for i in hits:
            conn.execute("UPDATE jobs SET remote=0 WHERE id=?", (i,))
    print("applied", len(hits), "updates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
