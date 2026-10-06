#!/usr/bin/env python3
"""Build skill_dictionary v1 seed from the curated techstack list + job frequencies.

Phase 0 of the CV/AI plan: formalize the existing tech_stack vocabulary before
parser / matching work. Does not change the live schema yet.

Usage (from repo root):
  python3 scripts/export_skill_dictionary.py
  python3 scripts/export_skill_dictionary.py --db worker/data/jobs.sqlite
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKER_DIR = ROOT / "worker"
OUT_DIR = ROOT / "docs" / "cv-ai"
# Packaged copy used by the worker image (Docker context is worker/).
PACKAGED_SEED = WORKER_DIR / "worker" / "skill_dictionary_v1.json"
ACADEMY_COURSE_MAP = OUT_DIR / "academy-course-skill-map-v1.json"


def load_academy_course_map(path: Path | None = None) -> dict[str, list[str]]:
    """canonical_name → ordered Academy training slugs (manual map)."""
    chosen = path or ACADEMY_COURSE_MAP
    if not chosen.is_file():
        return {}
    data = json.loads(chosen.read_text(encoding="utf-8"))
    raw = data.get("skills") if isinstance(data, dict) else None
    if not isinstance(raw, dict):
        return {}
    out: dict[str, list[str]] = {}
    for name, courses in raw.items():
        key = str(name or "").strip()
        if not key or not isinstance(courses, list):
            continue
        cleaned = []
        seen: set[str] = set()
        for item in courses:
            slug = str(item or "").strip().strip("/")
            if not slug or slug in seen:
                continue
            seen.add(slug)
            cleaned.append(slug)
        if cleaned:
            out[key] = cleaned
    return out


def apply_academy_course_map(
    skills: list[dict], mapping: dict[str, list[str]] | None = None
) -> int:
    """Fill academy_course_ids from the manual map. Returns skills updated."""
    course_map = mapping if mapping is not None else load_academy_course_map()
    updated = 0
    for row in skills:
        name = str(row.get("canonical_name") or "").strip()
        courses = list(course_map.get(name) or [])
        prev = row.get("academy_course_ids") or []
        if not isinstance(prev, list):
            prev = []
        if courses != [str(x) for x in prev]:
            updated += 1
        row["academy_course_ids"] = courses
    return updated

def _load_tech_entries() -> list[tuple[str, tuple[str, ...], str]]:
    sys.path.insert(0, str(WORKER_DIR))
    from worker.techstack import _TECH  # noqa: WPS433

    return [(name, aliases, cat) for name, _pattern, aliases, cat in _TECH]


def _job_skill_counts(db_path: Path) -> tuple[int, int, Counter[str]]:
    if not db_path.is_file():
        return 0, 0, Counter()

    conn = sqlite3.connect(db_path)
    try:
        total_jobs = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        rows = conn.execute(
            """
            SELECT tech_stack FROM jobs
            WHERE COALESCE(tech_stack, '') NOT IN ('', '[]')
            """
        ).fetchall()
    finally:
        conn.close()

    counts: Counter[str] = Counter()
    for (raw,) in rows:
        try:
            items = json.loads(raw) if isinstance(raw, str) else []
        except json.JSONDecodeError:
            items = []
        if not isinstance(items, list):
            continue
        for item in items:
            if isinstance(item, str) and item.strip():
                counts[item.strip()] += 1
    return int(total_jobs), len(rows), counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db",
        type=Path,
        default=ROOT / "worker" / "data" / "jobs.sqlite",
        help="Path to jobs SQLite database",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=OUT_DIR,
        help="Directory for JSON outputs",
    )
    args = parser.parse_args()

    entries = _load_tech_entries()
    total_jobs, jobs_with_stack, freq = _job_skill_counts(args.db)
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    skills = []
    for name, aliases, category in entries:
        synonym_set = {name.lower(), *(a.lower() for a in aliases)}
        # Keep synonyms distinct from the canonical display name.
        synonyms = sorted(s for s in synonym_set if s != name.lower())
        skills.append(
            {
                "canonical_name": name,
                "synonyms": synonyms,
                "category_hint": category or "other",
                "ad_count": int(freq.get(name, 0)),
                "academy_course_ids": [],
            }
        )

    skills.sort(key=lambda row: (-row["ad_count"], row["canonical_name"].lower()))
    mapped = apply_academy_course_map(skills)

    unknown_in_ads = sorted(
        name for name in freq if name not in {s["canonical_name"] for s in skills}
    )

    dictionary = {
        "version": "1.0",
        "generated_at": generated_at,
        "source": {
            "techstack_module": "worker/worker/techstack.py",
            "jobs_db": str(args.db.relative_to(ROOT)) if args.db.is_relative_to(ROOT) else str(args.db),
            "total_jobs": total_jobs,
            "jobs_with_tech_stack": jobs_with_stack,
            "unique_skills_in_ads": len(freq),
            "dictionary_size": len(skills),
        },
        "skills": skills,
        "notes": [
            "Seed for skill_dictionary table (Phase 0).",
            "canonical_name + synonyms come from the existing curated extractor.",
            "ad_count is a local snapshot from jobs.tech_stack; re-run this script to refresh.",
            "academy_course_ids merged from docs/cv-ai/academy-course-skill-map-v1.json.",
            "Unknown tech_stack values (not in the curated list) are listed under unknown_in_ads.",
            "Worker loads the packaged copy at worker/worker/skill_dictionary_v1.json.",
        ],
        "unknown_in_ads": [
            {"name": name, "ad_count": int(freq[name])} for name in unknown_in_ads
        ],
    }

    frequency = {
        "version": "1.0",
        "generated_at": generated_at,
        "total_jobs": total_jobs,
        "jobs_with_tech_stack": jobs_with_stack,
        "skills": [
            {"name": name, "ad_count": count}
            for name, count in freq.most_common()
        ],
    }

    args.out_dir.mkdir(parents=True, exist_ok=True)
    dict_path = args.out_dir / "skill-dictionary-v1.json"
    freq_path = args.out_dir / "skill-frequency-snapshot.json"
    payload = json.dumps(dictionary, ensure_ascii=False, indent=2) + "\n"
    dict_path.write_text(payload, encoding="utf-8")
    PACKAGED_SEED.parent.mkdir(parents=True, exist_ok=True)
    PACKAGED_SEED.write_text(payload, encoding="utf-8")
    freq_path.write_text(json.dumps(frequency, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"wrote {dict_path.relative_to(ROOT)} ({len(skills)} skills)")
    print(f"wrote {PACKAGED_SEED.relative_to(ROOT)}")
    print(f"wrote {freq_path.relative_to(ROOT)} ({len(freq)} observed)")
    print(f"academy course map: {mapped} skills with courses")
    if unknown_in_ads:
        print(f"warning: {len(unknown_in_ads)} tech_stack values not in curated list")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
