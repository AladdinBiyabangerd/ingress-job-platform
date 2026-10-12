"""One-time: hide published rows whose TITLE is non-IT under the current title-level
rules (business/sales/legal/risk/GTM/finance/HR/marketing, physical engineering,
crypto business). Sets hidden=1, reject_reason='non_it_title'. Nothing else changes.
Default dry-run; --apply writes in one transaction. Aborts if >10% of rows match.

  .venv/bin/python scripts/migrate_non_it_titles_2026_10.py [--db data/jobs.sqlite] [--apply]
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from worker.techstack import (  # noqa: E402
    _BIZ_KEEP, _BIZ_TITLE, _CRYPTO_BIZ_TITLE, _PHYSICAL_TITLE, _STRONG_TITLE,
)

MAX_SHARE = 0.10


def non_it(title: str) -> str:
    if _PHYSICAL_TITLE.search(title):
        return "physical"
    if _BIZ_TITLE.search(title) and not _BIZ_KEEP.search(title):
        return "business"
    if _CRYPTO_BIZ_TITLE.search(title) and not _STRONG_TITLE.search(title):
        return "crypto_business"
    return ""


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="data/jobs.sqlite")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)
    conn = sqlite3.connect(a.db)
    rows = conn.execute("SELECT id,title FROM jobs WHERE status='published' AND hidden=0 "
                        "AND merged_into IS NULL ORDER BY id").fetchall()
    hits = [(i, t, r) for i, t in rows if (r := non_it(t or ""))]
    for i, t, r in hits:
        print(f"#{i} | {r} | {t}")
    print(f"\nscanned {len(rows)}, to hide {len(hits)}")
    if rows and len(hits) / len(rows) > MAX_SHARE:
        print("STOP: too many matches; not applying.")
        return 2
    if not a.apply:
        print("dry-run: nothing written (use --apply)")
        return 0
    with conn:
        conn.executemany("UPDATE jobs SET hidden=1, reject_reason='non_it_title' WHERE id=?",
                         [(i,) for i, _, _ in hits])
    print("applied", len(hits))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
