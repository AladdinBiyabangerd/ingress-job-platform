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
# One-shot: re-run extract_stack on scraped ads after the curated dictionary grows.
REEXTRACT_STACK_STEP = "reextract-tech-stack-variants-v5-2026-10-13"
# One-shot: drop the CJK half of "English / 日本語" titles on stored ads.
LATIN_TITLE_STEP = "latin-title-mixed-cjk-2026-10-13"

# One-shot: merge ads that are one ad saved twice only because two boards wrote
# the remote place differently ("remote worldwide" vs empty). Keeps the
# published/older row and moves every source onto it.
MERGE_REMOTE_TWINS_STEP = "merge-remote-place-twins-2026-10-13"
# One-shot: re-check published collected ads with the 2026-10-13 title rules.
TITLE_RULE_STEP = "title-rule-recheck-2026-10-13"
# Second pass after "Delivery Manager" became non-IT (same reason, new marker
# so databases that already ran the first pass re-check once more).
TITLE_RULE_STEP_B = "title-rule-recheck-2026-10-13b-delivery"
TITLE_RULE_REASON = "title_rule_2026_10_13"
# Collected ads no source has listed for this long are hidden as expired.
EXPIRE_REASON = "expired_not_seen"
EXPIRE_AFTER_DAYS = 7
# Sources whose listing completeness cannot be told (capped APIs, monthly
# threads, paged search): their ads never expire from absence. Prefix match,
# lower case ("greenhouse boards" would cover every Greenhouse group).
EXPIRE_EXEMPT_SOURCES = (
    "himalayas", "djinni", "hn who is hiring", "jooble", "reed.co.uk",
    "remote ok", "wellfound", "get on board",
)


def _expire_exempt(name: str) -> bool:
    low = str(name or "").strip().lower()
    return any(low.startswith(prefix) for prefix in EXPIRE_EXEMPT_SOURCES)

_MERGES = """
CREATE TABLE IF NOT EXISTS job_merges (
    id INTEGER PRIMARY KEY,
    kept_id INTEGER NOT NULL,
    hidden_id INTEGER NOT NULL UNIQUE,
    created_at TEXT NOT NULL
)
"""


def like_prefix(value: str) -> str:
    """LIKE pattern matching values that start with value (use ESCAPE '\\')."""
    escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return escaped + "%"


def _parse_ts(value: object):
    from datetime import timezone

    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


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


def _content_norm(value: object) -> str:
    """Compare ad content ignoring whitespace and letter case."""
    return " ".join(str(value or "").split()).casefold()


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _open_sqlite(path: Path) -> sqlite3.Connection:
    # WAL + busy_timeout: several source threads write at once without
    # "database is locked"; each thread uses its own connection.
    conn = sqlite3.connect(path, timeout=60)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 60000")
    try:
        conn.execute("PRAGMA journal_mode = WAL")
    except sqlite3.OperationalError:
        pass
    return conn


class Store:
    def __init__(self, path: Path | None = None, *, sqlite_only: bool = False) -> None:
        from worker.jobs_db import connect, postgres_enabled

        if postgres_enabled() and not sqlite_only:
            self.path = None
            self.conn = connect()
        else:
            self.path = path or DB_PATH
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.conn = _open_sqlite(self.path)
        self.conn.executescript(SCHEMA)
        self._ensure_cleaned_column()
        self._ensure_staff_columns()
        self._ensure_run_columns()
        self._seed()
        with self.conn:
            self.hidden_retired = hide_retired_local(self.conn)
            self.conn.execute(_API_USAGE)
            self.conn.execute(_MERGES)
            from worker.cv_queue import ensure_cv_queue
            from worker.skills import ensure_skills
            from worker.roles import ensure_roles

            self.skills_seeded, self.skills_backfilled = ensure_skills(self.conn)
            self.roles_seeded, self.role_weights_seeded = ensure_roles(self.conn)
            from worker.categories import ensure_categories, reload_rules

            self.categories_seeded = ensure_categories(self.conn)
            reload_rules(self.conn)
            self.cv_queue_enqueued = ensure_cv_queue(self.conn)
            from worker.market_fit import ensure_rejects_table

            ensure_rejects_table(self.conn)

    def close(self) -> None:
        self.conn.close()

    def thread_store(self) -> "Store":
        """Same database, own connection, no schema/seed work. One per thread."""
        other = Store.__new__(Store)
        other.__dict__.update(self.__dict__)
        if self.path is None:
            from worker.jobs_db import connect

            other.conn = connect()
        else:
            other.conn = _open_sqlite(self.path)
        return other

    def _ensure_cleaned_column(self) -> None:
        cols = {row[1] for row in self.conn.execute("PRAGMA table_info(jobs)")}
        if "cleaned_text" not in cols:
            self.conn.execute("ALTER TABLE jobs ADD COLUMN cleaned_text TEXT")

    def _ensure_run_columns(self) -> None:
        cols = {row[1] for row in self.conn.execute("PRAGMA table_info(crawl_runs)")}
        if "complete_listing" not in cols:
            with self.conn:
                # 1 = the run listed the source's whole catalog (expiry may trust it).
                self.conn.execute(
                    "ALTER TABLE crawl_runs ADD COLUMN complete_listing INTEGER NOT NULL DEFAULT 0"
                )

    def _ensure_staff_columns(self) -> None:
        cols = {row[1] for row in self.conn.execute("PRAGMA table_info(jobs)")}
        alters = {
            "content_locked": "INTEGER NOT NULL DEFAULT 0",
            "hidden": "INTEGER NOT NULL DEFAULT 0",
            "merged_into": "INTEGER",
            "reject_reason": "TEXT NOT NULL DEFAULT ''",
            # Same declarations as api/app/cabinet_store.py, so either side may add them.
            "owner_subject": "TEXT NOT NULL DEFAULT ''",
            "updated_at": "TEXT NOT NULL DEFAULT ''",
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
            # Listing language code (az/en/ru/de/…). Scraped rows are filled by
            # listing_language(); cabinet ads keep the owner-chosen value.
            "language": "TEXT NOT NULL DEFAULT ''",
            # Date the source says the ad was posted (worker.posted.parse_posted).
            # NULL = unknown; the API then falls back to created_at.
            "posted_at": "TEXT",
        }
        for name, decl in alters.items():
            if name not in cols:
                self.conn.execute(f"ALTER TABLE jobs ADD COLUMN {name} {decl}")
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS jobs_public_list ON jobs(status, hidden, merged_into, created_at, id)"
        )
        self.conn.execute("CREATE INDEX IF NOT EXISTS job_sources_job ON job_sources(job_id, id)")
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
        complete_listing: bool = False,
    ) -> None:
        with self.conn:
            self.conn.execute(
                """
                UPDATE crawl_runs
                SET finished_at = ?, status = ?, found_count = ?, created_count = ?,
                    updated_count = ?, error = ?, complete_listing = ?
                WHERE id = ?
                """,
                (now_iso(), status, found, created, updated, error,
                 1 if complete_listing else 0, run_id),
            )

    def upsert(self, item: dict) -> str:
        from worker.posted import latin_title, parse_posted

        title = latin_title(str(item["title"]).strip())
        posted = parse_posted(item.get("posted_at") or item.get("_stamp")) or None
        company = str(item.get("company") or "").strip()
        from worker.place import is_remote_place, normalize_city

        raw_city = str(item.get("city") or "").strip()
        city = normalize_city(raw_city)
        text = str(item.get("text") or "").strip()
        url = str(item["source_url"]).strip()
        source_name = str(item["source_name"]).strip()
        external_id = str(item.get("external_id") or "")[:200]
        credit = str(item.get("credit_note") or "")
        stack = item.get("tech_stack") or []
        stack_json = json.dumps([str(x) for x in stack][:12], ensure_ascii=False)
        remote = 1 if item.get("remote") or is_remote_place(raw_city) else 0
        relocation = 1 if item.get("relocation") else 0
        category = str(item.get("job_category") or "")[:40]
        salary = str(item.get("salary") or "").strip()[:120]
        from worker.listing_language import listing_language

        language = listing_language(title, text)[:8]
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
                           merged_into, title, text, status,
                           COALESCE(reject_reason, '') AS reject_reason
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
                if held and self._unexpire(int(existing["job_id"]), held):
                    held = dict(held)
                    held["hidden"] = 0
                locked = held and (
                    int(held["content_locked"] or 0) == 1
                    or int(held["hidden"] or 0) == 1
                    or held["merged_into"]
                )
                if not locked:
                    # Do not force status=published — pending scraped ads stay in
                    # the moderator queue until staff approves.
                    self.conn.execute(
                        """
                        UPDATE jobs
                        SET title = ?, company = ?, city = ?, text = ?,
                            cleaned_text = CASE WHEN text = ? THEN cleaned_text ELSE NULL END,
                            tech_stack = ?, remote = ?, relocation = ?, category = ?,
                            language = ?,
                            updated_at = CASE
                                WHEN title = ? AND text = ? AND company = ? AND city = ?
                                THEN COALESCE(NULLIF(updated_at, ''), created_at)
                                ELSE ? END
                        WHERE id = ?
                        """,
                        (
                            title, company, city, text, text,
                            stack_json, remote, relocation, category, language,
                            title, text, company, city, seen,
                            existing["job_id"],
                        ),
                    )
                    if (held["status"] or "") == "published" and (
                        _content_norm(latin_title(held["title"])) != _content_norm(title)
                        or _content_norm(held["text"]) != _content_norm(text)
                    ):
                        # Staff approved different content; send it back to the
                        # moderation queue so the new text is reviewed first.
                        self.conn.execute(
                            "UPDATE jobs SET status = 'pending' WHERE id = ?",
                            (existing["job_id"],),
                        )
                    if salary:
                        self.conn.execute(
                            "UPDATE jobs SET salary = ? WHERE id = ?", (salary, existing["job_id"])
                        )
                    self._set_norm_key(int(existing["job_id"]), key)
                if posted:
                    # Date only: no updated_at or status change.
                    self.conn.execute(
                        "UPDATE jobs SET posted_at = ? WHERE id = ?", (posted, existing["job_id"])
                    )
                    from worker.skills import sync_job_skills

                    sync_job_skills(self.conn, int(existing["job_id"]), stack)
                return "updated"
            job = self.conn.execute("SELECT id FROM jobs WHERE norm_key = ?", (key,)).fetchone()
            if job is None and not city:
                job = self._legacy_remote_twin(title, company)
            if job:
                job_id = int(job["id"])
                kind = "updated"
                if posted:
                    self.conn.execute(
                        "UPDATE jobs SET posted_at = COALESCE(posted_at, ?) WHERE id = ?",
                        (posted, job_id),
                    )
                again = self.conn.execute(
                    "SELECT COALESCE(hidden, 0) AS hidden, merged_into, "
                    "COALESCE(reject_reason, '') AS reject_reason FROM jobs WHERE id = ?",
                    (job_id,),
                ).fetchone()
                if again:
                    self._unexpire(job_id, again)
            else:
                cur = self.conn.execute(
                    """
                    INSERT INTO jobs (
                        title, company, city, text, status, created_at, norm_key,
                        tech_stack, remote, relocation, category, language, updated_at
                    )
                    VALUES (?, ?, ?, ?, 'pending', ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        title, company, city, text, seen, key, stack_json,
                        remote, relocation, category, language, seen,
                    ),
                )
                job_id = int(cur.lastrowid)
                kind = "created"
                if salary:
                    self.conn.execute("UPDATE jobs SET salary = ? WHERE id = ?", (salary, job_id))
                if posted:
                    self.conn.execute("UPDATE jobs SET posted_at = ? WHERE id = ?", (posted, job_id))
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

    def backfill_language(self, limit: int = 2000) -> int:
        """Recompute listing language from title+body for scraped rows.

        Skips cabinet ads (non-empty owner_subject) so az/ru labels stay.
        Rewrites wrong stored en (English title + foreign body) after deploy.
        """
        from worker.listing_language import listing_language

        rows = self.conn.execute(
            """
            SELECT id, title, COALESCE(NULLIF(cleaned_text, ''), text) AS body,
                   COALESCE(language, '') AS language
            FROM jobs
            WHERE COALESCE(owner_subject, '') = ''
              AND status = 'published'
              AND COALESCE(hidden, 0) = 0
              AND (merged_into IS NULL OR merged_into = 0)
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        done = 0
        with self.conn:
            for row in rows:
                title = str(row["title"] or "")
                body = str(row["body"] or "")
                detected = listing_language(title, body)[:8]
                stored = str(row["language"] or "").strip().lower()
                if stored == detected:
                    continue
                self.conn.execute(
                    "UPDATE jobs SET language = ? WHERE id = ?",
                    (detected, row["id"]),
                )
                done += 1
        return done

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

    def normalize_cities(self, limit: int = 2000) -> int:
        """Collapse remote labels and alias cities on scraped rows."""
        from worker.place import is_remote_place, normalize_city

        rows = self.conn.execute(
            """
            SELECT id, city, COALESCE(remote, 0) AS remote
            FROM jobs
            WHERE COALESCE(owner_subject, '') = ''
              AND TRIM(COALESCE(city, '')) != ''
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        done = 0
        with self.conn:
            for row in rows:
                raw = str(row["city"] or "")
                cleaned = normalize_city(raw)
                remote = 1 if int(row["remote"] or 0) or is_remote_place(raw) else int(row["remote"] or 0)
                if cleaned == raw and remote == int(row["remote"] or 0):
                    continue
                self.conn.execute(
                    "UPDATE jobs SET city = ?, remote = ? WHERE id = ?",
                    (cleaned, remote, row["id"]),
                )
                done += 1
        return done

    def reextract_tech_stack(self, *, force: bool = False) -> int:
        """Re-extract chips from stored title+body with the current dictionary.

        Scraped rows only (empty owner_subject). Staff-locked and merged ads
        are skipped. Existing chips are remapped through the new aliases, then
        text matches fill in names the old list missed (no TAGS_ENOUGH skip).
        Returns how many jobs had their stored tech_stack JSON change.
        """
        from worker.skills import sync_job_skills
        from worker.techstack import MAX_STACK, dump_stack, extract_stack, stack_from_tags

        self.conn.execute(_MAINTENANCE)
        if not force:
            done = self.conn.execute(
                "SELECT 1 FROM maintenance_steps WHERE name = ?",
                (REEXTRACT_STACK_STEP,),
            ).fetchone()
            if done:
                return 0

        rows = self.conn.execute(
            """
            SELECT id, title, COALESCE(NULLIF(cleaned_text, ''), text) AS body,
                   COALESCE(tech_stack, '') AS tech_stack
            FROM jobs
            WHERE COALESCE(owner_subject, '') = ''
              AND COALESCE(content_locked, 0) = 0
              AND (merged_into IS NULL OR merged_into = 0)
            """
        ).fetchall()
        # Stack/skill rows only: no status, updated_at or acceptance columns are
        # touched, so approved ads stay approved. Batched commits (Postgres-safe);
        # the step is recorded after the last batch, a crash just re-runs it and
        # unchanged rows are skipped (idempotent).
        from worker.skills import _skill_id_map, ensure_skill_tables

        ensure_skill_tables(self.conn)
        skill_map = _skill_id_map(self.conn)
        updated = 0
        batch = 200
        for start in range(0, len(rows), batch):
            with self.conn:
                for row in rows[start:start + batch]:
                    title = str(row["title"] or "")
                    body = str(row["body"] or "")
                    raw = row["tech_stack"]
                    fresh = extract_stack(body, None, title)
                    for name in stack_from_tags(raw):
                        if name not in fresh:
                            fresh.append(name)
                    stack = fresh[:MAX_STACK]
                    stack_json = dump_stack(stack)
                    previous = raw if isinstance(raw, str) else dump_stack(
                        [str(x) for x in raw] if isinstance(raw, list) else []
                    )
                    if stack_json == previous:
                        continue
                    self.conn.execute(
                        "UPDATE jobs SET tech_stack = ? WHERE id = ?",
                        (stack_json, row["id"]),
                    )
                    sync_job_skills(self.conn, int(row["id"]), stack, skill_map=skill_map)
                    updated += 1
        with self.conn:
            self.conn.execute(
                "INSERT INTO maintenance_steps (name, done_at) VALUES (?, ?) "
                "ON CONFLICT (name) DO NOTHING",
                (REEXTRACT_STACK_STEP, now_iso()),
            )
        print(
            f"tech stack reextract {REEXTRACT_STACK_STEP}: scanned={len(rows)} updated={updated}",
            flush=True,
        )
        return updated

    def latin_titles(self) -> int:
        """One-shot: apply latin_title() to stored scraped titles. Title only;
        status, updated_at and norm_key are left alone (no re-review)."""
        from worker.posted import latin_title

        self.conn.execute(_MAINTENANCE)
        if self.conn.execute(
            "SELECT 1 FROM maintenance_steps WHERE name = ?", (LATIN_TITLE_STEP,)
        ).fetchone():
            return 0
        rows = self.conn.execute(
            "SELECT id, title FROM jobs WHERE COALESCE(owner_subject, '') = '' "
            "AND COALESCE(content_locked, 0) = 0"
        ).fetchall()
        updated = 0
        with self.conn:
            for row in rows:
                old = str(row["title"] or "")
                new = latin_title(old)
                if new and new != old:
                    self.conn.execute("UPDATE jobs SET title = ? WHERE id = ?", (new, row["id"]))
                    updated += 1
            self.conn.execute(
                "INSERT INTO maintenance_steps (name, done_at) VALUES (?, ?) "
                "ON CONFLICT (name) DO NOTHING",
                (LATIN_TITLE_STEP, now_iso()),
            )
        print(f"latin titles {LATIN_TITLE_STEP}: scanned={len(rows)} updated={updated}", flush=True)
        return updated

    def _legacy_remote_twin(self, title: str, company: str):
        """Same title and company saved earlier with a raw remote label as the
        place ("remote worldwide", "remote"): the same ad, so no second row."""
        from worker.place import is_remote_place

        prefix = norm_key(title, company, "")  # "title|company|"
        twin = self._spaced_company_twin(title, company)
        if twin is not None:
            return twin
        rows = self.conn.execute(
            "SELECT id, norm_key FROM jobs WHERE norm_key LIKE ? ESCAPE ? "
            "AND COALESCE(merged_into, 0) = 0",
            (like_prefix(prefix), "\\"),
        ).fetchall()
        for row in rows:
            tail = str(row["norm_key"])[len(prefix):]
            if tail and is_remote_place(tail):
                return row
        return None

    def _spaced_company_twin(self, title: str, company: str):
        """"Duck Duck Go" and "DuckDuckGo": same title, company equal once the
        spaces are gone, and the stored place is empty or a remote label."""
        from worker.place import is_remote_place

        title_key = norm_key(title, "", "").split("|", 1)[0]
        squash = lambda value: "".join(str(value).split())
        wanted = squash(norm_key("", company, "").split("|")[1])
        if not title_key or not wanted:
            return None
        rows = self.conn.execute(
            "SELECT id, norm_key FROM jobs WHERE norm_key LIKE ? ESCAPE ? "
            "AND COALESCE(merged_into, 0) = 0",
            (like_prefix(title_key + "|"), "\\"),
        ).fetchall()
        for row in rows:
            parts = str(row["norm_key"]).split("|")
            if len(parts) != 3 or squash(parts[1]) != wanted:
                continue
            if not parts[2] or is_remote_place(parts[2]):
                return row
        return None

    def _set_norm_key(self, job_id: int, key: str) -> None:
        other = self.conn.execute(
            "SELECT id FROM jobs WHERE norm_key = ? AND id != ?",
            (key, job_id),
        ).fetchone()
        if other is None:
            self.conn.execute("UPDATE jobs SET norm_key = ? WHERE id = ?", (key, job_id))
            return
        # Another row already holds this key: the same ad saved twice. Merge
        # collected twins instead of silently keeping two visible rows.
        kept = self._merge_twins([job_id, int(other["id"])])
        if kept is None:
            print(f"norm_key collision kept apart: job={job_id} other={other['id']} key={key!r}", flush=True)

    def touch_seen(self, urls, *, batch: int = 200) -> int:
        """Mark stored sources whose URL a board still lists as seen now."""
        clean = [str(u).strip() for u in urls if str(u or "").strip()]
        if not clean:
            return 0
        seen = now_iso()
        done = 0
        for start in range(0, len(clean), batch):
            chunk = clean[start:start + batch]
            marks = ", ".join("?" for _ in chunk)
            with self.conn:
                cur = self.conn.execute(
                    f"UPDATE job_sources SET last_seen = ? WHERE source_url IN ({marks})",
                    [seen, *chunk],
                )
                count = getattr(cur, "rowcount", -1)
                done += int(count) if count is not None and count >= 0 else 0
        return done

    def _unexpire(self, job_id: int, row) -> bool:
        """Show again an ad hidden as expired once a source lists it again.
        Only rows this worker hid as expired are touched (not staff hides,
        not merged twins). Changed content still goes back to review via the
        normal upsert path."""
        if not row or not int(row["hidden"] or 0) or row["merged_into"]:
            return False
        if str(row["reject_reason"] or "") != EXPIRE_REASON:
            return False
        self.conn.execute(
            "UPDATE jobs SET hidden = 0, reject_reason = '' WHERE id = ? AND reject_reason = ?",
            (job_id, EXPIRE_REASON),
        )
        return True

    def _merge_twins(self, ids: list[int]) -> int | None:
        """Merge collected rows that are one ad. Keeps the visible published
        row, else the oldest; the others get hidden=1 + merged_into and their
        sources move to the kept row. Cabinet (owner) and staff-locked rows
        are never merged. Returns the kept id, or None when nothing merged."""
        unique = sorted({int(i) for i in ids})
        if len(unique) < 2:
            return None
        marks = ", ".join("?" for _ in unique)
        rows = self.conn.execute(
            f"""
            SELECT id, status, COALESCE(hidden, 0) AS hidden, created_at,
                   COALESCE(owner_subject, '') AS owner_subject,
                   COALESCE(content_locked, 0) AS content_locked, merged_into
            FROM jobs WHERE id IN ({marks})
            """,
            unique,
        ).fetchall()
        rows = [
            r for r in rows
            if not r["owner_subject"] and not int(r["content_locked"] or 0)
            and not r["merged_into"]
        ]
        if len(rows) < 2:
            return None

        def rank(r):
            visible = str(r["status"] or "") == "published" and not int(r["hidden"] or 0)
            stamp = _parse_ts(r["created_at"])
            return (0 if visible else 1, stamp.timestamp() if stamp else float("inf"), int(r["id"]))

        rows.sort(key=rank)
        keep = int(rows[0]["id"])
        now = now_iso()
        for r in rows[1:]:
            dup = int(r["id"])
            self.conn.execute(
                "UPDATE jobs SET hidden = 1, merged_into = ? WHERE id = ?", (keep, dup)
            )
            self.conn.execute(
                "UPDATE job_sources SET job_id = ? WHERE job_id = ?", (keep, dup)
            )
            self.conn.execute(
                "INSERT INTO job_merges (kept_id, hidden_id, created_at) VALUES (?, ?, ?) "
                "ON CONFLICT (hidden_id) DO NOTHING",
                (keep, dup, now),
            )
        return keep

    def merge_remote_twins(self, *, force: bool = False) -> int:
        """One-time: re-key collected rows with the current norm_key (remote
        labels no longer part of the key) and merge rows that now share a key.
        Returns how many rows were merged away."""
        self.conn.execute(_MAINTENANCE)
        self.conn.execute(_MERGES)
        if not force and self.conn.execute(
            "SELECT 1 FROM maintenance_steps WHERE name = ?", (MERGE_REMOTE_TWINS_STEP,)
        ).fetchone():
            return 0
        rows = self.conn.execute(
            """
            SELECT id, title, company, city, norm_key FROM jobs
            WHERE COALESCE(owner_subject, '') = ''
              AND COALESCE(content_locked, 0) = 0
              AND (merged_into IS NULL OR merged_into = 0)
            ORDER BY id
            """
        ).fetchall()
        groups: dict[str, list[int]] = {}
        current: dict[int, str] = {}
        for r in rows:
            key = norm_key(str(r["title"] or ""), str(r["company"] or ""), str(r["city"] or ""))
            groups.setdefault(key, []).append(int(r["id"]))
            current[int(r["id"])] = str(r["norm_key"] or "")
        merged = 0
        rekeyed = 0
        with self.conn:
            for key, ids in groups.items():
                keep = ids[0]
                if len(ids) > 1:
                    kept = self._merge_twins(ids)
                    if kept is not None:
                        keep = kept
                        merged += len(ids) - 1
                if current.get(keep) != key:
                    taken = self.conn.execute(
                        "SELECT id FROM jobs WHERE norm_key = ? AND id != ?", (key, keep)
                    ).fetchone()
                    if taken is None:
                        self.conn.execute("UPDATE jobs SET norm_key = ? WHERE id = ?", (key, keep))
                        rekeyed += 1
            self.conn.execute(
                "INSERT INTO maintenance_steps (name, done_at) VALUES (?, ?) "
                "ON CONFLICT (name) DO NOTHING",
                (MERGE_REMOTE_TWINS_STEP, now_iso()),
            )
        print(f"remote twins {MERGE_REMOTE_TWINS_STEP}: merged={merged} rekeyed={rekeyed}", flush=True)
        return merged

    def recheck_title_rule(self, *, force: bool = False, step: str = TITLE_RULE_STEP_B) -> list[tuple[int, str]]:
        """One-time: hide published collected ads that the 2026-10-13 title
        rules make non-IT (hidden=1, reject_reason=TITLE_RULE_REASON). Status
        stays, so staff can unhide. Owner and staff-locked ads are skipped.
        Returns (id, title) of the rows hidden."""
        from worker.techstack import title_rule_2026_10_13_rejects

        self.conn.execute(_MAINTENANCE)
        if not force and self.conn.execute(
            "SELECT 1 FROM maintenance_steps WHERE name = ?", (step,)
        ).fetchone():
            return []
        rows = self.conn.execute(
            """
            SELECT id, title FROM jobs
            WHERE status = 'published'
              AND COALESCE(hidden, 0) = 0
              AND (merged_into IS NULL OR merged_into = 0)
              AND COALESCE(owner_subject, '') = ''
              AND COALESCE(content_locked, 0) = 0
            """
        ).fetchall()
        hit = [(int(r["id"]), str(r["title"] or "")) for r in rows
               if title_rule_2026_10_13_rejects(str(r["title"] or ""))]
        with self.conn:
            for start in range(0, len(hit), 200):
                chunk = [job_id for job_id, _ in hit[start:start + 200]]
                marks = ", ".join("?" for _ in chunk)
                self.conn.execute(
                    f"UPDATE jobs SET hidden = 1, reject_reason = ? WHERE id IN ({marks})",
                    [TITLE_RULE_REASON, *chunk],
                )
            self.conn.execute(
                "INSERT INTO maintenance_steps (name, done_at) VALUES (?, ?) "
                "ON CONFLICT (name) DO NOTHING",
                (step, now_iso()),
            )
        print(f"title rule {step}: checked={len(rows)} hidden={len(hit)}", flush=True)
        for job_id, title in hit:
            print(f"title rule hidden: {job_id} {title}", flush=True)
        return hit

    def expire_unseen(self, *, now=None, days: int = EXPIRE_AFTER_DAYS, batch: int = 200) -> int:
        """Hide collected ads no source has listed for `days`, but only when
        every source of the ad had a successful crawl after it last saw the
        ad (a broken or paused source never expires anything). Sets
        hidden=1 and reject_reason='expired_not_seen'; upsert shows the ad
        again when a source lists it. Timestamps are compared as parsed
        datetimes, so mixed UTC offsets and Postgres/SQLite text are safe."""
        from datetime import timedelta, timezone

        moment = now or datetime.now(timezone.utc)
        cutoff = moment - timedelta(days=days)
        # Latest complete run per source (ok and listed the whole catalog,
        # see runner.complete_listing), compared as parsed datetimes (MAX over
        # text would mis-order mixed UTC offsets). Exempt sources never count.
        parsed_ok: dict[str, object] = {}
        for r in self.conn.execute(
            """
            SELECT s.name AS name, r.started_at AS started_at
            FROM crawl_runs r JOIN crawl_sources s ON s.id = r.source_id
            WHERE r.status = 'ok' AND COALESCE(r.complete_listing, 0) = 1
              AND COALESCE(r.error, '') = ''
            """
        ).fetchall():
            stamp = _parse_ts(r["started_at"])
            name = str(r["name"] or "").lower()
            if _expire_exempt(name):
                continue
            if stamp is not None and (name not in parsed_ok or stamp > parsed_ok[name]):
                parsed_ok[name] = stamp
        rows = self.conn.execute(
            """
            SELECT j.id AS id, js.source_name AS source_name, js.last_seen AS last_seen
            FROM jobs j JOIN job_sources js ON js.job_id = j.id
            WHERE COALESCE(j.owner_subject, '') = ''
              AND COALESCE(j.content_locked, 0) = 0
              AND COALESCE(j.hidden, 0) = 0
              AND (j.merged_into IS NULL OR j.merged_into = 0)
            """
        ).fetchall()
        per_job: dict[int, list[tuple[str, object]]] = {}
        for r in rows:
            per_job.setdefault(int(r["id"]), []).append(
                (str(r["source_name"] or "").lower(), _parse_ts(r["last_seen"]))
            )
        expired: list[int] = []
        for job_id, seen in per_job.items():
            stamps = [stamp for _, stamp in seen]
            if any(stamp is None for stamp in stamps):
                continue
            if max(stamps) >= cutoff:
                continue
            ok = True
            for name, stamp in seen:
                run = parsed_ok.get(name)
                if run is None or run <= stamp:
                    ok = False
                    break
            if ok:
                expired.append(job_id)
        hidden = 0
        for start in range(0, len(expired), batch):
            chunk = expired[start:start + batch]
            marks = ", ".join("?" for _ in chunk)
            with self.conn:
                cur = self.conn.execute(
                    f"UPDATE jobs SET hidden = 1, reject_reason = ? "
                    f"WHERE id IN ({marks}) AND COALESCE(hidden, 0) = 0",
                    [EXPIRE_REASON, *chunk],
                )
                count = getattr(cur, "rowcount", -1)
                hidden += int(count) if count is not None and count >= 0 else len(chunk)
        print(
            f"expire unseen: checked={len(per_job)} expired={hidden} cutoff={cutoff.isoformat(timespec='seconds')}",
            flush=True,
        )
        return hidden

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
