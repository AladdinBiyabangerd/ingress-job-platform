"""Staff-controlled AI flow flags in the shared jobs DB.

Env still hard-offs a feature when set to 0/false/off. A DB row then wins.
With no row: gateway / job_tidy / engagement_copy default on when OPENAI_API_KEY
is set; other flows follow gateway.
"""

from __future__ import annotations

import logging
import os
import sqlite3
import time
from datetime import datetime, timezone
from threading import Lock
from typing import Any

log = logging.getLogger("ingress-job.api.ai_flags")

FEATURES = (
    "gateway",
    "cv_fallback",
    "job_tidy",
    "embeddings",
    "rerank",
    "llm_rerank",
    "match_why",
    "role_coach",
    "digest_intro",
    "engagement_copy",
)

FEATURE_ENV = {
    "gateway": "AI_GATEWAY_ENABLED",
    "cv_fallback": "CV_AI_FALLBACK_ENABLED",
    "rerank": "AI_RERANK_ENABLED",
    "llm_rerank": "AI_LLM_RERANK_ENABLED",
    "match_why": "AI_MATCH_WHY_ENABLED",
    "role_coach": "AI_ROLE_COACH_ENABLED",
    "digest_intro": "DIGEST_AI_INTRO_ENABLED",
    "engagement_copy": "ENGAGEMENT_AI_COPY_ENABLED",
}

_FALSE = {"0", "false", "no", "off"}
_TRUE = {"1", "true", "yes", "on"}
_TTL = 15.0

FLAG_SCHEMA = """
CREATE TABLE IF NOT EXISTS ai_feature_flags (
    feature TEXT PRIMARY KEY,
    enabled INTEGER NOT NULL,
    updated_at TEXT NOT NULL DEFAULT '',
    updated_by TEXT NOT NULL DEFAULT ''
);
"""

_LOCK = Lock()
_CACHE: dict[str, bool] | None = None
_CACHE_AT = 0.0

_UNKNOWN = "Naməlum AI axını"


class FlagError(Exception):
    def __init__(self, detail: str, status: int = 422) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status = status


def key_configured() -> bool:
    return bool(os.environ.get("OPENAI_API_KEY", "").strip())


def invalidate_flag_cache() -> None:
    global _CACHE, _CACHE_AT
    with _LOCK:
        _CACHE = None
        _CACHE_AT = 0.0


def ensure_flag_table(conn: sqlite3.Connection | None) -> None:
    if conn is None:
        return
    conn.executescript(FLAG_SCHEMA)


def _env_state(feature: str) -> bool | None:
    name = FEATURE_ENV.get(feature)
    if not name:
        return None
    raw = os.environ.get(name, "").strip().lower()
    if raw in _FALSE:
        return False
    if raw in _TRUE:
        return True
    return None


def _open_conn():
    from app.jobs_db import connect, postgres_enabled
    from app.sqlite_jobs import DB_PATH

    if postgres_enabled():
        return connect()
    conn = sqlite3.connect(DB_PATH, timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _cell(row: Any, key: str, index: int):
    if hasattr(row, "keys"):
        try:
            return row[key]
        except Exception:
            pass
    return row[index]


def _load_stored(conn) -> dict[str, bool]:
    ensure_flag_table(conn)
    rows = conn.execute("SELECT feature, enabled FROM ai_feature_flags").fetchall()
    out: dict[str, bool] = {}
    for row in rows:
        name = str(_cell(row, "feature", 0) or "")
        if name in FEATURES:
            out[name] = bool(int(_cell(row, "enabled", 1) or 0))
    return out


def stored_flags(conn=None) -> dict[str, bool]:
    global _CACHE, _CACHE_AT
    if conn is not None:
        try:
            return _load_stored(conn)
        except Exception as exc:
            if not isinstance(exc, (AttributeError, TypeError)):
                log.warning("ai flags load failed: %s", exc)
            return {}
    now = time.monotonic()
    with _LOCK:
        if _CACHE is not None and now - _CACHE_AT < _TTL:
            return dict(_CACHE)
    opened = None
    try:
        opened = _open_conn()
        loaded = _load_stored(opened)
    except Exception as exc:
        log.warning("ai flags load failed: %s", exc)
        loaded = {}
    finally:
        if opened is not None:
            try:
                opened.close()
            except Exception:
                pass
    with _LOCK:
        _CACHE = loaded
        _CACHE_AT = time.monotonic()
        return dict(_CACHE)


def feature_on(feature: str, conn=None) -> bool:
    if feature not in FEATURES:
        return False
    env = _env_state(feature)
    if env is False:
        return False
    stored = stored_flags(conn)
    if feature in stored:
        return bool(stored[feature])
    if env is True:
        return True
    # Notification engagement copy defaults on with the key (same as gateway).
    if feature in {"gateway", "job_tidy", "engagement_copy"}:
        return key_configured()
    return feature_on("gateway", conn)


def effective_flags(conn=None) -> dict[str, bool]:
    return {name: feature_on(name, conn) for name in FEATURES}


def set_flags(conn, flags: dict[str, Any], *, updated_by: str = "") -> dict[str, bool]:
    if not isinstance(flags, dict) or not flags:
        raise FlagError(_UNKNOWN)
    unknown = [key for key in flags if key not in FEATURES]
    if unknown:
        raise FlagError(_UNKNOWN)
    ensure_flag_table(conn)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    who = (updated_by or "").strip()[:120]
    for name, value in flags.items():
        if not isinstance(value, bool):
            raise FlagError(_UNKNOWN)
        conn.execute(
            """
            INSERT INTO ai_feature_flags (feature, enabled, updated_at, updated_by)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(feature) DO UPDATE SET
                enabled = excluded.enabled,
                updated_at = excluded.updated_at,
                updated_by = excluded.updated_by
            """,
            (name, 1 if value else 0, now, who),
        )
    try:
        conn.commit()
    except Exception:
        pass
    invalidate_flag_cache()
    return effective_flags(conn)
