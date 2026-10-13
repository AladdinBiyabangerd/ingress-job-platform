"""Job categories from the job_categories table (worker/worker/categories.py).

Public: active list (cached ~30 s). Staff: create / edit / reorder /
deactivate and a recategorise pass that only rewrites jobs.category.
"""

from __future__ import annotations

import json
import re
import threading
import time

from app.sqlite_jobs import _ensure_worker_path

_ensure_worker_path()
from worker import categories as wcat  # noqa: E402

OTHER = wcat.OTHER
_TTL = 30.0
_LOCK = threading.Lock()
_CACHE: tuple[float, tuple, list[dict]] | None = None  # (loaded_at, signature, rows)
_SLUG = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 /&+.\-]{0,39}$")


class CategoryError(Exception):
    def __init__(self, status: int, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.detail = detail


def _rw_conn():
    from app.cabinet_store import _connect

    conn = _connect()
    wcat.ensure_categories(conn)
    conn.commit()
    return conn


def _load_rows() -> list[dict]:
    try:
        conn = _rw_conn()
    except Exception:  # noqa: BLE001 - no database yet: built-in seed
        return [dict(i) for i in wcat.SEED]
    try:
        rows = wcat.read_categories(conn)
    finally:
        conn.close()
    return rows or [dict(i) for i in wcat.SEED]


def invalidate() -> None:
    global _CACHE
    with _LOCK:
        _CACHE = None


def all_rows() -> list[dict]:
    global _CACHE
    now = time.monotonic()
    with _LOCK:
        cached = _CACHE
    if cached is not None and now - cached[0] < _TTL:
        return cached[2]
    rows = _load_rows()
    sig = tuple(json.dumps(r, sort_keys=True, ensure_ascii=False) for r in rows)
    with _LOCK:
        _CACHE = (now, sig, rows)
    wcat.set_rules(rows)
    return rows


def version() -> int:
    """Changes whenever the category rows change (facet memo key)."""
    all_rows()
    with _LOCK:
        return hash(_CACHE[1]) if _CACHE else 0


def active_rows() -> list[dict]:
    rows = [r for r in all_rows() if r["active"]]
    rows.sort(key=lambda r: (r["sort_order"], r["slug"]))
    return rows


def active_slugs() -> tuple[str, ...]:
    return tuple(r["slug"] for r in active_rows())


def labels(row: dict) -> dict:
    return {"az": row["name_az"], "en": row["name_en"], "ru": row["name_ru"]}


def public_item(row: dict, total: int = 0) -> dict:
    return {"name": row["slug"], "slug": row["slug"], "labels": labels(row),
            "sort_order": row["sort_order"], "total": int(total)}


def display_category(value: object) -> str:
    """Stored value → active slug; inactive known slugs show as Other tech."""
    name = str(value or "").strip()
    if not name or name == "-":
        return ""
    if name in active_slugs():
        return name
    if any(r["slug"] == name for r in all_rows()):
        return OTHER
    return ""


# ---- staff ---------------------------------------------------------------

_FIELDS = ("name_az", "name_en", "name_ru", "sort_order", "priority", "stack_rank",
           "active", "title_pattern", "aliases", "stack_names")


def _clean_list(value, limit: int = 200) -> list[str]:
    out: list[str] = []
    for item in value or []:
        text = str(item or "").strip()[:80]
        if text and text not in out:
            out.append(text)
    return out[:limit]


def _validated(fields: dict) -> dict:
    out: dict = {}
    for key in _FIELDS:
        if key not in fields or fields[key] is None:
            continue
        value = fields[key]
        if key.startswith("name_"):
            value = str(value).strip()[:60]
            if not value:
                raise CategoryError(422, "Ad boş ola bilməz")
        elif key in {"sort_order", "priority", "stack_rank"}:
            value = max(0, min(100000, int(value)))
        elif key == "active":
            value = 1 if value else 0
        elif key == "title_pattern":
            value = str(value).strip()[:2000]
            err = wcat.validate_pattern(value)
            if err:
                raise CategoryError(422, f"Regex səhvdir: {err}")
        else:
            value = json.dumps(_clean_list(value), ensure_ascii=False)
        out[key] = value
    return out


def staff_list() -> list[dict]:
    invalidate()
    rows = all_rows()
    counts = _counts()
    return [{**r, "total": counts.get(r["slug"], 0)} for r in rows]


def _counts() -> dict[str, int]:
    try:
        conn = _rw_conn()
    except Exception:  # noqa: BLE001
        return {}
    try:
        return {
            str(row[0]): int(row[1])
            for row in conn.execute(
                """
                SELECT category, COUNT(*) FROM jobs
                WHERE status = 'published' AND COALESCE(hidden, 0) = 0 AND merged_into IS NULL
                GROUP BY category
                """
            ).fetchall()
        }
    finally:
        conn.close()


def create(slug: str, fields: dict) -> dict:
    slug = str(slug or "").strip()
    if not _SLUG.match(slug) or slug == "-":
        raise CategoryError(422, "Açar (slug) 1–40 simvol: hərf, rəqəm, boşluq, / & + . -")
    clean = _validated(fields)
    for key in ("name_az", "name_en", "name_ru"):
        clean.setdefault(key, slug)
    conn = _rw_conn()
    try:
        if conn.execute("SELECT 1 FROM job_categories WHERE slug = ?", (slug,)).fetchone():
            raise CategoryError(409, "Bu açar artıq var")
        item = {
            "slug": slug, "sort_order": 500, "priority": 500, "stack_rank": 500, "active": 1,
            "title_pattern": "", "aliases": [], "stack_names": [],
            **{k: (json.loads(v) if k in {"aliases", "stack_names"} else v) for k, v in clean.items()},
        }
        wcat.ensure_categories(conn, [item])
        conn.commit()
    finally:
        conn.close()
    invalidate()
    return next(r for r in staff_list() if r["slug"] == slug)


def update(slug: str, fields: dict) -> dict:
    clean = _validated(fields)
    if slug == OTHER and clean.get("active") == 0:
        raise CategoryError(422, "\"Other tech\" söndürülə bilməz")
    conn = _rw_conn()
    try:
        if not conn.execute("SELECT 1 FROM job_categories WHERE slug = ?", (slug,)).fetchone():
            raise CategoryError(404, "Kateqoriya tapılmadı")
        if clean:
            sets = ", ".join(f"{k} = ?" for k in clean) + ", updated_at = ?"
            conn.execute(
                f"UPDATE job_categories SET {sets} WHERE slug = ?",
                [*clean.values(), wcat._now(), slug],
            )
            conn.commit()
    finally:
        conn.close()
    invalidate()
    if clean.get("active") == 0:
        recategorise(only=slug)
    return next(r for r in staff_list() if r["slug"] == slug)


def reorder(slugs: list[str]) -> list[dict]:
    conn = _rw_conn()
    try:
        for index, slug in enumerate(slugs):
            conn.execute(
                "UPDATE job_categories SET sort_order = ?, updated_at = ? WHERE slug = ?",
                ((index + 1) * 10, wcat._now(), str(slug)),
            )
        conn.commit()
    finally:
        conn.close()
    invalidate()
    return staff_list()


def recategorise(only: str | None = None) -> dict:
    """Re-run classification on collected rows with the current table rules.

    Only jobs.category is written (status, hidden, updated_at untouched).
    The source board's category is not stored, so a row is changed only when
    the current rules give a different answer than the built-in 12 rules
    would for the same title/stack (i.e. the change comes from a category
    edit), or when its stored category is inactive/unknown.
    """
    from worker.techstack import classify_category

    invalidate()
    current = wcat.set_rules(all_rows())
    base = wcat.Rules(wcat.BASE_SEED)
    base_slugs = set(base.slugs)
    conn = _rw_conn()
    scanned = changed = 0
    moves: dict[str, int] = {}
    try:
        sql = """
            SELECT id, title, COALESCE(tech_stack, '') AS tech_stack, COALESCE(category, '') AS category
            FROM jobs WHERE COALESCE(owner_subject, '') = '' AND COALESCE(category, '') NOT IN ('', '-')
        """
        params: list = []
        if only:
            sql += " AND category = ?"
            params.append(only)
        for row in conn.execute(sql, params).fetchall():
            scanned += 1
            try:
                stack = json.loads(row["tech_stack"] or "[]")
            except (TypeError, ValueError):
                stack = []
            stack = [str(x) for x in stack] if isinstance(stack, list) else []
            title = str(row["title"] or "")
            stored = str(row["category"])
            new = classify_category("", title, stack, rules=current)
            if stored not in current.active or stored not in base_slugs:
                target = new
            else:
                old = classify_category("", title, stack, rules=base)
                target = new if new != old else stored
            if target != stored:
                conn.execute("UPDATE jobs SET category = ? WHERE id = ?", (target, row["id"]))
                changed += 1
                key = f"{stored} → {target}"
                moves[key] = moves.get(key, 0) + 1
        conn.commit()
    finally:
        conn.close()
    from app import sqlite_jobs

    sqlite_jobs._FACETS_MEMO = None
    return {"scanned": scanned, "changed": changed, "moves": moves}
