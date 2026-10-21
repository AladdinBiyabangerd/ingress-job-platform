"""Real-data eval for the market-fit staff % (``python -m worker eval-market-fit``).

Fixtures: ``worker/tests/fixtures/market_fit/eval_real_ads.json`` — real scraped ads,
hand-labelled from the ad text only:

* ``eligible``      — remote from Azerbaijan is clearly allowed; must reach 85+.
* ``manual``        — a real relocation + visa route; the policy keeps it for a human
                      check, so it must land in 60–84 (not auto-approved, not dropped).
* ``not_eligible``  — no route for an Azerbaijan resident; must stay below 85.
* ``unclear``       — the text does not settle it; must stay below 85.
* ``truncated``     — ad cut by ``prompt_ad_text`` (``prompt_limit``); must stay below 85.

``flags`` holds only the flags the label is sure about (per-flag accuracy is
measured on those).

Modes:

* offline (default): the labelled flags go through ``fit_mapping.staff_percent`` and the
  ``eligibility`` cap — checks the mapping + rules, no AI call.
* ``--replay FILE``: re-score AI answers saved by an earlier ``--live --save FILE`` run
  through the current validation + mapping (no AI call).
* ``--live``: call the AI (keys from the environment, normal gateway budget; answers are
  cached in a scratch sqlite, never the jobs DB) and report false positives (wrongly
  85+), false negatives, and per-flag accuracy.
"""

from __future__ import annotations

import json
import sqlite3
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

from worker import market_fit as mf
from worker.eligibility import APPROVE_BAND, assess, is_hard_reject
from worker.fit_mapping import FLAGS, staff_percent

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "market_fit" / "eval_real_ads.json"
MANUAL_MIN = 60
USAGE = (
    "usage: python -m worker eval-market-fit [--live] [--limit N] [--only KEY,KEY] "
    "[--save FILE] [--replay FILE] [--cache FILE] [--fixtures FILE] [--quiet]"
)


def load_fixtures(path: Path | None = None) -> list[dict[str, Any]]:
    data = json.loads(Path(path or FIXTURES).read_text(encoding="utf-8"))
    return list(data["ads"])


def outcome(expected: str, score: int) -> str:
    """ok / FP (wrongly 85+) / FN (eligible below 85, or manual route dropped)."""
    if expected == "eligible":
        return "ok" if score >= APPROVE_BAND else "FN"
    if score >= APPROVE_BAND:
        return "FP"
    if expected == "manual" and score < MANUAL_MIN:
        return "FN"
    return "ok"


def _elig(ad: dict[str, Any]) -> dict[str, Any]:
    return assess(
        ad["title"],
        ad.get("city") or "",
        ad["text"],
        source_remote=bool(ad.get("source_remote")) or None,
        source_url=ad.get("source_url") or "",
        source=ad.get("source") or "",
    )


def offline_score(ad: dict[str, Any]) -> dict[str, Any]:
    """Labelled flags -> mapping -> eligibility cap (what a perfect AI answer would get)."""
    elig = _elig(ad)
    flags = dict(ad.get("flags") or {})
    _, truncated = mf.prompt_ad_text(ad["text"], int(ad.get("prompt_limit") or mf.PROMPT_TEXT_MAX))
    flags["text_truncated"] = truncated
    score, route = staff_percent(flags)
    cap = int(elig["cap"])
    if is_hard_reject(elig):
        score, route = cap, "eligibility_reject"
    return {"score": min(score, cap), "route": route, "cap": cap, "flags": flags}


def _verdict_score(ad: dict[str, Any], verdict: dict[str, Any], elig: dict[str, Any]) -> dict[str, Any]:
    cap = int(elig["cap"])
    return {
        "score": min(int(verdict.get("confidence") or 0), cap),
        "route": verdict.get("route") or ("eligibility_reject" if verdict.get("hard_reject") else ""),
        "cap": cap,
        "flags": verdict.get("flags") or {},
        "notes": verdict.get("validation_notes") or [],
        "reason": verdict.get("reason") or "",
    }


def replay_score(ad: dict[str, Any], raw: dict[str, Any] | None) -> dict[str, Any] | None:
    elig = _elig(ad)
    if is_hard_reject(elig):
        return {"score": int(elig["cap"]), "route": "eligibility_reject", "cap": int(elig["cap"]), "flags": {}, "notes": []}
    if not isinstance(raw, dict):
        return None
    _, truncated = mf.prompt_ad_text(ad["text"], int(ad.get("prompt_limit") or mf.PROMPT_TEXT_MAX))
    verdict = mf.verdict_from_ai(
        raw, ad_text=f"{ad['title']}\n{ad.get('city') or ''}\n{ad['text']}", truncated=truncated
    )
    return _verdict_score(ad, verdict, elig)


def live_score(ad: dict[str, Any], conn: sqlite3.Connection) -> tuple[dict[str, Any] | None, dict | None]:
    """One real market-fit check (same path as staff rechecks). Returns (score, raw AI JSON)."""
    captured: dict[str, Any] = {}
    original = mf.complete_json

    def _capture(**kwargs):
        result = original(**kwargs)
        if result.ok and isinstance(result.data, dict):
            captured["raw"] = result.data
        return result

    mf.complete_json = _capture
    try:
        verdict = mf.checked_verdict(
            title=ad["title"],
            company=ad.get("company") or "",
            place=ad.get("city") or "",
            text=ad["text"],
            conn=conn,
            source_url=ad.get("source_url") or "",
            source_remote=bool(ad.get("source_remote")) or None,
            source_relocation=bool(ad.get("source_relocation")) or None,
            source=ad.get("source") or "",
            prompt_limit=int(ad.get("prompt_limit") or mf.PROMPT_TEXT_MAX),
        )
    finally:
        mf.complete_json = original
    if verdict is None:
        return None, None
    return _verdict_score(ad, verdict, _elig(ad)), captured.get("raw")


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    scored = [r for r in rows if r.get("result")]
    counts = Counter(r["outcome"] for r in scored)
    per_flag: dict[str, list[int]] = {}
    for r in scored:
        got = r["result"].get("flags") or {}
        for name, want in (r["ad"].get("flags") or {}).items():
            if name not in FLAGS or not got and r["result"].get("route") == "eligibility_reject":
                continue
            hit = per_flag.setdefault(name, [0, 0])
            hit[1] += 1
            hit[0] += int(bool(got.get(name)) == bool(want))
    by_label: dict[str, Counter] = {}
    for r in scored:
        by_label.setdefault(r["ad"]["expected"], Counter())[r["outcome"]] += 1
    return {
        "total": len(rows),
        "scored": len(scored),
        "failed": len(rows) - len(scored),
        "ok": counts.get("ok", 0),
        "false_positives": counts.get("FP", 0),
        "false_negatives": counts.get("FN", 0),
        "by_label": {k: dict(v) for k, v in sorted(by_label.items())},
        "per_flag": {k: {"correct": v[0], "labelled": v[1], "accuracy": round(v[0] / v[1], 3)}
                     for k, v in sorted(per_flag.items())},
    }


def run(args: list[str]) -> int:
    opts: dict[str, Any] = {"live": False, "limit": 0, "only": set(), "save": "", "replay": "",
                            "cache": "", "fixtures": "", "quiet": False}
    it = iter(args)
    for arg in it:
        if arg == "--live":
            opts["live"] = True
        elif arg == "--quiet":
            opts["quiet"] = True
        elif arg in {"--limit", "--only", "--save", "--replay", "--cache", "--fixtures"}:
            value = next(it, "")
            if not value:
                print(USAGE, flush=True)
                return 2
            if arg == "--limit":
                opts["limit"] = int(value)
            elif arg == "--only":
                opts["only"] = {v.strip() for v in value.split(",") if v.strip()}
            else:
                opts[arg[2:]] = value
        else:
            print(USAGE, flush=True)
            return 2
    ads = load_fixtures(Path(opts["fixtures"]) if opts["fixtures"] else None)
    if opts["only"]:
        ads = [a for a in ads if a["key"] in opts["only"] or str(a["job_id"]) in opts["only"]]
    if opts["limit"]:
        ads = ads[: opts["limit"]]

    mode = "live" if opts["live"] else ("replay" if opts["replay"] else "offline")
    replay = json.loads(Path(opts["replay"]).read_text(encoding="utf-8")) if opts["replay"] else {}
    conn = None
    tmp = None
    if opts["live"]:
        from worker.ai_gateway.gateway import any_provider_key

        if not any_provider_key():
            print("eval-market-fit: no AI provider key in the environment; --live needs one.", flush=True)
            return 2
        if opts["cache"]:
            cache_path = Path(opts["cache"])
        else:
            tmp = tempfile.TemporaryDirectory()
            cache_path = Path(tmp.name) / "eval-cache.sqlite"
        conn = sqlite3.connect(cache_path)
        conn.row_factory = sqlite3.Row

    rows: list[dict[str, Any]] = []
    saved: dict[str, Any] = {}
    try:
        for ad in ads:
            raw = None
            if mode == "live":
                result, raw = live_score(ad, conn)
                if result is None:
                    print(f"  {ad['key']:<14} AI miss: {mf.last_miss_error}", flush=True)
                    if mf.last_miss_error in {"ai_budget_exceeded", "ai_disabled", "market_fit_off"}:
                        rows.append({"ad": ad, "result": None, "outcome": "fail"})
                        break
            elif mode == "replay":
                result = replay_score(ad, (replay.get("answers") or {}).get(ad["key"]))
            else:
                result = offline_score(ad)
            if raw is not None:
                saved[ad["key"]] = raw
            row = {"ad": ad, "result": result, "outcome": outcome(ad["expected"], result["score"]) if result else "fail"}
            rows.append(row)
            if result and not opts["quiet"]:
                wrong = [n for n, w in (ad.get("flags") or {}).items()
                         if result.get("flags") and bool(result["flags"].get(n)) != bool(w)]
                print(
                    f"  {ad['key']:<14} {ad['expected']:<12} {result['score']:>3}% cap {result['cap']:>3} "
                    f"{row['outcome']:<3} {result['route']:<26} {ad['company'][:18]:<18} {ad['title'][:40]}"
                    + (f"  flags≠label: {','.join(wrong)}" if wrong else ""),
                    flush=True,
                )
                for note in result.get("notes") or []:
                    print(f"      quote rejected: {note[:150]}", flush=True)
    finally:
        if conn is not None:
            conn.close()
        if tmp is not None:
            tmp.cleanup()

    stats = summarize(rows)
    if opts["save"] and saved:
        Path(opts["save"]).write_text(
            json.dumps({"prompt_version": mf.PROMPT_VERSION, "answers": saved}, ensure_ascii=False, indent=1),
            encoding="utf-8",
        )
    print(f"eval-market-fit [{mode}] {mf.PROMPT_VERSION}: " + json.dumps(
        {k: v for k, v in stats.items() if k not in {"per_flag", "by_label"}}), flush=True)
    print("  by label: " + json.dumps(stats["by_label"]), flush=True)
    for name, acc in stats["per_flag"].items():
        print(f"  flag {name:<30} {acc['correct']:>3}/{acc['labelled']:<3} {acc['accuracy']:.0%}", flush=True)
    fps = [r["ad"]["key"] for r in rows if r["outcome"] == "FP"]
    fns = [r["ad"]["key"] for r in rows if r["outcome"] == "FN"]
    if fps:
        print("  false positives (wrongly 85+): " + ", ".join(fps), flush=True)
    if fns:
        print("  false negatives: " + ", ".join(fns), flush=True)
    return 0
