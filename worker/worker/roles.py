"""role_taxonomy + role_skill_weight tables (Phase 0.3).

Deterministic only: seed from the packaged JSON under existing job categories.
Signature skills link to skill_dictionary by canonical name. No AI.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from worker.techstack import CATEGORIES

SCHEMA = """
CREATE TABLE IF NOT EXISTS role_taxonomy (
    id INTEGER PRIMARY KEY,
    canonical_name TEXT NOT NULL UNIQUE,
    category TEXT NOT NULL,
    synonyms TEXT NOT NULL DEFAULT '[]',
    updated_at TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS role_skill_weight (
    role_id INTEGER NOT NULL REFERENCES role_taxonomy(id),
    skill_id INTEGER NOT NULL REFERENCES skill_dictionary(id),
    weight REAL NOT NULL,
    PRIMARY KEY (role_id, skill_id)
);
"""

INDEXES = (
    "CREATE INDEX IF NOT EXISTS role_taxonomy_category ON role_taxonomy(category)",
    "CREATE INDEX IF NOT EXISTS role_skill_weight_skill ON role_skill_weight(skill_id)",
)

_KNOWN_CATEGORIES = frozenset(CATEGORIES)


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def seed_path() -> Path:
    """Packaged copy ships with the worker image; docs/ is the editable source."""
    packaged = Path(__file__).with_name("role_taxonomy_v1.json")
    if packaged.is_file():
        return packaged
    return (
        Path(__file__).resolve().parents[2]
        / "docs"
        / "cv-ai"
        / "role-taxonomy-v1.json"
    )


def ensure_role_tables(conn) -> None:
    conn.executescript(SCHEMA)
    for sql in INDEXES:
        conn.execute(sql)


def load_seed(path: Path | None = None) -> list[dict]:
    chosen = path or seed_path()
    data = json.loads(chosen.read_text(encoding="utf-8"))
    roles = data.get("roles") if isinstance(data, dict) else None
    if not isinstance(roles, list):
        raise ValueError(f"invalid role taxonomy seed: {chosen}")
    return roles


def _skill_ids_by_name(conn) -> dict[str, int]:
    mapping: dict[str, int] = {}
    try:
        rows = conn.execute("SELECT id, canonical_name FROM skill_dictionary")
    except Exception:
        return mapping
    for row in rows:
        skill_id = int(row[0] if not hasattr(row, "keys") else row["id"])
        name = str(row[1] if not hasattr(row, "keys") else row["canonical_name"])
        mapping[name] = skill_id
    return mapping


def seed_role_taxonomy(conn, path: Path | None = None) -> tuple[int, int]:
    """Upsert roles and signature skill weights. Returns (roles_written, weights_written).

    Unknown skill names are skipped. Categories outside techstack.CATEGORIES are skipped.
    """
    ensure_role_tables(conn)
    roles = load_seed(path)
    skill_ids = _skill_ids_by_name(conn)
    stamp = _now()

    role_sql = """
        INSERT INTO role_taxonomy (canonical_name, category, synonyms, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(canonical_name) DO UPDATE SET
            category = excluded.category,
            synonyms = excluded.synonyms,
            updated_at = excluded.updated_at
    """
    roles_written = 0
    weights_written = 0

    for item in roles:
        name = str(item.get("canonical_name") or "").strip()
        category = str(item.get("category") or "").strip()
        if not name or category not in _KNOWN_CATEGORIES:
            continue
        synonyms = item.get("synonyms") or []
        if not isinstance(synonyms, list):
            synonyms = []
        conn.execute(
            role_sql,
            (
                name,
                category,
                json.dumps([str(x) for x in synonyms], ensure_ascii=False),
                stamp,
            ),
        )
        roles_written += 1

        row = conn.execute(
            "SELECT id FROM role_taxonomy WHERE canonical_name = ?", (name,)
        ).fetchone()
        if row is None:
            continue
        role_id = int(row[0] if not hasattr(row, "keys") else row["id"])

        # Replace weights for this role so seed edits drop removed skills.
        conn.execute("DELETE FROM role_skill_weight WHERE role_id = ?", (role_id,))
        sigs = item.get("signature_skills") or []
        if not isinstance(sigs, list):
            continue
        seen: set[int] = set()
        for sig in sigs:
            if not isinstance(sig, dict):
                continue
            skill_name = str(sig.get("skill") or "").strip()
            skill_id = skill_ids.get(skill_name)
            if skill_id is None or skill_id in seen:
                continue
            try:
                weight = float(sig.get("weight"))
            except (TypeError, ValueError):
                continue
            if weight <= 0:
                continue
            seen.add(skill_id)
            conn.execute(
                """
                INSERT INTO role_skill_weight (role_id, skill_id, weight)
                VALUES (?, ?, ?)
                """,
                (role_id, skill_id, weight),
            )
            weights_written += 1

    return roles_written, weights_written


def ensure_roles(conn, path: Path | None = None) -> tuple[int, int]:
    """Create tables and seed taxonomy. Returns (roles_written, weights_written)."""
    return seed_role_taxonomy(conn, path)
