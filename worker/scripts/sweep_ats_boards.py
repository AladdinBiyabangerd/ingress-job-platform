"""One-time sweep: which employer boards are worth adding to ats_boards.py?

Reads a slug list (JSON list, JSON list of {"slug": ...}, CSV with a ``slug``
column, or one slug per line), fetches each board's job LIST once (one request
per board, no posting text), keeps boards that have tech titles AND a
Remote / Anywhere / Global / EMEA / relocation / visa signal, and writes the
candidate slugs to a JSON file. It reads public ATS endpoints only, through
PoliteClient (robots.txt checked, >= 1 s between requests per host). It never
touches the jobs database. The sweep is resumable: processed slugs are stored
in the output file and skipped on the next run.

  python scripts/sweep_ats_boards.py --platform greenhouse --slugs /tmp/lists/gh.csv \
      --skip-existing --out /tmp/lists/gh_candidates.json [--limit 500] [--resume]

Candidates still have to pass a dry-run through finish_item (acceptance) before a
board is added; the signal is only a cheap first filter.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from worker.ats_boards_extra import all_groups  # noqa: E402

GROUPS = all_groups()
from worker.http import (  # noqa: E402
    Disallowed,
    NotFound,
    PoliteClient,
    SourceBlocked,
    SourceFailed,
)
from worker.parsing import clean  # noqa: E402
from worker.techstack import is_tech_job  # noqa: E402

ENDPOINTS = {
    "greenhouse": "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs",
    "lever": "https://api.lever.co/v0/postings/{slug}?mode=json",
    "breezy": "https://{slug}.breezy.hr/json",
    "pinpoint": "https://{slug}.pinpointhq.com/postings.json",
    # api.ashbyhq.com answers robots.txt with 401, so the robots-allowed hosted page is read.
    "ashby": "https://jobs.ashbyhq.com/{slug}",
    "workable": "https://apply.workable.com/api/v1/widget/accounts/{slug}?details=true",
    "recruitee": "https://{slug}.recruitee.com/api/offers/",
}
_RELOC = re.compile(r"relocat\w*|visa sponsor\w*|sponsor\w* (?:a )?visa", re.IGNORECASE)
GLOBAL = re.compile(
    r"\b(anywhere|global(?:ly)?|worldwide|world[- ]wide|emea|europe|eu|apac|asia|relocat\w*|visa|sponsor\w*)\b",
    re.IGNORECASE,
)
REMOTE = re.compile(r"\b(remote|distributed|work from home|wfh)\b", re.IGNORECASE)
# "Remote - US", "Remote (Canada)": remote, but tied to a place that is not ours.
US_ONLY = re.compile(
    r"\b(us|usa|u\.s\.a?\.?|united states|canada|latam|latin america|brazil|mexico|"
    r"california|texas|new york|ny|ca|tx)\b",
    re.IGNORECASE,
)
SAVE_EVERY = 25


def load_slugs(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    slugs: list[str] = []
    stripped = text.lstrip()
    if stripped.startswith("["):
        for row in json.loads(text):
            slugs.append(str(row.get("slug") if isinstance(row, dict) else row))
    elif path.suffix.lower() == ".csv" or stripped.lower().startswith("name,slug"):
        for row in csv.DictReader(text.splitlines()):
            slugs.append(str(row.get("slug") or ""))
    else:
        slugs = [line.strip() for line in text.splitlines()]
    seen: set[str] = set()
    out = []
    for slug in slugs:
        slug = slug.strip()
        if slug and re.fullmatch(r"[A-Za-z0-9_.-]+", slug) and slug.lower() not in seen:
            seen.add(slug.lower())
            out.append(slug)
    return out


def known_slugs(platform: str) -> set[str]:
    known = {b.lower() for _n, ats, _r, boards in GROUPS if ats == platform for b in boards}
    from worker.connectors import ats as _ats
    single = {"workable": _ats.WorkableConnector, "recruitee": _ats.RecruiteeConnector}.get(platform)
    if single is not None:
        known |= {b.lower() for b in single.boards}
    return known


def place_signal(place: str) -> bool:
    if not place:
        return False
    if GLOBAL.search(place):
        return True
    return bool(REMOTE.search(place)) and not US_ONLY.search(place)


def scan_greenhouse(payload: object) -> tuple[int, list[tuple[str, str]]]:
    jobs = payload.get("jobs") if isinstance(payload, dict) else None
    if not isinstance(jobs, list):
        raise SourceFailed("no jobs list")
    rows = []
    for job in jobs:
        if isinstance(job, dict):
            rows.append((clean(job.get("title")), clean((job.get("location") or {}).get("name"))))
    return len(jobs), rows


def scan_lever(payload: object) -> tuple[int, list[tuple[str, str]]]:
    if not isinstance(payload, list):
        raise SourceFailed("not a list")
    rows = []
    for job in payload:
        if not isinstance(job, dict):
            continue
        cats = job.get("categories") or {}
        places = [clean(p) for p in cats.get("allLocations") or [] if clean(p)] or [clean(cats.get("location"))]
        place = "; ".join(p for p in places if p)
        if str(job.get("workplaceType") or "").lower() == "remote":
            place = (place + "; Remote").strip("; ")
        text = clean(job.get("descriptionPlain"))[:4000].lower()
        if re.search(r"relocat\w*|visa sponsor\w*|sponsor\w* (?:a )?visa", text):
            place = (place + "; relocation").strip("; ")
        rows.append((clean(job.get("text")), place))
    return len(payload), rows


def scan_breezy(payload: object) -> tuple[int, list[tuple[str, str]]]:
    if not isinstance(payload, list):
        raise SourceFailed("not a list")
    rows = []
    for job in payload:
        if not isinstance(job, dict):
            continue
        loc = job.get("location") if isinstance(job.get("location"), dict) else {}
        place = clean(loc.get("name"))
        if loc.get("is_remote"):
            country = clean((loc.get("country") or {}).get("name")) if isinstance(loc.get("country"), dict) else ""
            place = f"Remote {country}".strip() if country and not US_ONLY.search(country) else (place + "; Remote").strip("; ")
        rows.append((clean(job.get("name")), place))
    return len(payload), rows


def scan_pinpoint(payload: object) -> tuple[int, list[tuple[str, str]]]:
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, list):
        raise SourceFailed("no data list")
    rows = []
    for job in data:
        if not isinstance(job, dict):
            continue
        loc = job.get("location") if isinstance(job.get("location"), dict) else {}
        place = clean(loc.get("name"))
        if str(job.get("workplace_type") or "").lower() == "remote":
            place = (place + "; Remote").strip("; ")
        if re.search(r"relocat\w*|visa sponsor\w*", str(job.get("description") or "")[:6000], re.IGNORECASE):
            place = (place + "; relocation").strip("; ")
        rows.append((clean(job.get("title")), place))
    return len(data), rows


def scan_ashby(payload: object) -> tuple[int, list[tuple[str, str]]]:
    from worker.connectors.ats import _ashby_app_data
    board = _ashby_app_data(str(payload)).get("jobBoard") or {}
    posts = board.get("jobPostings") if isinstance(board, dict) else None
    if not isinstance(posts, list):
        raise SourceFailed("no postings")
    rows = []
    for job in posts:
        if not isinstance(job, dict):
            continue
        places = [clean(job.get("locationName"))] + [
            clean(x.get("locationName") if isinstance(x, dict) else x) for x in job.get("secondaryLocations") or []]
        place = "; ".join(p for p in places if p)
        if str(job.get("workplaceType") or "").lower() == "remote":
            place = (place + "; Remote").strip("; ")
        rows.append((clean(job.get("title")), place))
    return len(posts), rows


def scan_workable(payload: object) -> tuple[int, list[tuple[str, str]]]:
    jobs = payload.get("jobs") if isinstance(payload, dict) else None
    if not isinstance(jobs, list):
        raise SourceFailed("no jobs list")
    rows = []
    for job in jobs:
        if not isinstance(job, dict):
            continue
        place = ", ".join(x for x in (clean(job.get("city")), clean(job.get("country"))) if x)
        if job.get("telecommuting"):
            place = (place + "; Remote").strip("; ")
        if _RELOC.search(str(job.get("description") or "")[:8000]):
            place = (place + "; relocation").strip("; ")
        rows.append((clean(job.get("title")), place))
    return len(jobs), rows


def scan_recruitee(payload: object) -> tuple[int, list[tuple[str, str]]]:
    offers = payload.get("offers") if isinstance(payload, dict) else None
    if not isinstance(offers, list):
        raise SourceFailed("no offers list")
    rows = []
    for job in offers:
        if not isinstance(job, dict):
            continue
        place = clean(job.get("location")) or clean(job.get("country"))
        if job.get("remote"):
            place = (place + "; Remote").strip("; ")
        if _RELOC.search(str(job.get("description") or "")[:8000] + str(job.get("requirements") or "")[:4000]):
            place = (place + "; relocation").strip("; ")
        rows.append((clean(job.get("title")), place))
    return len(offers), rows


SCANNERS = {"ashby": scan_ashby, "workable": scan_workable, "recruitee": scan_recruitee,
            "greenhouse": scan_greenhouse, "lever": scan_lever, "breezy": scan_breezy, "pinpoint": scan_pinpoint}


def sweep_one(client: PoliteClient, platform: str, slug: str) -> dict:
    url = ENDPOINTS[platform].format(slug=slug)
    payload = client.get_text(url) if platform == "ashby" else client.get_json(url)
    total, rows = SCANNERS[platform](payload)
    tech = [(t, p) for t, p in rows if t and is_tech_job(t)]
    sig = [(t, p) for t, p in tech if place_signal(p)]
    locs = sorted({p for _t, p in sig if p})[:4]
    return {"slug": slug, "live": True, "total": total, "tech": len(tech), "sig": len(sig),
            "locs": locs, "plat": platform}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--platform", choices=sorted(ENDPOINTS), required=True)
    ap.add_argument("--slugs", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--limit", type=int, default=0, help="stop after this many boards this run")
    ap.add_argument("--skip-existing", action="store_true", help="skip slugs already in ats_boards.GROUPS")
    ap.add_argument("--skip-file", type=Path, action="append", default=[],
                    help="JSON list (or sweep output) of slugs to skip")
    ap.add_argument("--resume", action="store_true", help="continue from --out if it exists")
    args = ap.parse_args(argv)

    slugs = load_slugs(args.slugs)
    skip: set[str] = known_slugs(args.platform) if args.skip_existing else set()
    for path in args.skip_file:
        data = json.loads(path.read_text(encoding="utf-8"))
        for row in data.get("done", data) if isinstance(data, dict) else data:
            skip.add(str(row.get("slug") if isinstance(row, dict) else row).lower())
    state = {"platform": args.platform, "done": [], "candidates": []}
    if args.resume and args.out.exists():
        state = json.loads(args.out.read_text(encoding="utf-8"))
    done = set(state["done"])
    todo = [s for s in slugs if s not in done and s.lower() not in skip]
    if args.limit:
        todo = todo[: args.limit]
    print(f"{args.platform}: {len(slugs)} in list, {len(todo)} to sweep", flush=True)

    def save() -> None:
        tmp = args.out.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        tmp.replace(args.out)

    client = PoliteClient()
    errors = 0
    try:
        for i, slug in enumerate(todo, 1):
            try:
                info = sweep_one(client, args.platform, slug)
                if info["tech"] and info["sig"]:
                    state["candidates"].append(info)
            except (NotFound, Disallowed):
                pass
            except SourceBlocked as exc:
                print(f"blocked, stopping politely: {exc}", flush=True)
                break
            except SourceFailed:
                errors += 1
                if errors >= 25 and errors * 3 > i:
                    print("too many failures, stopping", flush=True)
                    break
                time.sleep(2)
                continue
            state["done"].append(slug)
            if i % SAVE_EVERY == 0:
                save()
                print(f"{i}/{len(todo)} swept, {len(state['candidates'])} candidates", flush=True)
    finally:
        save()
        client.close()
    print(f"done: {len(state['done'])} swept in total, {len(state['candidates'])} candidates -> {args.out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
