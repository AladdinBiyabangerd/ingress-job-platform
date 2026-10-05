"""skill_dictionary + job_skill tables (Phase 0.2).

Deterministic only: seed from the packaged JSON (export of techstack.py),
backfill job_skill from jobs.tech_stack. No AI.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS skill_dictionary (
    id INTEGER PRIMARY KEY,
    canonical_name TEXT NOT NULL UNIQUE,
    synonyms TEXT NOT NULL DEFAULT '[]',
    category_hint TEXT NOT NULL DEFAULT '',
    academy_course_ids TEXT NOT NULL DEFAULT '[]',
    updated_at TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS job_skill (
    job_id INTEGER NOT NULL REFERENCES jobs(id),
    skill_id INTEGER NOT NULL REFERENCES skill_dictionary(id),
    source TEXT NOT NULL DEFAULT 'tech_stack',
    PRIMARY KEY (job_id, skill_id)
);
"""

INDEXES = (
    "CREATE INDEX IF NOT EXISTS job_skill_skill ON job_skill(skill_id)",
    "CREATE INDEX IF NOT EXISTS job_skill_job ON job_skill(job_id)",
)

BACKFILL_STEP = "backfill-job-skill-from-tech-stack-v1"

_MAINTENANCE = """
CREATE TABLE IF NOT EXISTS maintenance_steps (
    name TEXT PRIMARY KEY,
    done_at TEXT NOT NULL
)
"""


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def seed_path() -> Path:
    """Packaged copy ships with the worker image; docs/ is the editable source."""
    packaged = Path(__file__).with_name("skill_dictionary_v1.json")
    if packaged.is_file():
        return packaged
    return (
        Path(__file__).resolve().parents[2]
        / "docs"
        / "cv-ai"
        / "skill-dictionary-v1.json"
    )


def ensure_skill_tables(conn) -> None:
    conn.executescript(SCHEMA)
    for sql in INDEXES:
        conn.execute(sql)


def load_seed(path: Path | None = None) -> list[dict]:
    chosen = path or seed_path()
    data = json.loads(chosen.read_text(encoding="utf-8"))
    skills = data.get("skills") if isinstance(data, dict) else None
    if not isinstance(skills, list):
        raise ValueError(f"invalid skill dictionary seed: {chosen}")
    return skills


def seed_skill_dictionary(conn, path: Path | None = None) -> int:
    """Upsert canonical skills from the v1 JSON. Returns row count written."""
    ensure_skill_tables(conn)
    skills = load_seed(path)
    stamp = _now()
    sql = """
        INSERT INTO skill_dictionary (
            canonical_name, synonyms, category_hint, academy_course_ids, updated_at
        ) VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(canonical_name) DO UPDATE SET
            synonyms = excluded.synonyms,
            category_hint = excluded.category_hint,
            academy_course_ids = excluded.academy_course_ids,
            updated_at = excluded.updated_at
    """
    rows = []
    for item in skills:
        name = str(item.get("canonical_name") or "").strip()
        if not name:
            continue
        synonyms = item.get("synonyms") or []
        if not isinstance(synonyms, list):
            synonyms = []
        courses = item.get("academy_course_ids") or []
        if not isinstance(courses, list):
            courses = []
        rows.append(
            (
                name,
                json.dumps([str(x) for x in synonyms], ensure_ascii=False),
                str(item.get("category_hint") or "")[:40],
                json.dumps([str(x) for x in courses], ensure_ascii=False),
                stamp,
            )
        )
    if rows:
        conn.executemany(sql, rows)
    return len(rows)


def _skill_id_map(conn) -> dict[str, int]:
    """canonical_name (exact) and lower-case alias → skill_id."""
    mapping: dict[str, int] = {}
    for row in conn.execute(
        "SELECT id, canonical_name, synonyms FROM skill_dictionary"
    ):
        skill_id = int(row[0] if not hasattr(row, "keys") else row["id"])
        name = str(row[1] if not hasattr(row, "keys") else row["canonical_name"])
        raw_syn = row[2] if not hasattr(row, "keys") else row["synonyms"]
        mapping[name] = skill_id
        mapping[name.lower()] = skill_id
        try:
            synonyms = json.loads(raw_syn) if raw_syn else []
        except (TypeError, ValueError, json.JSONDecodeError):
            synonyms = []
        if isinstance(synonyms, list):
            for syn in synonyms:
                key = str(syn).strip().lower()
                if key:
                    mapping[key] = skill_id
    return mapping


def _parse_stack(raw: object) -> list[str]:
    if raw is None or raw == "":
        return []
    if isinstance(raw, list):
        items = raw
    else:
        try:
            items = json.loads(raw) if isinstance(raw, str) else []
        except (TypeError, ValueError, json.JSONDecodeError):
            return []
    if not isinstance(items, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, str):
            continue
        name = item.strip()
        if not name or name in seen:
            continue
        seen.add(name)
        out.append(name)
    return out


def sync_job_skills(
    conn,
    job_id: int,
    stack: object,
    *,
    source: str = "tech_stack",
    skill_map: dict[str, int] | None = None,
) -> int:
    """Replace job_skill rows for one job from a tech_stack list. Returns links written."""
    ensure_skill_tables(conn)
    mapping = skill_map if skill_map is not None else _skill_id_map(conn)
    names = _parse_stack(stack)
    skill_ids: list[int] = []
    seen_ids: set[int] = set()
    for name in names:
        skill_id = mapping.get(name) or mapping.get(name.lower())
        if skill_id is None or skill_id in seen_ids:
            continue
        seen_ids.add(skill_id)
        skill_ids.append(skill_id)
    conn.execute(
        "DELETE FROM job_skill WHERE job_id = ? AND source = ?",
        (job_id, source),
    )
    if skill_ids:
        conn.executemany(
            """
            INSERT INTO job_skill (job_id, skill_id, source)
            VALUES (?, ?, ?)
            ON CONFLICT(job_id, skill_id) DO UPDATE SET source = excluded.source
            """,
            [(job_id, skill_id, source) for skill_id in skill_ids],
        )
    return len(skill_ids)


def backfill_job_skills(conn, *, force: bool = False) -> int:
    """One-time (unless force) link of jobs.tech_stack → job_skill.

    Returns number of job rows processed. Unknown stack values are skipped.
    """
    ensure_skill_tables(conn)
    conn.execute(_MAINTENANCE)
    if not force:
        done = conn.execute(
            "SELECT 1 FROM maintenance_steps WHERE name = ?", (BACKFILL_STEP,)
        ).fetchone()
        if done:
            return 0

    mapping = _skill_id_map(conn)
    if not mapping:
        return 0

    rows = conn.execute(
        """
        SELECT id, COALESCE(tech_stack, '') AS tech_stack
        FROM jobs
        WHERE COALESCE(tech_stack, '') NOT IN ('', '[]')
        """
    ).fetchall()

    processed = 0
    for row in rows:
        job_id = int(row[0] if not hasattr(row, "keys") else row["id"])
        stack = row[1] if not hasattr(row, "keys") else row["tech_stack"]
        sync_job_skills(conn, job_id, stack, skill_map=mapping)
        processed += 1

    conn.execute(
        "INSERT INTO maintenance_steps (name, done_at) VALUES (?, ?) "
        "ON CONFLICT (name) DO NOTHING",
        (BACKFILL_STEP, _now()),
    )
    return processed


def ensure_skills(conn, path: Path | None = None) -> tuple[int, int]:
    """Create tables, seed dictionary, run one-time backfill. Returns (seeded, backfilled)."""
    seeded = seed_skill_dictionary(conn, path)
    backfilled = backfill_job_skills(conn)
    return seeded, backfilled
