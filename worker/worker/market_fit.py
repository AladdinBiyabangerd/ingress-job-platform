"""Azerbaijan-market fit for scraped ads.

When keyword detection finds no remote / relocation / visa signal, ask the
shared AI gateway (free providers first, OpenAI last). Unsuitable URLs are
stored in ``crawl_rejects`` so the next crawl skips them without another call.
"""

from __future__ import annotations

import logging
import os
import re
import sqlite3
from datetime import datetime, timezone
from typing import Any

from worker.ai_flags import feature_on
from worker.ai_gateway import complete_json
from worker.techstack import (
    international_reloc_offer,
    open_market_tier,
    relocation_flag,
    remote_flag,
)

log = logging.getLogger("ingress-job.worker.market_fit")

PURPOSE = "market_fit"
PROMPT_VERSION = "market-fit-v4"
ENV_FLAG = "AI_MARKET_FIT_ENABLED"

# Graded rule confidence (how sure deterministic rules are the ad is OK to publish).
# Stronger AZ-open signals → higher %; bare board default / weak keyword → lower.
_RULE_SCORE_AZ = 96
_RULE_SCORE_OPEN_PLACE = 90
_RULE_SCORE_OPEN_BODY = 84
_RULE_SCORE_INTL_RELOC = 86
_RULE_SCORE_SCHEMA = 78
_RULE_SCORE_REMOTE_PLACE = 76
_RULE_SCORE_REMOTE_TITLE = 72
_RULE_SCORE_REMOTE_TEXT = 70
_RULE_SCORE_RELOC_KW = 68
_RULE_SCORE_BOARD_DEFAULT = 64

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
    "confidence is an integer 0-100: how sure you are that this ad IS suitable "
    "to publish under those Azerbaijan-market rules "
    "(not how sure you are that suitable=false).\n"
    "- 80–100: you are confident it should be published (worldwide/EMEA remote "
    "or real reloc/visa) → suitable=true;\n"
    "- around 30–50: you are unsure whether it qualifies for publish → "
    "suitable=false;\n"
    "- 0–25: you are confident it must NOT be published (US-only, residency "
    "lock, no visa, foreign onsite) → suitable=false.\n"
    "Never return high confidence with suitable=false.\n"
    "Reply with JSON only matching the schema."
)

_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "suitable",
        "remote",
        "relocation",
        "visa_support",
        "reason",
        "confidence",
    ],
    "properties": {
        "suitable": {"type": "boolean"},
        "remote": {"type": "boolean"},
        "relocation": {"type": "boolean"},
        "visa_support": {"type": "boolean"},
        "reason": {"type": "string"},
        "confidence": {"type": "integer", "minimum": 0, "maximum": 100},
    },
}


def clamp_confidence(raw: Any) -> int:
    """Normalize AI confidence to 0–100."""
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return 0
    return max(0, min(100, value))


def fit_score(*, suitable: bool, confidence: int) -> int:
    """Staff-facing % = how sure AI is the ad is OK to publish under our rules.

    Example: 30 ≈ unsure; 90 ≈ sure it qualifies; rejected/unsuitable must
    never show as 100. Older models sometimes returned suitable=false + 100
    ("sure of the reject") — invert that into a low publish-confidence.
    """
    raw = clamp_confidence(confidence)
    if suitable:
        return raw
    return min(raw, 100 - raw, 35)


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
    return rule_fit_confidence(
        title,
        place,
        text,
        pre_remote=pre_remote,
        pre_relocation=pre_relocation,
        remote_default=remote_default,
        relocation_default=relocation_default,
    ) is not None


def rule_fit_confidence(
    title: str,
    place: str,
    text: str,
    *,
    pre_remote: bool | None,
    pre_relocation: bool | None,
    remote_default: bool,
    relocation_default: bool,
) -> dict[str, Any] | None:
    """Graded rule %: how sure deterministic rules are the ad is OK to publish.

    Returns ``{"confidence": 0-100, "reason": str}`` when keywords / schema /
    board default give a market signal; None when AI should decide instead.
    Never returns a flat 100 for every clear hit — stronger open-market and
    visa/reloc evidence scores higher than a bare board default.
    """
    kw_remote = remote_flag(title, place, text)
    kw_reloc = relocation_flag(title, place, text)
    schema_remote = pre_remote is True
    schema_reloc = pre_relocation is True
    board_remote = bool(remote_default)
    board_reloc = bool(relocation_default)

    if not (
        kw_remote
        or kw_reloc
        or schema_remote
        or schema_reloc
        or board_remote
        or board_reloc
    ):
        return None

    open_tier = open_market_tier(title, place, text)
    intl_reloc = international_reloc_offer(title, place, text)
    title_remote = bool(
        re.search(r"(?i)\bremote\b", title or "")
        and not re.search(r"(?i)\bhybrid\b|on[\s-]?site", title or "")
    )
    place_remote = bool(
        re.search(r"(?i)\bremote\b|worldwide|anywhere|telecommute|\bwfh\b", place or "")
        and not re.search(r"(?i)\bhybrid\b", place or "")
    )

    # Strongest matching evidence wins; small bonus when several agree.
    candidates: list[tuple[int, str]] = []
    if open_tier == "az":
        candidates.append((_RULE_SCORE_AZ, "azerbaijan / CIS open market"))
    elif open_tier == "place":
        candidates.append((_RULE_SCORE_OPEN_PLACE, "open remote place (worldwide/EMEA)"))
    elif open_tier == "body":
        candidates.append((_RULE_SCORE_OPEN_BODY, "open-market wording in description"))
    if intl_reloc:
        candidates.append((_RULE_SCORE_INTL_RELOC, "international visa / relocation"))
    elif kw_reloc:
        candidates.append((_RULE_SCORE_RELOC_KW, "relocation keywords"))
    if schema_remote or schema_reloc:
        candidates.append((_RULE_SCORE_SCHEMA, "source schema remote/relocation"))
    if place_remote:
        candidates.append((_RULE_SCORE_REMOTE_PLACE, "remote location field"))
    if title_remote:
        candidates.append((_RULE_SCORE_REMOTE_TITLE, "remote in title"))
    if kw_remote and not (place_remote or title_remote or open_tier):
        candidates.append((_RULE_SCORE_REMOTE_TEXT, "remote keywords in description"))
    if (board_remote or board_reloc) and not (
        kw_remote or kw_reloc or schema_remote or schema_reloc or open_tier
    ):
        candidates.append((_RULE_SCORE_BOARD_DEFAULT, "board remote/relocation default"))

    if not candidates:
        # Schema/board + weak overlap already covered; fall back sanely.
        if schema_remote or schema_reloc:
            candidates.append((_RULE_SCORE_SCHEMA, "source schema remote/relocation"))
        elif board_remote or board_reloc:
            candidates.append((_RULE_SCORE_BOARD_DEFAULT, "board remote/relocation default"))
        elif kw_remote:
            candidates.append((_RULE_SCORE_REMOTE_TEXT, "remote keywords"))
        else:
            candidates.append((_RULE_SCORE_RELOC_KW, "relocation keywords"))

    score, reason = max(candidates, key=lambda row: row[0])

    bonus = 0
    evidence = sum(
        (
            1 if open_tier else 0,
            1 if intl_reloc or kw_reloc else 0,
            1 if kw_remote or place_remote or title_remote else 0,
            1 if schema_remote or schema_reloc else 0,
        )
    )
    if evidence >= 3:
        bonus += 6
    elif evidence >= 2:
        bonus += 3
    if (schema_remote or schema_reloc) and (kw_remote or kw_reloc or open_tier):
        bonus += 2

    # Cap below absolute 100 unless AZ/CIS is named — leaves room for staff doubt.
    capped = clamp_confidence(score + bonus)
    if open_tier != "az":
        capped = min(capped, 95)
    return {
        "confidence": capped,
        "reason": reason,
    }


# Last clarify miss reason (for recheck job / ops; not a public API).
last_miss_error: str = ""

# After each crawl pass: AI-score pending scraped ads that still lack ai_confidence
# (rule-passed rows show AI% empty until staff used to click recheck). Leftover
# rows wait for the next hourly pass. Override with AI_MARKET_FIT_AUTO_SCORE_LIMIT.
AUTO_SCORE_PER_RUN = 40


def auto_score_limit() -> int:
    raw = (os.environ.get("AI_MARKET_FIT_AUTO_SCORE_LIMIT") or "").strip()
    if not raw:
        return AUTO_SCORE_PER_RUN
    try:
        return max(0, min(200, int(raw)))
    except ValueError:
        return AUTO_SCORE_PER_RUN


def score_pending_without_ai(
    conn: sqlite3.Connection,
    *,
    limit: int | None = None,
) -> dict[str, int]:
    """Fill AI % on pending scraped ads missing ``ai_confidence``.

    Same outcomes as staff queue recheck: suitable → write ``ai_confidence``;
    unsuitable → ``status=rejected``. Company/manual ads (owner_subject) skipped.
    Oldest id first. Soft-no-op when market_fit / gateway is off.
    """
    cap = AUTO_SCORE_PER_RUN if limit is None else max(0, int(limit))
    stats = {"planned": 0, "checked": 0, "rejected": 0, "failed": 0, "skipped": 0}
    if cap <= 0:
        return stats
    if not feature_on("market_fit", conn) or not feature_on("gateway", conn):
        return stats

    rows = conn.execute(
        """
        SELECT id, title, company, city, text
        FROM jobs
        WHERE status = 'pending'
          AND COALESCE(owner_subject, '') = ''
          AND ai_confidence IS NULL
          AND COALESCE(merged_into, 0) = 0
        ORDER BY id ASC
        LIMIT ?
        """,
        (cap,),
    ).fetchall()
    stats["planned"] = len(rows)
    if not rows:
        return stats

    now = datetime.now().astimezone().isoformat(timespec="seconds")
    for row in rows:
        job_id = int(row["id"])
        live = conn.execute(
            """
            SELECT status, ai_confidence, COALESCE(owner_subject, '') AS owner_subject
            FROM jobs WHERE id = ?
            """,
            (job_id,),
        ).fetchone()
        if (
            live is None
            or (live["status"] or "") != "pending"
            or live["ai_confidence"] is not None
            or (live["owner_subject"] or "") != ""
        ):
            stats["skipped"] += 1
            continue

        verdict = clarify_market_fit(
            title=row["title"] or "",
            company=row["company"] or "",
            place=row["city"] or "",
            text=row["text"] or "",
            conn=conn,
        )
        if verdict is None:
            stats["failed"] += 1
            # Feature flipped off mid-batch — stop burning attempts.
            if last_miss_error in {"market_fit_off", "ai_disabled"}:
                break
            continue

        reason = str(verdict.get("reason") or "")[:300]
        confidence = int(verdict.get("confidence") or 0)
        if not verdict.get("suitable"):
            conn.execute(
                """
                UPDATE jobs
                SET status = 'rejected',
                    reject_reason = ?,
                    rule_confidence = NULL,
                    ai_confidence = ?,
                    market_fit_reason = ?,
                    updated_at = ?
                WHERE id = ? AND status = 'pending' AND ai_confidence IS NULL
                """,
                (reason or "unsuitable", confidence, reason, now, job_id),
            )
            stats["checked"] += 1
            stats["rejected"] += 1
        else:
            remote = 1 if verdict.get("remote") else 0
            relocation = 1 if verdict.get("relocation") else 0
            conn.execute(
                """
                UPDATE jobs
                SET remote = ?,
                    relocation = ?,
                    ai_confidence = ?,
                    market_fit_reason = ?,
                    updated_at = ?
                WHERE id = ? AND status = 'pending' AND ai_confidence IS NULL
                """,
                (remote, relocation, confidence, reason, now, job_id),
            )
            stats["checked"] += 1
        conn.commit()
    return stats


def clarify_market_fit(
    *,
    title: str,
    company: str,
    place: str,
    text: str,
    conn: sqlite3.Connection | None,
) -> dict[str, Any] | None:
    """Ask AI. Returns verdict dict, or None when AI is off / fails."""
    global last_miss_error
    if not feature_on("market_fit", conn):
        last_miss_error = "market_fit_off"
        log.warning("market_fit skipped: feature off")
        return None
    if not feature_on("gateway", conn):
        last_miss_error = "ai_disabled"
        log.warning("market_fit skipped: gateway off")
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
        last_miss_error = (result.error or "failed")[:180]
        log.warning("market_fit ai miss: %s", last_miss_error)
        return None
    last_miss_error = ""
    data = result.data
    remote = bool(data.get("remote"))
    relocation = bool(data.get("relocation") or data.get("visa_support"))
    suitable = bool(data.get("suitable"))
    if suitable and not (remote or relocation):
        suitable = False
    confidence = fit_score(
        suitable=suitable,
        confidence=clamp_confidence(data.get("confidence")),
    )
    return {
        "suitable": suitable,
        "remote": remote,
        "relocation": relocation,
        "visa_support": bool(data.get("visa_support")),
        "reason": str(data.get("reason") or "")[:300],
        "confidence": confidence,
        "cached": result.cached,
    }
