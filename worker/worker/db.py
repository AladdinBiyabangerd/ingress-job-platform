"""Jobs store.

SQLite when DATABASE_URL is unset. Postgres, shared with the API, when it is set.
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path

from worker.catalog import SOURCES
from worker.parsing import norm_key

def _db_path() -> Path:
    configured = os.environ.get("JOBS_DB_PATH", "").strip()
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[1] / "data" / "jobs.sqlite"


DB_PATH = _db_path()

SCHEMA = """
CREATE TABLE IF NOT EXISTS crawl_sources (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    homepage TEXT NOT NULL,
    connector TEXT NOT NULL,
    entry_url TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 0,
    min_delay_seconds REAL NOT NULL DEFAULT 1,
    go_decision TEXT NOT NULL DEFAULT 'pending',
    go_decided_by TEXT NOT NULL DEFAULT '',
    go_decided_at TEXT NOT NULL DEFAULT '',
    credit_note TEXT NOT NULL DEFAULT '',
    api_key_env TEXT NOT NULL DEFAULT '',
    note TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS crawl_runs (
    id INTEGER PRIMARY KEY,
    source_id INTEGER NOT NULL REFERENCES crawl_sources(id),
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    found_count INTEGER NOT NULL DEFAULT 0,
    created_count INTEGER NOT NULL DEFAULT 0,
    updated_count INTEGER NOT NULL DEFAULT 0,
    error TEXT
);

CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    company TEXT NOT NULL DEFAULT '',
    city TEXT NOT NULL DEFAULT '',
    text TEXT NOT NULL DEFAULT '',
    cleaned_text TEXT,
    status TEXT NOT NULL DEFAULT 'published',
    created_at TEXT NOT NULL,
    norm_key TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS job_sources (
    id INTEGER PRIMARY KEY,
    job_id INTEGER NOT NULL REFERENCES jobs(id),
    source_name TEXT NOT NULL,
    source_url TEXT NOT NULL UNIQUE,
    external_id TEXT NOT NULL DEFAULT '',
    last_seen TEXT NOT NULL,
    credit_note TEXT NOT NULL DEFAULT ''
);
"""


# One-time maintenance: hide the ads collected from the retired domestic
# sources. Uses the same jobs.hidden flag as the staff "hide" button, so staff
# still see these rows in the collected-ads admin and can unhide them. Rows are
# never deleted. Only collected rows (empty owner_subject) whose every source
# is a retired one are touched; cabinet/company ads and ads also seen on a
# current source are left alone. The marker row in maintenance_steps makes it
# run once per database, so a later unhide by staff is not undone.
# The same step lives in api/app/cabinet_store.py (API schema setup); whichever process opens the database first
# does it.
RETIRED_LOCAL_SOURCES = (
    "Busy.az", "Boss.az", "HelloJob", "Glorri", "JobSearch.az",
    "HRX", "Work.az", "eJob.az", "hh1.az", "hh.ru",
)
HIDE_RETIRED_STEP = "hide-retired-local-sources-2026-10-05"

_MAINTENANCE = """
CREATE TABLE IF NOT EXISTS maintenance_steps (
    name TEXT PRIMARY KEY,
    done_at TEXT NOT NULL
)
"""


def hide_retired_local(conn) -> int:
    """Hide collected ads from RETIRED_LOCAL_SOURCES once. Returns rows hidden
    (0 when the step already ran). The caller commits."""
    conn.execute(_MAINTENANCE)
    done = conn.execute(
        "SELECT 1 FROM maintenance_steps WHERE name = ?", (HIDE_RETIRED_STEP,)
    ).fetchone()
    if done:
        return 0
    names = [name.lower() for name in RETIRED_LOCAL_SOURCES]
    marks = ", ".join("?" for _ in names)
    where = f"""
        WHERE COALESCE(j.owner_subject, '') = ''
          AND COALESCE(j.hidden, 0) = 0
          AND j.id IN (
              SELECT js.job_id FROM job_sources js WHERE LOWER(js.source_name) IN ({marks})
          )
          AND j.id NOT IN (
              SELECT js.job_id FROM job_sources js WHERE LOWER(js.source_name) NOT IN ({marks})
          )
    """
    ids = [int(row[0]) for row in conn.execute(f"SELECT j.id FROM jobs j {where}", names + names).fetchall()]
    for start in range(0, len(ids), 200):
        chunk = ids[start:start + 200]
        conn.execute(
            f"UPDATE jobs SET hidden = 1 WHERE id IN ({', '.join('?' for _ in chunk)})",
            chunk,
        )
    conn.execute(
        "INSERT INTO maintenance_steps (name, done_at) VALUES (?, ?) ON CONFLICT (name) DO NOTHING",
        (HIDE_RETIRED_STEP, datetime.now().astimezone().isoformat(timespec="seconds")),
    )
    return len(ids)


# Requests spent on metered APIs (Jooble's key allows 500 in total), counted
# per source and calendar month so a connector can stop before the limit.
_API_USAGE = """
CREATE TABLE IF NOT EXISTS api_usage (
    name TEXT NOT NULL,
    period TEXT NOT NULL,
    requests INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (name, period)
)
"""


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


class Store:
    def __init__(self, path: Path | None = None, *, sqlite_only: bool = False) -> None:
        from worker.jobs_db import connect, postgres_enabled

        if postgres_enabled() and not sqlite_only:
            self.path = None
            self.conn = connect()
        else:
            self.path = path or DB_PATH
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.conn = sqlite3.connect(self.path)
            self.conn.row_factory = sqlite3.Row
            self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(SCHEMA)
        self._ensure_cleaned_column()
        self._ensure_staff_columns()
        self._seed()
        with self.conn:
            self.hidden_retired = hide_retired_local(self.conn)
            self.conn.execute(_API_USAGE)
            from worker.cv_queue import ensure_cv_queue
            from worker.skills import ensure_skills
            from worker.roles import ensure_roles

            self.skills_seeded, self.skills_backfilled = ensure_skills(self.conn)
            self.roles_seeded, self.role_weights_seeded = ensure_roles(self.conn)
            self.cv_queue_enqueued = ensure_cv_queue(self.conn)

    def close(self) -> None:
        self.conn.close()

    def _ensure_cleaned_column(self) -> None:
        cols = {row[1] for row in self.conn.execute("PRAGMA table_info(jobs)")}
        if "cleaned_text" not in cols:
            self.conn.execute("ALTER TABLE jobs ADD COLUMN cleaned_text TEXT")

    def _ensure_staff_columns(self) -> None:
        cols = {row[1] for row in self.conn.execute("PRAGMA table_info(jobs)")}
        alters = {
            "content_locked": "INTEGER NOT NULL DEFAULT 0",
            "hidden": "INTEGER NOT NULL DEFAULT 0",
            "merged_into": "INTEGER",
            "reject_reason": "TEXT NOT NULL DEFAULT ''",
            # Same declarations as api/app/cabinet_store.py, so either side may add them.
            "owner_subject": "TEXT NOT NULL DEFAULT ''",
            "remote": "INTEGER NOT NULL DEFAULT 0",
            # JSON list of curated tech names, e.g. ["Python", "AWS"]. '' = not scanned yet.
            "tech_stack": "TEXT NOT NULL DEFAULT ''",
            # 1 when the ad offers visa sponsorship or relocation support.
            "relocation": "INTEGER NOT NULL DEFAULT 0",
            # Normalized tech category (techstack.CATEGORIES), "-" = not a tech
            # role, '' = not classified yet.
            "category": "TEXT NOT NULL DEFAULT ''",
            # Free-text salary shown on the ad, same declaration as the API side
            # (cabinet_store). Sources with structured pay (Reed) fill it,
            # e.g. "45,000–55,000 GBP per annum".
            "salary": "TEXT NOT NULL DEFAULT ''",
        }
        for name, decl in alters.items():
            if name not in cols:
                self.conn.execute(f"ALTER TABLE jobs ADD COLUMN {name} {decl}")
        self.conn.commit()


    def _seed(self) -> None:
        sql = """
        INSERT INTO crawl_sources (
            name, homepage, connector, entry_url, enabled, min_delay_seconds,
            go_decision, go_decided_by, go_decided_at, credit_note, api_key_env, note
        ) VALUES (
            :name, :homepage, :connector, :entry_url, :enabled, :min_delay_seconds,
            :go_decision, :go_decided_by, :go_decided_at, :credit_note, :api_key_env, :note
        )
        ON CONFLICT(name) DO UPDATE SET
            homepage = excluded.homepage,
            connector = excluded.connector,
            entry_url = excluded.entry_url,
            enabled = excluded.enabled,
            min_delay_seconds = excluded.min_delay_seconds,
            go_decision = excluded.go_decision,
            go_decided_by = excluded.go_decided_by,
            go_decided_at = excluded.go_decided_at,
            credit_note = CASE
                WHEN crawl_sources.credit_note IS NULL OR crawl_sources.credit_note = ''
                THEN excluded.credit_note
                ELSE crawl_sources.credit_note
            END,
            api_key_env = excluded.api_key_env,
            note = excluded.note
        """
        with self.conn:
            self.conn.executemany(sql, SOURCES)
            # Sources dropped from the catalog stay in the table (their runs and
            # ads are kept) but are switched off so no pass collects them again.
            names = [row["name"] for row in SOURCES]
            marks = ", ".join("?" for _ in names)
            self.conn.execute(
                f"""
                UPDATE crawl_sources
                SET enabled = 0, go_decision = 'retired',
                    note = 'Kataloqdan çıxarılıb, artıq toplanmır. Köhnə elanlar saxlanılır.'
                WHERE name NOT IN ({marks}) AND (enabled != 0 OR go_decision != 'retired')
                """,
                names,
            )

    def api_requests_used(self, name: str, period: str) -> int:
        row = self.conn.execute(
            "SELECT requests FROM api_usage WHERE name = ? AND period = ?", (name, period)
        ).fetchone()
        return int(row[0]) if row else 0

    def add_api_requests(self, name: str, period: str, count: int = 1) -> None:
        """Counted and committed before the request is sent, so a crash
        mid-request still uses up budget instead of hiding it."""
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO api_usage (name, period, requests) VALUES (?, ?, ?)
                ON CONFLICT (name, period) DO UPDATE SET requests = api_usage.requests + excluded.requests
                """,
                (name, period, int(count)),
            )

    def source_by_name(self, name: str) -> sqlite3.Row:
        row = self.conn.execute("SELECT * FROM crawl_sources WHERE name = ?", (name,)).fetchone()
        if row is None:
            raise KeyError(name)
        return row

    def disabled_sources(self) -> list[sqlite3.Row]:
        return list(
            self.conn.execute(
                "SELECT * FROM crawl_sources WHERE enabled = 0 AND go_decision != 'retired' ORDER BY id"
            )
        )

    def last_ok_run(self, source_id: int) -> str:
        row = self.conn.execute(
            """
            SELECT started_at FROM crawl_runs
            WHERE source_id = ? AND status = 'ok'
            ORDER BY id DESC LIMIT 1
            """,
            (source_id,),
        ).fetchone()
        return str(row["started_at"]) if row else ""

    def set_credit_note(self, name: str, credit_note: str) -> None:
        with self.conn:
            self.conn.execute(
                "UPDATE crawl_sources SET credit_note = ? WHERE name = ?",
                (credit_note, name),
            )

    def has_source_url(self, url: str) -> bool:
        row = self.conn.execute("SELECT 1 FROM job_sources WHERE source_url = ?", (url,)).fetchone()
        return row is not None

    def start_run(self, source_id: int) -> int:
        cur = self.conn.execute(
            "INSERT INTO crawl_runs (source_id, started_at, status) VALUES (?, ?, 'running')",
            (source_id, now_iso()),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def finish_run(
        self,
        run_id: int,
        *,
        status: str,
        found: int,
        created: int,
        updated: int,
        error: str | None,
    ) -> None:
        with self.conn:
            self.conn.execute(
                """
                UPDATE crawl_runs
                SET finished_at = ?, status = ?, found_count = ?, created_count = ?,
                    updated_count = ?, error = ?
                WHERE id = ?
                """,
                (now_iso(), status, found, created, updated, error, run_id),
            )

    def upsert(self, item: dict) -> str:
        title = str(item["title"]).strip()
        company = str(item.get("company") or "").strip()
        city = str(item.get("city") or "").strip()
        text = str(item.get("text") or "").strip()
        url = str(item["source_url"]).strip()
        source_name = str(item["source_name"]).strip()
        external_id = str(item.get("external_id") or "")[:200]
        credit = str(item.get("credit_note") or "")
        stack = item.get("tech_stack") or []
        stack_json = json.dumps([str(x) for x in stack][:12], ensure_ascii=False)
        remote = 1 if item.get("remote") else 0
        relocation = 1 if item.get("relocation") else 0
        category = str(item.get("job_category") or "")[:40]
        salary = str(item.get("salary") or "").strip()[:120]
        key = norm_key(title, company, city)
        seen = now_iso()
        with self.conn:
            existing = self.conn.execute(
                "SELECT id, job_id FROM job_sources WHERE source_url = ?",
                (url,),
            ).fetchone()
            if existing:
                held = self.conn.execute(
                    """
                    SELECT COALESCE(content_locked, 0) AS content_locked,
                           COALESCE(hidden, 0) AS hidden,
                           merged_into
                    FROM jobs WHERE id = ?
                    """,
                    (existing["job_id"],),
                ).fetchone()
                self.conn.execute(
                    """
                    UPDATE job_sources
                    SET source_name = ?, external_id = ?, last_seen = ?, credit_note = ?
                    WHERE id = ?
                    """,
                    (source_name, external_id, seen, credit, existing["id"]),
                )
                locked = held and (
                    int(held["content_locked"] or 0) == 1
                    or int(held["hidden"] or 0) == 1
                    or held["merged_into"]
                )
                if not locked:
                    self.conn.execute(
                        """
                        UPDATE jobs
                        SET title = ?, company = ?, city = ?, text = ?, status = 'published',
                            cleaned_text = CASE WHEN text = ? THEN cleaned_text ELSE NULL END,
                            tech_stack = ?, remote = ?, relocation = ?, category = ?
                        WHERE id = ?
                        """,
                        (
                            title, company, city, text, text,
                            stack_json, remote, relocation, category, existing["job_id"],
                        ),
                    )
                    if salary:
                        self.conn.execute(
                            "UPDATE jobs SET salary = ? WHERE id = ?", (salary, existing["job_id"])
                        )
                    self._set_norm_key(int(existing["job_id"]), key)
                    from worker.skills import sync_job_skills

                    sync_job_skills(self.conn, int(existing["job_id"]), stack)
                return "updated"
            job = self.conn.execute("SELECT id FROM jobs WHERE norm_key = ?", (key,)).fetchone()
            if job:
                job_id = int(job["id"])
                kind = "updated"
            else:
                cur = self.conn.execute(
                    """
                    INSERT INTO jobs (
                        title, company, city, text, status, created_at, norm_key,
                        tech_stack, remote, relocation, category
                    )
                    VALUES (?, ?, ?, ?, 'published', ?, ?, ?, ?, ?, ?)
                    """,
                    (title, company, city, text, seen, key, stack_json, remote, relocation, category),
                )
                job_id = int(cur.lastrowid)
                kind = "created"
                if salary:
                    self.conn.execute("UPDATE jobs SET salary = ? WHERE id = ?", (salary, job_id))
                from worker.skills import sync_job_skills

                sync_job_skills(self.conn, job_id, stack)
            self.conn.execute(
                """
                INSERT INTO job_sources (
                    job_id, source_name, source_url, external_id, last_seen, credit_note
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (job_id, source_name, url, external_id, seen, credit),
            )
            return kind

    def backfill_derived(self, limit: int = 500) -> int:
        """Tech stack, category and relocation for collected rows saved before
        those columns existed.

        Only scraped rows (empty owner_subject) with an empty tech_stack or
        category are read. A stack already stored (it may come from source
        tags) is kept. The source's category was not stored for old rows, so
        their category comes from the title and stack. Nothing is deleted;
        remote and relocation are only ever switched on.
        """
        from worker.techstack import (
            classify_category,
            extract_stack,
            is_tech_job,
            relocation_flag,
            remote_flag,
        )

        rows = self.conn.execute(
            """
            SELECT id, title, city, COALESCE(NULLIF(cleaned_text, ''), text) AS body,
                   COALESCE(tech_stack, '') AS tech_stack,
                   COALESCE(remote, 0) AS remote, COALESCE(relocation, 0) AS relocation
            FROM jobs
            WHERE COALESCE(owner_subject, '') = ''
              AND (COALESCE(tech_stack, '') = '' OR COALESCE(category, '') = '')
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        done = 0
        with self.conn:
            for row in rows:
                title = str(row["title"] or "")
                city = str(row["city"] or "")
                body = str(row["body"] or "")
                stack: list[str] | None = None
                if row["tech_stack"]:
                    try:
                        loaded = json.loads(row["tech_stack"])
                        stack = [str(x) for x in loaded] if isinstance(loaded, list) else None
                    except (TypeError, ValueError):
                        stack = None
                if stack is None:
                    stack = extract_stack(body, None, title)
                category = classify_category("", title, stack) if is_tech_job(title) else "-"
                remote = 1 if int(row["remote"] or 0) or remote_flag(title, city, body) else 0
                relocation = 1 if int(row["relocation"] or 0) or relocation_flag(title, city, body) else 0
                stack_json = json.dumps(stack, ensure_ascii=False)
                self.conn.execute(
                    "UPDATE jobs SET tech_stack = ?, category = ?, remote = ?, relocation = ? WHERE id = ?",
                    (stack_json, category, remote, relocation, row["id"]),
                )
                from worker.skills import sync_job_skills

                sync_job_skills(self.conn, int(row["id"]), stack)
                done += 1
        return done

    def _set_norm_key(self, job_id: int, key: str) -> None:
        other = self.conn.execute(
            "SELECT id FROM jobs WHERE norm_key = ? AND id != ?",
            (key, job_id),
        ).fetchone()
        if other is None:
            self.conn.execute("UPDATE jobs SET norm_key = ? WHERE id = ?", (key, job_id))

    def list_jobs(self) -> list[sqlite3.Row]:
        return list(
            self.conn.execute(
                """
                SELECT j.title, j.company, j.city,
                       group_concat(js.source_name, ', ') AS source
                FROM jobs j
                JOIN job_sources js ON js.job_id = j.id
                GROUP BY j.id
                ORDER BY j.id
                """
            )
        )
