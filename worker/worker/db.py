"""Jobs store.

SQLite when DATABASE_URL is unset. Postgres, shared with the API, when it is set.
"""

from __future__ import annotations

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


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


class Store:
    def __init__(self, path: Path | None = None) -> None:
        from worker.jobs_db import connect, postgres_enabled

        if postgres_enabled():
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

    def source_by_name(self, name: str) -> sqlite3.Row:
        row = self.conn.execute("SELECT * FROM crawl_sources WHERE name = ?", (name,)).fetchone()
        if row is None:
            raise KeyError(name)
        return row

    def disabled_sources(self) -> list[sqlite3.Row]:
        return list(self.conn.execute("SELECT * FROM crawl_sources WHERE enabled = 0 ORDER BY id"))

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
                            cleaned_text = CASE WHEN text = ? THEN cleaned_text ELSE NULL END
                        WHERE id = ?
                        """,
                        (title, company, city, text, text, existing["job_id"]),
                    )
                    self._set_norm_key(int(existing["job_id"]), key)
                return "updated"
            job = self.conn.execute("SELECT id FROM jobs WHERE norm_key = ?", (key,)).fetchone()
            if job:
                job_id = int(job["id"])
                kind = "updated"
            else:
                cur = self.conn.execute(
                    """
                    INSERT INTO jobs (title, company, city, text, status, created_at, norm_key)
                    VALUES (?, ?, ?, ?, 'published', ?, ?)
                    """,
                    (title, company, city, text, seen, key),
                )
                job_id = int(cur.lastrowid)
                kind = "created"
            self.conn.execute(
                """
                INSERT INTO job_sources (
                    job_id, source_name, source_url, external_id, last_seen, credit_note
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (job_id, source_name, url, external_id, seen, credit),
            )
            return kind

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
