"""One-time refresh: NoDesk ads were stored from the RSS summary (first paragraphs only).

Re-reads each NoDesk listing page (robots.txt allows it; PoliteClient pacing), rebuilds
text + tech stack and runs the normal acceptance rules (finish_item, AI market-fit off).
Accepted rows go through Store.upsert (re-approval / updated_at / job_skill rules apply);
rows the rules now reject are hidden with reject_reason. Default is dry-run.

  .venv/bin/python scripts/refresh_nodesk_2026_10.py [--db data/jobs.sqlite] [--apply]
  DATABASE_URL=postgres://... .venv/bin/python scripts/refresh_nodesk_2026_10.py --prod [--apply]
  (on Railway: railway run --service worker -- .venv/bin/python scripts/refresh_nodesk_2026_10.py --prod)

Preview opens the database read-only (sqlite mode=ro / Postgres read-only
session) and writes nothing. --apply first backs up: sqlite file copy, or for
Postgres a JSON dump of the touched jobs/job_sources/job_skill rows.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import sys
import time
from pathlib import Path

os.environ["AI_MARKET_FIT_ENABLED"] = "0"
os.environ["AI_GATEWAY_ENABLED"] = "0"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from worker.acceptance import finish_item  # noqa: E402
from worker.db import Store  # noqa: E402
from worker.http import PoliteClient  # noqa: E402
from worker.parsing import clean, posting_item  # noqa: E402


class _Conn:
    name = "NoDesk"
    remote_default = True
    credit_note = "NoDesk public RSS feed. The link opens the ad on nodesk.co."

    class store:  # noqa: N801 - no reject memory writes during the dry run
        conn = None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="data/jobs.sqlite")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--prod", action="store_true", help="use DATABASE_URL (Postgres)")
    args = ap.parse_args(argv)
    db = Path(args.db)
    if args.prod:
        from worker.jobs_db import connect
        conn = connect()
        conn.execute("SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY")
    else:
        conn = sqlite3.connect(f"file:{db.resolve()}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT j.id, j.title, j.company, j.city, j.status, j.hidden, j.tech_stack, s.source_url, s.external_id "
        "FROM job_sources s JOIN jobs j ON j.id = s.job_id WHERE s.source_name = 'NoDesk' AND j.merged_into IS NULL "
        "ORDER BY j.id"
    ).fetchall()
    store = None
    if args.apply:
        stamp = time.strftime("%Y%m%d%H%M%S")
        if args.prod:
            ids = [int(r["id"]) for r in rows] or [0]
            q = ",".join("?" for _ in ids)
            dump = {t: [{k: x[k] for k in x.keys()} for x in
                        conn.execute(f"SELECT * FROM {t} WHERE {c} IN ({q})", ids).fetchall()]
                    for t, c in (("jobs", "id"), ("job_sources", "job_id"), ("job_skill", "job_id"))}
            bak = Path("data") / f"prod-nodesk-backup-{stamp}.json"
            bak.write_text(json.dumps(dump, ensure_ascii=False, default=str, indent=1))
        else:
            bak = db.with_name(db.name + f".bak-nodesk-{stamp}")
            shutil.copy2(db, bak)
        print("backup:", bak)
        conn.close()
        store = Store(None if args.prod else db, sqlite_only=not args.prod)
        conn = store.conn
    client = PoliteClient()
    changed = rejected = 0
    for r in rows:
        url = r["source_url"]
        try:
            page = posting_item(client.get_text(url)) if client.allowed(url) else None
        except Exception as exc:  # noqa: BLE001
            print(f"#{r['id']} skip ({exc.__class__.__name__}) {url}")
            continue
        if not page or not page.get("text"):
            print(f"#{r['id']} skip (no JobPosting on page) {url}")
            continue
        head = f"{r['title']} at {r['company']}"
        item = {
            "title": r["title"], "company": r["company"], "city": "Remote", "remote": True,
            "text": head + "\n" + page["text"], "source_url": url, "source_name": "NoDesk",
            "external_id": r["external_id"],
        }
        old = json.loads(r["tech_stack"] or "[]")
        done = finish_item(_Conn(), dict(item))
        if done is None:
            rejected += 1
            print(f"#{r['id']} REJECT now | {r['title'][:60]} @ {r['company']} | status={r['status']} hidden={r['hidden']}")
            if args.apply:
                with conn:
                    conn.execute("UPDATE jobs SET hidden = 1, reject_reason = ? WHERE id = ?",
                                 ("nodesk_refresh_rules", r["id"]))
            continue
        changed += 1
        print(f"#{r['id']} ok | {r['title'][:60]} | stack {old} -> {done.get('tech_stack')}")
        if args.apply:
            done["source_name"] = "NoDesk"
            print("   upsert:", store.upsert(done))
    print(f"\nNoDesk rows: {len(rows)}, refreshed: {changed}, now rejected: {rejected}")
    if not args.apply:
        print("dry-run: nothing written (use --apply)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
