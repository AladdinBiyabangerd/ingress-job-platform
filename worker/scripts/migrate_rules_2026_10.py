"""One-time migration: re-apply the current worker rules to existing rows.

Touches ONLY relocation, city, category. Never hidden/status, never dedupes.
Default is dry-run; use --apply to write (single transaction).

  .venv/bin/python scripts/migrate_rules_2026_10.py [--db data/jobs.sqlite] [--apply]
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from worker.place import normalize_city  # noqa: E402
from worker.techstack import classify_category, relocation_flag  # noqa: E402

SKIP_RELOCATION_IDS = {262}  # intentionally left as is


def plain(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text or ""))


def compute(row: dict) -> dict:
    """Return {field: new_value} for fields that differ."""
    out: dict = {}
    title, city, text = row["title"], row["city"], plain(row["text"])
    new_city = normalize_city(city)
    if new_city != city:
        out["city"] = new_city
    try:
        stack = json.loads(row["tech_stack"] or "[]")
    except ValueError:
        stack = []
    # The source's raw category is not stored; the title and stack decide.
    new_cat = classify_category(row["category"], title, stack)
    if row["category"] and new_cat != row["category"]:
        out["category"] = new_cat
    if (
        row["id"] not in SKIP_RELOCATION_IDS
        and row["relocation"]
        and row["remote"]
        and not relocation_flag(title, new_city, text)
    ):
        out["relocation"] = 0
    return out


def kind(field: str, old, new) -> str:
    if field == "relocation":
        return "relocation 1->0"
    if field == "city":
        return "city -> empty" if new == "" else "city normalized"
    return f"category {old}->{new}"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="data/jobs.sqlite")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args(argv)
    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    rows = [dict(r) for r in conn.execute(
        "SELECT id,title,city,text,tech_stack,category,relocation,remote FROM jobs ORDER BY id")]
    changes, counts = [], Counter()
    for r in rows:
        for f, new in compute(r).items():
            changes.append((r["id"], f, r[f], new))
            counts[kind(f, r[f], new)] += 1
    for i, f, old, new in changes:
        print(f"#{i} {f}: {old!r} -> {new!r}")
    print(f"\nrows scanned: {len(rows)}, rows changed: {len({c[0] for c in changes})}")
    for k, n in sorted(counts.items()):
        print(f"  {k}: {n}")
    if not args.apply:
        print("dry-run: nothing written (use --apply)")
        return 0
    with conn:  # one transaction
        for i, f, _old, new in changes:
            conn.execute(f"UPDATE jobs SET {f}=? WHERE id=?", (new, i))
    print("applied", len(changes), "field updates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
