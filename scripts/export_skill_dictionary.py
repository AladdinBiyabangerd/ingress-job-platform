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

# Mirrors comment groups in worker/worker/techstack.py (_TECH).
_CATEGORY_BY_CANONICAL: dict[str, str] = {
    "Python": "language",
    "Java": "language",
    "Kotlin": "language",
    "Scala": "language",
    "Go": "language",
    "Rust": "language",
    "TypeScript": "language",
    "JavaScript": "language",
    "PHP": "language",
    "Ruby": "language",
    "C#": "language",
    "C++": "language",
    "C": "language",
    ".NET": "language",
    "Swift": "language",
    "Objective-C": "language",
    "Dart": "language",
    "Elixir": "language",
    "Erlang": "language",
    "Haskell": "language",
    "Clojure": "language",
    "Solidity": "language",
    "SQL": "language",
    "Bash": "language",
    "React": "frontend",
    "React Native": "mobile",
    "Next.js": "frontend",
    "Vue.js": "frontend",
    "Nuxt": "frontend",
    "Angular": "frontend",
    "Svelte": "frontend",
    "Redux": "frontend",
    "Tailwind": "frontend",
    "HTML": "frontend",
    "CSS": "frontend",
    "Flutter": "mobile",
    "iOS": "mobile",
    "Android": "mobile",
    "Node.js": "backend",
    "NestJS": "backend",
    "Express": "backend",
    "Django": "backend",
    "Flask": "backend",
    "FastAPI": "backend",
    "Spring": "backend",
    "Ruby on Rails": "backend",
    "Laravel": "backend",
    "Symfony": "backend",
    "Phoenix": "backend",
    "GraphQL": "backend",
    "gRPC": "backend",
    "WordPress": "backend",
    "Shopify": "backend",
    "AWS": "cloud",
    "GCP": "cloud",
    "Azure": "cloud",
    "Kubernetes": "devops",
    "Docker": "devops",
    "Terraform": "devops",
    "Ansible": "devops",
    "Helm": "devops",
    "Linux": "devops",
    "CI/CD": "devops",
    "Jenkins": "devops",
    "GitHub Actions": "devops",
    "Prometheus": "devops",
    "Grafana": "devops",
    "Datadog": "devops",
    "Nginx": "devops",
    "PostgreSQL": "data",
    "MySQL": "data",
    "MongoDB": "data",
    "Redis": "data",
    "Elasticsearch": "data",
    "DynamoDB": "data",
    "Cassandra": "data",
    "ClickHouse": "data",
    "Kafka": "data",
    "RabbitMQ": "data",
    "Spark": "data",
    "Airflow": "data",
    "dbt": "data",
    "Snowflake": "data",
    "BigQuery": "data",
    "Databricks": "data",
    "Pandas": "data",
    "PyTorch": "ml",
    "TensorFlow": "ml",
    "scikit-learn": "ml",
    "LLM": "ml",
    "Selenium": "qa",
    "Cypress": "qa",
    "Playwright": "qa",
    "Jest": "qa",
    "Figma": "design",
    "Unity": "gamedev",
    "Unreal Engine": "gamedev",
    "Ethereum": "web3",
}


def _load_tech_entries() -> list[tuple[str, tuple[str, ...]]]:
    sys.path.insert(0, str(WORKER_DIR))
    from worker.techstack import _TECH  # noqa: WPS433

    return [(name, aliases) for name, _pattern, aliases in _TECH]


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
    for name, aliases in entries:
        synonym_set = {name.lower(), *(a.lower() for a in aliases)}
        # Keep synonyms distinct from the canonical display name.
        synonyms = sorted(s for s in synonym_set if s != name.lower())
        skills.append(
            {
                "canonical_name": name,
                "synonyms": synonyms,
                "category_hint": _CATEGORY_BY_CANONICAL.get(name, "other"),
                "ad_count": int(freq.get(name, 0)),
                "academy_course_ids": [],
            }
        )

    skills.sort(key=lambda row: (-row["ad_count"], row["canonical_name"].lower()))

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
            "Seed for skill_dictionary table (Phase 0). Schema/migration is a later step.",
            "canonical_name + synonyms come from the existing curated extractor.",
            "ad_count is a local snapshot from jobs.tech_stack; re-run this script to refresh.",
            "Unknown tech_stack values (not in the curated list) are listed under unknown_in_ads.",
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
    dict_path.write_text(json.dumps(dictionary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    freq_path.write_text(json.dumps(frequency, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"wrote {dict_path.relative_to(ROOT)} ({len(skills)} skills)")
    print(f"wrote {freq_path.relative_to(ROOT)} ({len(freq)} observed)")
    if unknown_in_ads:
        print(f"warning: {len(unknown_in_ads)} tech_stack values not in curated list")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
