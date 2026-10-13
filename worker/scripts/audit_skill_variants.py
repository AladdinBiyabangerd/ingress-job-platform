"""Audit: are skills missed only because of case / spacing / joined / hyphen / dot forms?

Usage:
  .venv/bin/python scripts/audit_skill_variants.py            # dictionary variant audit
  .venv/bin/python scripts/audit_skill_variants.py --db data/jobs.sqlite --snapshot out.json
Read-only. Prints miss counts and samples; with --snapshot dumps per-job stack and
rule verdicts (is_tech_job / remote / relocation / az_market_relevant) for diffs.
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from worker import techstack as t  # noqa: E402
from worker.techstack_extra import text_alias  # noqa: E402

SENTENCES = (
    "Experience with {v} is required.",
    "Our stack: {v}, Docker and AWS.",
    "- Strong {v} skills",
)


def variants(term: str) -> set[str]:
    """Spelling forms a human would write for the same term."""
    toks = [x for x in re.split(r"[\s\-_.]+", term) if x]
    out = {term, term.lower(), term.upper(), term.title()}
    if len(toks) > 1:
        seps = (" ", "-", "", ".") if "." in term else (" ", "-", "")
        for sep in seps:
            joined = sep.join(toks)
            out |= {joined, joined.lower()}
    m = re.fullmatch(r"(?i)(.+?)[\s.]?js", term)
    if m and len(m.group(1)) >= 2:
        base = m.group(1).rstrip(".")
        out |= {f"{base}.js", f"{base}js", f"{base} js", f"{base}JS", f"{base}.JS".lower()}
    return {v for v in out if v.strip()}


def _bucket(term: str, var: str) -> str:
    if var == term:
        return "exact"
    if re.sub(r"[\s\-_.]", "", var).lower() == re.sub(r"[\s\-_.]", "", term).lower() and var.lower() != term.lower():
        return "separator"
    return "case"


def audit_dictionary(show: int) -> dict:
    misses_text: list[tuple[str, str, str]] = []
    misses_tag: list[tuple[str, str]] = []
    tested = 0
    for name, pattern, extra, cat in t._TECH:
        if pattern.pattern == "(?!)" or "(?!)" in pattern.pattern and len(pattern.pattern) < 40:
            continue
        # free text: the canonical name (if the pattern accepts it as written) + text aliases
        base = []
        if pattern.search(f" {name} ") or any(pattern.search(s.format(v=name)) for s in SENTENCES):
            base.append(name)
        base += [a for a in extra if text_alias(a) and pattern.search(a)]
        for term in base:
            for var in sorted(variants(term)):
                tested += 1
                ok = any(name in t.find_stack(s.format(v=var)) for s in SENTENCES)
                if not ok:
                    misses_text.append((name, var, _bucket(term, var)))
        # tags: every alias + name in any spelling must map back
        for term in {name, *extra}:
            for var in variants(term):
                got = t.stack_from_tags([var])
                if name not in got:
                    misses_tag.append((name, var))
    by_bucket: dict[str, int] = {}
    for _n, _v, b in misses_text:
        by_bucket[b] = by_bucket.get(b, 0) + 1
    print(f"variants tested (text): {tested}")
    print(f"text misses: {len(misses_text)} {by_bucket}  skills affected: {len({n for n, *_ in misses_text})}")
    print(f"tag misses: {len(misses_tag)}  skills affected: {len({n for n, _ in misses_tag})}")
    for row in misses_text[:show]:
        print("  TEXT", row)
    for row in misses_tag[:show]:
        print("  TAG ", row)
    return {"text": misses_text, "tag": misses_tag}


def _rows(db: str):
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    return conn.execute(
        "SELECT id, title, city, COALESCE(NULLIF(cleaned_text,''), text) AS body FROM jobs "
        "WHERE COALESCE(owner_subject,'')='' AND (merged_into IS NULL OR merged_into=0)"
    ).fetchall()


def audit_db(db: str, show: int, snapshot: str | None) -> None:
    rows = _rows(db)
    known = {}
    for name, pattern, extra, cat in t._TECH:
        if cat in t._NON_CHIP:
            continue
        for term in (name, *[a for a in extra if text_alias(a)]):
            if len(term) >= 4 and not re.fullmatch(r"[a-z]+", term.lower()) or len(term) >= 6:
                known.setdefault(term.lower(), name)
    rx = re.compile(r"(?<![A-Za-z0-9])(" + "|".join(sorted(map(re.escape, known), key=len, reverse=True)) + r")(?![A-Za-z0-9])", re.I)
    missing: dict[str, int] = {}
    snap = {}
    for r in rows:
        title, body, place = r["title"] or "", r["body"] or "", r["city"] or ""
        full = t.find_stack(f"{title}\n{body}")
        for m in rx.finditer(f"{title}\n{body}"[:30000]):
            name = known[m.group(1).lower()]
            if name not in full:
                key = f"{name} <- {m.group(1)}"
                missing[key] = missing.get(key, 0) + 1
        if snapshot:
            remote = t.remote_flag(title, place, body)
            reloc = t.relocation_flag(title, place, body)
            snap[r["id"]] = {
                "stack": t.extract_stack(body, None, title),
                "tech": t.is_tech_job(title),
                "remote": remote,
                "reloc": reloc,
                "fo": t.foreign_office_without_offer(title, place, body),
                "az": t.az_market_relevant(title, place, body, remote=remote, relocation=reloc),
            }
    total = sum(missing.values())
    print(f"db jobs: {len(rows)}  term-present-but-not-extracted: {total} ({len(missing)} distinct)")
    for k, v in sorted(missing.items(), key=lambda kv: -kv[1])[:show]:
        print(f"  {v:4d}  {k}")
    if snapshot:
        Path(snapshot).write_text(json.dumps(snap, ensure_ascii=False))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--db")
    ap.add_argument("--snapshot")
    ap.add_argument("--show", type=int, default=40)
    a = ap.parse_args()
    if a.db:
        audit_db(a.db, a.show, a.snapshot)
    else:
        audit_dictionary(a.show)
