"""Azerbaijan-market fit for scraped ads.

When keyword detection finds no remote / relocation / visa signal, ask the
shared AI gateway (free providers first, OpenAI last). Unsuitable URLs are
stored in ``crawl_rejects`` so the next crawl skips them without another call.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone
from typing import Any

from worker.ai_flags import feature_on
from worker.ai_gateway import complete_json
from worker.techstack import relocation_flag, remote_flag

log = logging.getLogger("ingress-job.worker.market_fit")

PURPOSE = "market_fit"
PROMPT_VERSION = "market-fit-v1"
ENV_FLAG = "AI_MARKET_FIT_ENABLED"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS crawl_rejects (
    source_url TEXT PRIMARY KEY,
    reason TEXT NOT NULL DEFAULT '',
    decided_at TEXT NOT NULL DEFAULT '',
    via_ai INTEGER NOT NULL DEFAULT 0
);
"""

_SYSTEM = (
    "You classify international tech job ads for a job board whose candidates "
    "are primarily in Azerbaijan.\n"
    "suitable=true only when the role lets someone in Azerbaijan apply usefully:\n"
    "- remote work that is worldwide / anywhere / EMEA / not locked to one foreign "
    "country (US-only, Canada-only, UK-only, EU-residents-only → suitable=false);\n"
    "- OR relocation / visa sponsorship to move abroad.\n"
    "Onsite or hybrid jobs in a foreign city (e.g. Tel Aviv, London, Berlin) "
    "with no remote, relocation, or visa support are suitable=false. "
    "LinkedIn #LI-Hybrid without visa/relocation is suitable=false.\n"
    "Set remote/relocation/visa_support from the ad. visa_support that only helps "
    "relocation counts as relocation=true.\n"
    "Be strict. If unclear, suitable=false.\n"
    "Reply with JSON only matching the schema."
)

_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["suitable", "remote", "relocation", "visa_support", "reason"],
    "properties": {
        "suitable": {"type": "boolean"},
        "remote": {"type": "boolean"},
        "relocation": {"type": "boolean"},
        "visa_support": {"type": "boolean"},
        "reason": {"type": "string"},
    },
}


def ensure_rejects_table(conn: sqlite3.Connection | None) -> None:
    if conn is None:
        return
    conn.executescript(_SCHEMA)


def is_rejected(conn: sqlite3.Connection | None, source_url: str) -> bool:
    url = (source_url or "").strip()
    if not url or conn is None:
        return False
    ensure_rejects_table(conn)
    row = conn.execute(
        "SELECT 1 FROM crawl_rejects WHERE source_url = ?",
        (url,),
    ).fetchone()
    return row is not None


def mark_rejected(
    conn: sqlite3.Connection | None,
    source_url: str,
    reason: str = "",
    *,
    via_ai: bool = False,
) -> None:
    url = (source_url or "").strip()
    if not url or conn is None:
        return
    ensure_rejects_table(conn)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    conn.execute(
        """
        INSERT INTO crawl_rejects (source_url, reason, decided_at, via_ai)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(source_url) DO UPDATE SET
            reason = excluded.reason,
            decided_at = excluded.decided_at,
            via_ai = excluded.via_ai
        """,
        (url, (reason or "")[:300], now, 1 if via_ai else 0),
    )
    try:
        conn.commit()
    except Exception:
        pass


def has_clear_market_signal(
    title: str,
    place: str,
    text: str,
    *,
    pre_remote: bool | None,
    pre_relocation: bool | None,
    remote_default: bool,
    relocation_default: bool,
) -> bool:
    """True when keywords, source schema, or board default already decides."""
    if remote_default or relocation_default:
        return True
    if pre_remote is True or pre_relocation is True:
        return True
    if remote_flag(title, place, text) or relocation_flag(title, place, text):
        return True
    return False


def clarify_market_fit(
    *,
    title: str,
    company: str,
    place: str,
    text: str,
    conn: sqlite3.Connection | None,
) -> dict[str, Any] | None:
    """Ask AI. Returns verdict dict, or None when AI is off / fails."""
    if not feature_on("market_fit", conn):
        return None
    user = (
        f"Title: {title}\n"
        f"Company: {company}\n"
        f"Location: {place}\n\n"
        f"Ad text:\n{(text or '')[:10000]}"
    )
    result = complete_json(
        purpose=PURPOSE,
        prompt_version=PROMPT_VERSION,
        system=_SYSTEM,
        user=user,
        schema=_JSON_SCHEMA,
        schema_name="market_fit",
        conn=conn,
        timeout=45.0,
    )
    if not result.ok or not isinstance(result.data, dict):
        log.info("market_fit ai miss: %s", result.error or "failed")
        return None
    data = result.data
    remote = bool(data.get("remote"))
    relocation = bool(data.get("relocation") or data.get("visa_support"))
    suitable = bool(data.get("suitable"))
    if suitable and not (remote or relocation):
        suitable = False
    return {
        "suitable": suitable,
        "remote": remote,
        "relocation": relocation,
        "visa_support": bool(data.get("visa_support")),
        "reason": str(data.get("reason") or "")[:300],
        "cached": result.cached,
    }
