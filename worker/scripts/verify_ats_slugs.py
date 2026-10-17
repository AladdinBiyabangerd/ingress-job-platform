"""Verify employer board slugs before they go into ats_boards.py.

For each "platform:slug" it checks, through PoliteClient (robots.txt, >= 1 s
per host, ingress-job-bot UA): robots.txt allows the board URL, the board
answers, it lists tech roles, and how many of its new tech ads pass the real
acceptance rules (finish_item, AI off) on a throw-away SQLite file. The jobs
database is never touched. Resumable: results are kept in --out.

  python scripts/verify_ats_slugs.py --out /tmp/verify.json --per-board 8 \
      greenhouse:clickhouse lever:mistral ashby:posthog workable:smartnews
  python scripts/verify_ats_slugs.py --out /tmp/verify.json --from-file slugs.txt

A slug is worth adding when ok=True, tech >= 1 and accepted >= 1.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.pop("DATABASE_URL", None)
for _key in ("AI_GATEWAY_ENABLED", "AI_MARKET_FIT_ENABLED", "JOB_TIDY_ENABLED", "EMBEDDINGS_ENABLED"):
    os.environ[_key] = "0"

from worker.acceptance import finish_item  # noqa: E402
from worker.ats_boards_extra import all_groups  # noqa: E402
from worker.connectors.ats import _BASES, _group_class  # noqa: E402
from worker.db import Store  # noqa: E402
from worker.http import Disallowed, NotFound, PoliteClient, SourceBlocked, SourceFailed  # noqa: E402

BOARD_URLS = {
    "greenhouse": "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs",
    "lever": "https://api.lever.co/v0/postings/{slug}?mode=json",
    "ashby": "https://jobs.ashbyhq.com/{slug}",
    "workable": "https://apply.workable.com/api/v1/widget/accounts/{slug}?details=true",
    "recruitee": "https://{slug}.recruitee.com/api/offers/",
    "teamtailor": "https://{slug}.teamtailor.com/jobs.rss",
    "breezy": "https://{slug}.breezy.hr/json",
    "pinpoint": "https://{slug}.pinpointhq.com/postings.json",
}


def existing() -> set[tuple[str, str]]:
    return {(ats, b.lower()) for _n, ats, _r, boards in all_groups() for b in boards}


def verify(client: PoliteClient, store: Store, plat: str, slug: str, per_board: int) -> dict:
    url = BOARD_URLS[plat].format(slug=slug)
    out: dict = {"plat": plat, "slug": slug, "ok": False, "tech": 0, "accepted": 0, "items": []}
    try:
        if not client.allowed(url):
            out["error"] = "robots.txt disallows"
            return out
    except (SourceBlocked, SourceFailed) as exc:
        out["error"] = f"robots: {exc}"[:160]
        return out
    cls = _group_class(f"verify {plat} {slug}", plat, (slug,))
    conn = cls(client, store)
    try:
        try:
            rows = conn.board_items(slug)
        except SourceFailed as exc:
            if "request failed" not in str(exc):
                raise
            rows = conn.board_items(slug)  # one retry for a dropped connection
    except (NotFound, SourceFailed, SourceBlocked, Disallowed, ValueError) as exc:
        out["error"] = f"{type(exc).__name__}: {exc}"[:160]
        return out
    except Exception as exc:  # noqa: BLE001 — one broken board must not stop the sweep
        out["error"] = f"{type(exc).__name__}"[:160]
        return out
    out["ok"] = True
    out["tech"] = len(rows)
    if not rows:
        return out
    conn.candidates = per_board
    try:
        urls = conn.discover()
    except Exception as exc:  # noqa: BLE001
        out["error"] = f"discover {type(exc).__name__}: {exc}"[:160]
        return out
    for link in urls[:per_board]:
        try:
            item = finish_item(conn, conn.normalize(conn.fetch(link), link))
        except SourceBlocked:
            break
        except Exception:  # noqa: BLE001
            continue
        if item:
            out["accepted"] += 1
            out["items"].append({
                "title": str(item.get("title") or "")[:90],
                "company": str(item.get("company") or "")[:60],
                "city": str(item.get("city") or "")[:80],
                "remote": bool(item.get("remote")),
                "relocation": bool(item.get("relocation")),
            })
    out["checked"] = min(len(urls), per_board)
    return out


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("slugs", nargs="*", help="platform:slug")
    ap.add_argument("--from-file", type=Path, help="one platform:slug per line (# comments allowed)")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--per-board", type=int, default=8, help="new tech ads dry-run per board")
    ap.add_argument("--include-existing", action="store_true")
    args = ap.parse_args(argv)

    todo: list[tuple[str, str]] = []
    lines = list(args.slugs)
    if args.from_file:
        lines += args.from_file.read_text(encoding="utf-8").splitlines()
    known = existing()
    for line in lines:
        line = line.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        plat, slug = (x.strip() for x in line.split(":", 1))
        if plat not in BOARD_URLS or plat not in _BASES:
            print(f"skip {line}: unknown platform", flush=True)
            continue
        if not args.include_existing and (plat, slug.lower()) in known:
            print(f"skip {line}: already in ats_boards", flush=True)
            continue
        if (plat, slug) not in todo:
            todo.append((plat, slug))

    state: dict = json.loads(args.out.read_text(encoding="utf-8")) if args.out.exists() else {}
    client = PoliteClient()
    with tempfile.TemporaryDirectory(prefix="ij-verify-") as tmp:
        store = Store(Path(tmp) / "verify.sqlite", sqlite_only=True)
        try:
            for i, (plat, slug) in enumerate(todo, 1):
                key = f"{plat}:{slug}"
                if key in state:
                    continue
                info = verify(client, store, plat, slug, args.per_board)
                state[key] = info
                print(
                    f"{i}/{len(todo)} {key}: ok={info['ok']} tech={info['tech']} "
                    f"accepted={info['accepted']} {info.get('error', '')}",
                    flush=True,
                )
                args.out.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
        finally:
            client.close()
            store.close()
    good = [k for k, v in state.items() if v.get("ok") and v.get("accepted")]
    print(f"done: {len(state)} checked, {len(good)} with accepted ads -> {args.out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
