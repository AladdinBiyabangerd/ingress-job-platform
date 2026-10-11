"""One-time migration for open remote ads whose remote is limited to a region that
excludes Azerbaijan (EU/US/LATAM only, country lists, work-authorization, regional source
boards). Timezone overlap is NOT a reason any more.
  - region-locked, NO relocation/visa offer -> remote 1 -> 0
  - region-locked, relocation/visa offered (text or stored relocation=1) ->
    remote 1 -> 0 AND relocation -> 1 (relocation overrides the lock)
Neighbouring-region ads (Asia/Turkey/Georgia...) that the text opens to Azerbaijan are kept.
Touches ONLY jobs.remote / jobs.relocation. Never hides, never changes status.
Default is dry-run; --apply writes in one transaction. Aborts if >25% of remote rows match.
A read-only section also lists hidden/rejected ads that the new rules would accept
(report only; never written).

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

from worker.techstack import (  # noqa: E402
    az_market_relevant,
    foreign_locked_remote,
    international_reloc_offer,
    neighbour_region_eligible,
    region_restriction_reason,
)

MAX_SHARE = 0.25


def plain(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text or ""))


def report_newly_acceptable(conn) -> None:
    """Read-only: hidden/rejected ads (joined to a job row by source_url) that the
    current rules would accept, per source/reason. crawl_rejects keeps only URLs, so
    rejects without a stored job row cannot be re-judged without a re-crawl."""
    total = conn.execute("SELECT COUNT(*) FROM crawl_rejects").fetchone()[0]
    rows = conn.execute(
        "SELECT cr.reason cr_reason, j.id, j.title, j.city, j.text, j.remote, j.relocation, "
        "j.hidden, s.source_name src FROM job_sources s JOIN jobs j ON j.id=s.job_id "
        "LEFT JOIN crawl_rejects cr ON cr.source_url=s.source_url "
        "WHERE (j.hidden=1 OR cr.source_url IS NOT NULL) AND j.merged_into IS NULL"
    ).fetchall()
    out = collections.defaultdict(list)
    for r in rows:
        text = plain(r["text"])
        reason = r["cr_reason"] or "hidden"
        if reason not in ("foreign_locked_remote", "hidden", "foreign_office"):
            continue
        remote = bool(r["remote"])
        if not remote:
            continue
        if not foreign_locked_remote(r["title"], r["city"], text, r["src"] or ""):
            ok, how = True, "now_remote"
        elif az_market_relevant(r["title"], r["city"], text, remote=True, relocation=bool(r["relocation"]),
                                source=r["src"] or "", structured_relocation=bool(r["relocation"])):
            ok, how = True, "now_relocation"
        else:
            continue
        out[(r["src"], reason, how)].append(r["id"])
    print(f"\ncrawl_rejects total: {total}; rows joined to a job: {len(rows)}")
    print("hidden/rejected jobs passing the geo gate now (UPPER BOUND, many hidden for other reasons; report only):")
    for (src, reason, how), ids in sorted(out.items(), key=lambda kv: -len(kv[1])):
        print(f"  {src} | {reason} | {how}: {len(ids)} e.g. {ids[:6]}")


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
    hits, by = [], collections.defaultdict(list)  # hits: (id, set_relocation)
    for r in rows:
        text = plain(r["text"])
        reason, offer = "", False
        for src in (r["src"] or "").split("|") or [""]:
            reason = region_restriction_reason(r["title"], r["city"], text, src)
            if not reason or neighbour_region_eligible(r["title"], r["city"], text):
                reason = ""
                break  # an unrestricted source listing exists
        if reason:
            offer = bool(r["relocation"]) or international_reloc_offer(r["title"], r["city"], text)
            hits.append((r["id"], offer))
            by[reason + ("+relocation" if offer else "")].append(r["id"])
            print(f"#{r['id']} remote: 1 -> 0{' relocation: ->1' if offer else ''} | {reason} | "
                  f"{r['title'][:60]} | reloc={r['relocation']}")
    print(f"\nremote rows scanned: {len(rows)}, to change: {len(hits)}")
    for k, v in by.items():
        print(f"  {k}: {len(v)}")
    report_newly_acceptable(conn)
    if rows and len(hits) / len(rows) > MAX_SHARE:
        print(f"STOP: >{int(MAX_SHARE*100)}% of remote rows match; not applying.")
        return 2
    if not args.apply:
        print("dry-run: nothing written (use --apply)")
        return 0
    with conn:
        for i, offer in hits:
            if offer:
                conn.execute("UPDATE jobs SET remote=0, relocation=1 WHERE id=?", (i,))
            else:
                conn.execute("UPDATE jobs SET remote=0 WHERE id=?", (i,))
    print("applied", len(hits), "updates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
