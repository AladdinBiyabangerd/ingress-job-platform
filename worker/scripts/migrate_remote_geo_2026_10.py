"""One-time migration: remote=1 -> 0 for ads whose remote is locked to a country/region.

Only open rows (published, not hidden, not merged); hidden rows are left alone.
Touches ONLY jobs.remote (1 -> 0). Never hidden/status/city/relocation, never dedupes.
Default is dry-run; use --apply to write (single transaction).

  .venv/bin/python scripts/migrate_remote_geo_2026_10.py [--db data/jobs.sqlite] [--apply]
"""
from __future__ import annotations

import argparse
import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from worker.techstack import foreign_locked_remote  # noqa: E402


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
        "SELECT id,title,city,text,status,hidden,relocation FROM jobs WHERE remote=1 AND status='published' AND hidden=0 "
        "AND merged_into IS NULL ORDER BY id"
    ).fetchall()
    ids = []
    for r in rows:
        if foreign_locked_remote(r["title"], r["city"], plain(r["text"])):
            ids.append(r["id"])
            print(f"#{r['id']} remote: 1 -> 0 | {r['title'][:70]} | status={r['status']} "
                  f"hidden={r['hidden']} relocation={r['relocation']}")
    print(f"\nremote rows scanned: {len(rows)}, rows changed: {len(ids)}")
    if not args.apply:
        print("dry-run: nothing written (use --apply)")
        return 0
    with conn:
        for i in ids:
            conn.execute("UPDATE jobs SET remote=0 WHERE id=?", (i,))
    print("applied", len(ids), "updates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
