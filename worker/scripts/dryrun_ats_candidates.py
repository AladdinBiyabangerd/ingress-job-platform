"""Dry-run candidate ATS boards through finish_item (AI off). No jobs DB writes.

Reads signal-board JSON (same shape as docs/source-research-2026-10-signal-boards.json),
skips slugs already in ats_boards.GROUPS, fetches each board via the live connector,
and keeps boards that accept >= 1 ad. Output: JSON list of {slug, plat, accepted, ...}.

  AI_MARKET_FIT_ENABLED=0 python scripts/dryrun_ats_candidates.py \
      --signal ../../docs/source-research-2026-10-signal-boards.json \
      --out /tmp/ats_dryrun_pass.json --limit 80
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("AI_MARKET_FIT_ENABLED", "0")

from worker.acceptance import finish_item  # noqa: E402
from worker.ats_boards_extra import all_groups  # noqa: E402

GROUPS = all_groups()
from worker.connectors.ats import (  # noqa: E402
    GreenhouseConnector,
    LeverConnector,
)
from worker.db import Store  # noqa: E402
from worker.http import NotFound, PoliteClient, SourceFailed  # noqa: E402

US_RISK = re.compile(
    r"\b(us only|usa only|united states only|remote[- ]?us\b|us[- ]?remote|"
    r"canada only|latam only|philippines|brazil only|"
    r"axios|actblue|clearstreet|allegiantair|cgsfederal|agile-defense|kepler)\b",
    re.I,
)
GLOBALISH = re.compile(
    r"\b(anywhere|global|worldwide|world[- ]wide|emea|europe|eu\b|cis|"
    r"remote[- ]europe|europe[- ]remote|open globally)\b",
    re.I,
)
SKIP_SLUGS = {
    # Prior dry-run rejects / aggregators / US-gov contractors (research notes).
    "jobgether", "cribl", "sysdig", "pigment", "scaleway", "honeycomb", "bitgo",
    "axios", "actblue", "clearstreet", "allegiantair", "cgsfederal", "agile-defense",
    "kepler", "greenthumbindustries", "levelaccess", "3cloud", "doordashusa",
    "defenseunicorns", "cgsfederal",
}
CONNECTORS = {"greenhouse": GreenhouseConnector, "lever": LeverConnector}
PER_BOARD_CAP = 12


def known(platform: str) -> set[str]:
    return {b.lower() for _n, ats, _r, boards in GROUPS if ats == platform for b in boards}


def pick_candidates(rows: list[dict], *, limit: int) -> list[dict]:
    known_gh = known("greenhouse")
    known_lv = known("lever")
    out: list[dict] = []
    high: list[dict] = []
    rest: list[dict] = []
    for row in rows:
        plat = row.get("plat")
        slug = str(row.get("slug") or "")
        if plat not in CONNECTORS or not slug:
            continue
        if slug.lower() in SKIP_SLUGS:
            continue
        if slug.lower() in (known_gh if plat == "greenhouse" else known_lv):
            continue
        locs = " ; ".join(row.get("locs") or [])
        if US_RISK.search(slug) or US_RISK.search(locs):
            continue
        if not row.get("sig"):
            continue
        bucket = high if GLOBALISH.search(locs) else rest
        bucket.append(row)
    high.sort(key=lambda r: (-int(r.get("sig") or 0), r["slug"]))
    rest.sort(key=lambda r: (-int(r.get("sig") or 0), r["slug"]))
    # Prefer global/EMEA first, then highest-signal remote boards.
    for row in high + rest:
        out.append(row)
        if len(out) >= limit:
            break
    return out


def dryrun_board(client: PoliteClient, plat: str, slug: str) -> dict:
    cls = CONNECTORS[plat]
    tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
    tmp.close()
    path = Path(tmp.name)
    try:
        store = Store(path)
        # Single-board connector subclass for this slug only.
        conn = type(f"Tmp{plat}{slug}", (cls,), {"name": f"dryrun:{slug}", "boards": (slug,)})(
            client, store
        )
        try:
            urls = conn.discover()
        except (NotFound, SourceFailed) as exc:
            return {"slug": slug, "plat": plat, "ok": False, "error": str(exc)[:160], "accepted": 0}
        accepted = 0
        samples: list[str] = []
        for url in urls[:PER_BOARD_CAP]:
            try:
                raw = conn.fetch(url)
                item = finish_item(conn, conn.normalize(raw, url))
            except Exception as exc:  # noqa: BLE001 — board-level probe
                continue
            if item:
                accepted += 1
                samples.append(str(item.get("title") or "")[:80])
        return {
            "slug": slug,
            "plat": plat,
            "ok": True,
            "found": len(urls),
            "accepted": accepted,
            "samples": samples[:3],
        }
    finally:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--signal", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--limit", type=int, default=60)
    ap.add_argument("--resume", action="store_true")
    args = ap.parse_args(argv)

    rows = json.loads(args.signal.read_text(encoding="utf-8"))
    cands = pick_candidates(rows, limit=args.limit)
    state = {"done": [], "pass": [], "fail": []}
    if args.resume and args.out.exists():
        state = json.loads(args.out.read_text(encoding="utf-8"))
    done = {str(x.get("slug")).lower() for x in state["done"]}
    todo = [r for r in cands if r["slug"].lower() not in done]
    print(f"dry-run: {len(todo)} boards (of {len(cands)} picked)", flush=True)

    client = PoliteClient()
    try:
        for i, row in enumerate(todo, 1):
            info = dryrun_board(client, row["plat"], row["slug"])
            state["done"].append(info)
            (state["pass"] if info.get("accepted", 0) >= 1 else state["fail"]).append(info)
            print(
                f"{i}/{len(todo)} {row['plat']} {row['slug']}: "
                f"accepted={info.get('accepted', 0)} found={info.get('found', '-')}",
                flush=True,
            )
            if i % 5 == 0:
                args.out.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    finally:
        args.out.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        client.close()
    print(
        f"done: pass={len(state['pass'])} fail={len(state['fail'])} -> {args.out}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
