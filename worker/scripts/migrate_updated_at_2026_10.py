"""One-time: jobs.updated_at = '' -> created_at. Dry-run by default; --apply writes
(after copying the DB to <db>.bak-updated-at-<ts>)."""
from __future__ import annotations

import argparse
import shutil
import sqlite3
import time
from pathlib import Path

DEFAULT_DB = Path(__file__).resolve().parents[1] / "data" / "jobs.sqlite"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(DEFAULT_DB))
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    db = Path(args.db)
    conn = sqlite3.connect(db)
    n = conn.execute("SELECT COUNT(*) FROM jobs WHERE updated_at = '' OR updated_at IS NULL").fetchone()[0]
    print(f"rows with empty updated_at: {n}")
    if not args.apply:
        print("dry-run; pass --apply to write")
        return
    backup = db.with_name(f"{db.name}.bak-updated-at-{time.strftime('%Y%m%d%H%M%S')}")
    conn.close()
    shutil.copy2(db, backup)
    print(f"backup: {backup}")
    conn = sqlite3.connect(db)
    with conn:
        cur = conn.execute(
            "UPDATE jobs SET updated_at = created_at WHERE updated_at = '' OR updated_at IS NULL"
        )
    print(f"updated: {cur.rowcount}")


if __name__ == "__main__":
    main()
